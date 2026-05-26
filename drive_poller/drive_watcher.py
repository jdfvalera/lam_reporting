import argparse
import base64
import hashlib
import json
import logging
import os
import re
import tempfile
import time
from ssl import SSLEOFError
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from agent.folder_parser import BRAND_KEY_MAP, load_config, parse_campaign

log = logging.getLogger(__name__)

DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"
SCOPES = ["https://www.googleapis.com/auth/drive"]

_WEEK_RE = re.compile(r"^[Ww]\d+$")
_RIESBECKS_WEEK_RE = re.compile(r"^(?:[Ww])?\d+$")
_OUTPUT_RE = re.compile(r"(^\(|_Internal_Raw_File_for_CS\.xlsx$)")
_DOWNLOAD_SUFFIXES = {".xlsx", ".json"}
_STATE_FILE = ".drive_poller_state.json"


@dataclass
class DriveFile:
    id: str
    name: str
    mime_type: str
    md5_checksum: str | None = None
    modified_time: str | None = None
    size: str | None = None

    @property
    def is_folder(self) -> bool:
        return self.mime_type == DRIVE_FOLDER_MIME

    @property
    def signature(self) -> str:
        return "|".join([
            self.id,
            self.md5_checksum or "",
            self.modified_time or "",
            self.size or "",
        ])


@dataclass
class SyncContext:
    tmp_root: Path
    local_root: Path
    folder_ids: dict[tuple[str, ...], str] = field(default_factory=dict)
    remote_files: dict[tuple[str, ...], dict[str, DriveFile]] = field(default_factory=dict)
    before_hashes: dict[Path, str] = field(default_factory=dict)
    state: dict = field(default_factory=dict)
    changed_dirs: set[Path] = field(default_factory=set)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_credentials():
    """
    Load Drive credentials from one of:
      - GOOGLE_SERVICE_ACCOUNT_JSON: raw service-account JSON
      - GOOGLE_SERVICE_ACCOUNT_JSON_B64: base64-encoded service-account JSON
      - GOOGLE_APPLICATION_CREDENTIALS: path to service-account JSON
      - GOOGLE_OAUTH_TOKEN_JSON: OAuth token JSON with refresh token
      - GOOGLE_OAUTH_TOKEN_JSON_B64: base64-encoded OAuth token JSON
      - GOOGLE_OAUTH_TOKEN_FILE: path to OAuth token JSON
      - optional GOOGLE_OAUTH_CLIENT_JSON / GOOGLE_OAUTH_CLIENT_FILE for token
        exports that do not include client_id/client_secret

    Service account is preferred for cloud deployment. OAuth token support is
    useful for local smoke tests from the existing gog-authorized account.
    """
    raw_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    raw_b64 = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_B64")
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    oauth_json = os.getenv("GOOGLE_OAUTH_TOKEN_JSON")
    oauth_b64 = os.getenv("GOOGLE_OAUTH_TOKEN_JSON_B64")
    oauth_path = os.getenv("GOOGLE_OAUTH_TOKEN_FILE")
    oauth_client_json = os.getenv("GOOGLE_OAUTH_CLIENT_JSON")
    oauth_client_path = os.getenv("GOOGLE_OAUTH_CLIENT_FILE")

    if raw_json:
        from google.oauth2 import service_account
        info = json.loads(raw_json)
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    if raw_b64:
        from google.oauth2 import service_account
        info = json.loads(base64.b64decode(raw_b64).decode("utf-8"))
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    if cred_path:
        from google.oauth2 import service_account
        return service_account.Credentials.from_service_account_file(cred_path, scopes=SCOPES)

    oauth_info = None
    if oauth_json:
        oauth_info = json.loads(oauth_json)
    elif oauth_b64:
        oauth_info = json.loads(base64.b64decode(oauth_b64).decode("utf-8"))
    elif oauth_path:
        with open(oauth_path) as f:
            oauth_info = json.load(f)

    if oauth_info:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        if "client_id" not in oauth_info or "client_secret" not in oauth_info:
            client_info = None
            if oauth_client_json:
                client_info = json.loads(oauth_client_json)
            elif oauth_client_path:
                with open(oauth_client_path) as f:
                    client_info = json.load(f)
            else:
                gog_credentials = Path.home() / ".config" / "gogcli" / "credentials.json"
                if gog_credentials.exists():
                    with open(gog_credentials) as f:
                        client_info = json.load(f)

            if client_info:
                oauth_info.setdefault("client_id", client_info.get("client_id"))
                oauth_info.setdefault("client_secret", client_info.get("client_secret"))

        creds = Credentials.from_authorized_user_info(oauth_info, scopes=SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return creds

    raise RuntimeError(
        "Missing Google Drive credentials. Set service-account credentials "
        "or GOOGLE_OAUTH_TOKEN_JSON/GOOGLE_OAUTH_TOKEN_FILE."
    )


def build_drive_service():
    from googleapiclient.discovery import build

    creds = _load_credentials()
    return build("drive", "v3", credentials=creds, cache_discovery=False)


class DriveClient:
    def __init__(self, service) -> None:
        self.service = service

    def list_children(self, folder_id: str) -> list[DriveFile]:
        files: list[DriveFile] = []
        page_token = None
        while True:
            resp = (
                self.service.files()
                .list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    spaces="drive",
                    fields="nextPageToken, files(id, name, mimeType, md5Checksum, modifiedTime, size)",
                    pageToken=page_token,
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                )
                .execute()
            )
            for item in resp.get("files", []):
                files.append(
                    DriveFile(
                        id=item["id"],
                        name=item["name"],
                        mime_type=item["mimeType"],
                        md5_checksum=item.get("md5Checksum"),
                        modified_time=item.get("modifiedTime"),
                        size=item.get("size"),
                    )
                )
            page_token = resp.get("nextPageToken")
            if not page_token:
                return files

    def download(self, file_id: str, dest: Path) -> None:
        from googleapiclient.http import MediaIoBaseDownload

        dest.parent.mkdir(parents=True, exist_ok=True)
        request = self.service.files().get_media(fileId=file_id, supportsAllDrives=True)
        with dest.open("wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

    def _execute_with_retry(self, request, label: str, attempts: int = 4):
        for attempt in range(1, attempts + 1):
            try:
                return request.execute()
            except (TimeoutError, ConnectionError, SSLEOFError) as exc:
                if attempt == attempts:
                    raise
                delay = 2 ** attempt
                log.warning("Drive %s failed (%s). Retrying in %ss [%s/%s]", label, exc, delay, attempt, attempts)
                time.sleep(delay)

    def upload_or_update(self, local_path: Path, parent_id: str, existing: DriveFile | None = None) -> DriveFile:
        from googleapiclient.http import MediaFileUpload

        body = {"name": local_path.name}
        if existing:
            request = self.service.files().update(
                fileId=existing.id,
                media_body=MediaFileUpload(str(local_path), resumable=True),
                fields="id, name, mimeType, md5Checksum, modifiedTime, size",
                supportsAllDrives=True,
            )
            result = self._execute_with_retry(request, f"update {local_path.name}")
        else:
            body["parents"] = [parent_id]
            request = self.service.files().create(
                body=body,
                media_body=MediaFileUpload(str(local_path), resumable=True),
                fields="id, name, mimeType, md5Checksum, modifiedTime, size",
                supportsAllDrives=True,
            )
            result = self._execute_with_retry(request, f"create {local_path.name}")
        return DriveFile(
            id=result["id"],
            name=result["name"],
            mime_type=result["mimeType"],
            md5_checksum=result.get("md5Checksum"),
            modified_time=result.get("modifiedTime"),
            size=result.get("size"),
        )


def _should_download(file: DriveFile) -> bool:
    if file.is_folder:
        return False
    if file.name.startswith("~$"):
        return False
    return Path(file.name).suffix.lower() in _DOWNLOAD_SUFFIXES


def _is_output_or_state(path: Path) -> bool:
    name = path.name
    return (
        bool(_OUTPUT_RE.search(name))
        or name == ".foodtown_state.json"
        or name == "usm_category_learned.json"
    )


def _record_folder(ctx: SyncContext, rel: tuple[str, ...], folder_id: str, children: list[DriveFile]) -> None:
    ctx.folder_ids[rel] = folder_id
    ctx.remote_files[rel] = {child.name: child for child in children if not child.is_folder}


def _foodtown_week_needs_partial(rel: tuple[str, ...], children: list[DriveFile]) -> bool:
    """True when a Foodtown week has Habanero inputs but no partial CS output yet."""
    if len(rel) < 3 or rel[0] != "Foodtown":
        return False

    week_match = _WEEK_RE.match(rel[-1])
    if not week_match:
        return False

    file_names = [child.name for child in children if not child.is_folder]
    input_names = [name.lower() for name in file_names]
    has_weekly = any(name.endswith(".xlsx") and "weekly" in name and not _is_output_or_state(Path(name)) for name in input_names)
    has_frequency = any(
        name.endswith(".xlsx")
        and ("frequency" in name or "freq" in name)
        and not _is_output_or_state(Path(name))
        for name in input_names
    )
    if not (has_weekly and has_frequency):
        return False

    week_num = int(re.search(r"\d+", rel[-1]).group())
    partial_prefix = f"(W{week_num})"
    return not any(
        name.startswith(partial_prefix) and name.endswith("_Internal_Raw_File_for_CS.xlsx")
        for name in file_names
    )


def _download_folder_files(client: DriveClient, ctx: SyncContext, rel: tuple[str, ...], folder_id: str, children: list[DriveFile]) -> None:
    local_dir = ctx.local_root.joinpath(*rel)
    local_dir.mkdir(parents=True, exist_ok=True)
    _record_folder(ctx, rel, folder_id, children)

    downloadable = [child for child in children if _should_download(child)]
    state_files = ctx.state.setdefault("files", {})
    changed = any(
        state_files.get("/".join(rel + (child.name,))) != child.signature
        for child in downloadable
    )
    force_scan = _foodtown_week_needs_partial(rel, children)

    if changed or force_scan:
        _mark_changed_dir(ctx, rel)
        if force_scan and not changed:
            log.info("Foodtown week missing partial CS; forcing scan: %s", "/".join(rel))
        for child in downloadable:
            dest = local_dir / child.name
            client.download(child.id, dest)
            ctx.before_hashes[dest] = _sha256(dest)
            state_files["/".join(rel + (child.name,))] = child.signature

    _download_existing_outputs_for_dir(client, ctx, rel, children)


def _find_root_learned_file(root_children: Iterable[DriveFile]) -> DriveFile | None:
    return next((f for f in root_children if f.name == "usm_category_learned.json" and not f.is_folder), None)


def _load_poll_state(client: DriveClient, root_children: Iterable[DriveFile]) -> dict:
    state_file = next((f for f in root_children if f.name == _STATE_FILE and not f.is_folder), None)
    if not state_file:
        return {"version": 1, "files": {}}

    with tempfile.TemporaryDirectory(prefix="lam-drive-state-") as tmp:
        path = Path(tmp) / _STATE_FILE
        try:
            client.download(state_file.id, path)
            data = json.loads(path.read_text() or "{}")
            if isinstance(data, dict):
                data.setdefault("version", 1)
                data.setdefault("files", {})
                return data
        except Exception:
            log.warning("Could not load Drive poller state; falling back to full scan", exc_info=True)
    return {"version": 1, "files": {}}


def _save_poll_state(client: DriveClient, ctx: SyncContext) -> None:
    state_path = ctx.tmp_root / _STATE_FILE
    state_path.write_text(json.dumps(ctx.state, indent=2, sort_keys=True) + "\n")
    root_id = ctx.folder_ids[tuple()]
    existing = ctx.remote_files.get(tuple(), {}).get(_STATE_FILE)
    uploaded = client.upload_or_update(state_path, root_id, existing)
    ctx.remote_files.setdefault(tuple(), {})[_STATE_FILE] = uploaded
    log.info("Updated Drive poller state: %s", _STATE_FILE)


def _mark_changed_dir(ctx: SyncContext, rel: tuple[str, ...]) -> None:
    if not rel:
        return
    ctx.changed_dirs.add(ctx.local_root.joinpath(*rel))


def _download_existing_outputs_for_dir(client: DriveClient, ctx: SyncContext, rel: tuple[str, ...], children: Iterable[DriveFile]) -> None:
    if ctx.local_root.joinpath(*rel) not in ctx.changed_dirs:
        return
    local_dir = ctx.local_root.joinpath(*rel)
    for child in children:
        if child.is_folder or not _is_output_or_state(Path(child.name)):
            continue
        dest = local_dir / child.name
        if dest.exists():
            continue
        client.download(child.id, dest)
        ctx.before_hashes[dest] = _sha256(dest)


def _sync_month_changed_dirs(ctx: SyncContext) -> None:
    expanded = set(ctx.changed_dirs)
    for changed in list(ctx.changed_dirs):
        try:
            rel = changed.relative_to(ctx.local_root).parts
        except ValueError:
            continue
        if len(rel) >= 3 and rel[0] in {"Foodtown", "Riesbecks"}:
            expanded.add(ctx.local_root.joinpath(*rel[:2]))
    ctx.changed_dirs = expanded


def _sync_drive_to_temp(client: DriveClient, root_folder_id: str) -> SyncContext:
    tmp = Path(tempfile.mkdtemp(prefix="lam-drive-poll-"))
    ctx = SyncContext(tmp_root=tmp, local_root=tmp / "inbox")
    ctx.local_root.mkdir(parents=True, exist_ok=True)

    root_children = client.list_children(root_folder_id)
    ctx.state = _load_poll_state(client, root_children)
    _record_folder(ctx, tuple(), root_folder_id, root_children)

    learned = _find_root_learned_file(root_children)
    learned_local = tmp / "usm_category_learned.json"
    if learned:
        client.download(learned.id, learned_local)
        ctx.before_hashes[learned_local] = _sha256(learned_local)
    else:
        learned_local.write_text("{}\n")
        ctx.before_hashes[learned_local] = _sha256(learned_local)
    os.environ["USM_CATEGORY_LEARNED_FILE"] = str(learned_local)
    try:
        from agent import categorizer
        categorizer.LEARNED_FILE = learned_local
    except Exception:
        log.warning("Could not patch USM learned-file path", exc_info=True)

    brand_folders = [f for f in root_children if f.is_folder and f.name in BRAND_KEY_MAP]
    for brand in sorted(brand_folders, key=lambda f: f.name):
        brand_rel = (brand.name,)
        brand_children = client.list_children(brand.id)
        _record_folder(ctx, brand_rel, brand.id, brand_children)

        for child in sorted([f for f in brand_children if f.is_folder and not f.name.startswith(".")], key=lambda f: f.name):
            campaign_rel = brand_rel + (child.name,)
            campaign_children = client.list_children(child.id)

            if brand.name in {"Foodtown", "Riesbecks"}:
                week_folders = [w for w in campaign_children if w.is_folder]
                week_re = _WEEK_RE if brand.name == "Foodtown" else _RIESBECKS_WEEK_RE
                if any(week_re.match(w.name) for w in week_folders):
                    _record_folder(ctx, campaign_rel, child.id, campaign_children)
                    for week in sorted(week_folders, key=lambda f: f.name):
                        if week_re.match(week.name):
                            week_rel = campaign_rel + (week.name,)
                            week_children = client.list_children(week.id)
                            _download_folder_files(client, ctx, week_rel, week.id, week_children)
                    continue

            _download_folder_files(client, ctx, campaign_rel, child.id, campaign_children)

    _sync_month_changed_dirs(ctx)
    log.info("Drive scan found %s changed processing folder(s)", len(ctx.changed_dirs))
    return ctx


def _upload_changed_files(
    client: DriveClient,
    ctx: SyncContext,
    roots: Iterable[Path] | None = None,
    include_state: bool = True,
) -> int:
    upload_count = 0
    if roots is None:
        candidates = [p for p in ctx.local_root.rglob("*") if p.is_file()]
    else:
        candidates = []
        for root in roots:
            if not root.exists():
                continue
            if root.is_file():
                candidates.append(root)
            else:
                candidates.extend(p for p in root.rglob("*") if p.is_file())

    if include_state:
        candidates.append(ctx.tmp_root / "usm_category_learned.json")

    for path in candidates:
        if not path.exists() or not _is_output_or_state(path):
            continue

        before = ctx.before_hashes.get(path)
        after = _sha256(path)
        if before == after:
            continue

        if path.parent == ctx.tmp_root:
            rel = tuple()
        else:
            rel = path.parent.relative_to(ctx.local_root).parts

        parent_id = ctx.folder_ids.get(rel)
        if not parent_id:
            log.warning("Cannot upload %s: no Drive folder mapping for %s", path.name, "/".join(rel))
            continue

        existing = ctx.remote_files.get(rel, {}).get(path.name)
        uploaded = client.upload_or_update(path, parent_id, existing)
        ctx.remote_files.setdefault(rel, {})[path.name] = uploaded
        ctx.before_hashes[path] = after
        upload_count += 1
        action = "Updated" if existing else "Uploaded"
        log.info("%s Drive output: %s", action, path.relative_to(ctx.tmp_root))

    return upload_count


def _scan_standard_campaign(campaign_dir: Path) -> None:
    from agent.orchestrator import full_ready, habanero_ready, run_campaign, run_habanero_only

    brand_folder = campaign_dir.parent.name
    key = f"{brand_folder}/{campaign_dir.name}"

    try:
        config = load_config(campaign_dir)
        meta = parse_campaign(brand_folder, campaign_dir.name, config)
    except ValueError as exc:
        log.error("Cannot parse '%s': %s", key, exc)
        return

    has_cs = any(f.name.endswith("_Internal_Raw_File_for_CS.xlsx") for f in campaign_dir.iterdir() if f.is_file())
    has_habanero = any(f.name.startswith("(") and f.suffix.lower() == ".xlsx" for f in campaign_dir.iterdir() if f.is_file())

    if full_ready(campaign_dir) and not has_cs:
        log.info("[%s] Drive files ready — running full pipeline", key)
        run_campaign(campaign_dir, meta)
    elif habanero_ready(campaign_dir) and not has_habanero:
        log.info("[%s] Drive files ready — generating Habanero", key)
        run_habanero_only(campaign_dir, meta)


def _process_local_tree(local_root: Path, on_processed=None, changed_dirs: set[Path] | None = None) -> int:
    upload_count = 0
    from agent.foodtown_orchestrator import is_foodtown_month
    from agent.riesbecks_orchestrator import is_riesbecks_month
    from agent import foodtown_orchestrator, riesbecks_orchestrator

    for brand_dir in sorted(local_root.iterdir()):
        if not brand_dir.is_dir() or brand_dir.name not in BRAND_KEY_MAP:
            continue

        for child in sorted(brand_dir.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            if changed_dirs is not None and child not in changed_dirs:
                continue

            processed_dir = None
            if brand_dir.name == "Foodtown" and is_foodtown_month(child):
                meta = parse_campaign("Foodtown", child.name, load_config(child))
                foodtown_orchestrator.try_advance(child, meta)
                processed_dir = child
            elif brand_dir.name == "Riesbecks" and is_riesbecks_month(child):
                meta = parse_campaign("Riesbecks", child.name, load_config(child))
                riesbecks_orchestrator.try_advance(child, meta)
                processed_dir = child
            elif brand_dir.name not in {"Foodtown", "Riesbecks"}:
                _scan_standard_campaign(child)
                processed_dir = child

            if processed_dir and on_processed:
                uploaded = on_processed(processed_dir)
                upload_count += uploaded
                if uploaded:
                    log.info(
                        "Uploaded/updated %s file(s) after %s",
                        uploaded,
                        processed_dir.relative_to(local_root),
                    )

    return upload_count


def run_once(root_folder_id: str, service=None) -> int:
    service = service or build_drive_service()
    client = DriveClient(service)

    ctx = _sync_drive_to_temp(client, root_folder_id)
    try:
        def upload_processed_folder(processed_dir: Path) -> int:
            return _upload_changed_files(client, ctx, roots=[processed_dir], include_state=True)

        uploaded = _process_local_tree(ctx.local_root, on_processed=upload_processed_folder, changed_dirs=ctx.changed_dirs)
        uploaded += _upload_changed_files(client, ctx, roots=[], include_state=True)
        if ctx.changed_dirs:
            _save_poll_state(client, ctx)
        return uploaded
    finally:
        # Keep temp dirs only when debugging; otherwise remove automatically.
        if os.getenv("DRIVE_WATCHER_KEEP_TEMP") != "1":
            import shutil
            shutil.rmtree(ctx.tmp_root, ignore_errors=True)


def run_polling_loop(root_folder_id: str, interval_seconds: int) -> None:
    service = build_drive_service()
    log.info("Drive poller started. root=%s interval=%ss", root_folder_id, interval_seconds)
    while True:
        try:
            uploaded = run_once(root_folder_id, service=service)
            log.info("Drive poll complete. Uploaded/updated %s file(s).", uploaded)
        except Exception:
            log.exception("Drive poll failed")
        time.sleep(interval_seconds)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the LAM Reporting Google Drive poller")
    parser.add_argument("--root-folder-id", default=os.getenv("DRIVE_ROOT_FOLDER_ID"))
    parser.add_argument("--interval-seconds", type=int, default=int(os.getenv("DRIVE_POLL_INTERVAL_SECONDS", "10")))
    parser.add_argument("--once", action="store_true", help="Run one poll immediately, upload outputs, then exit")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if not args.root_folder_id:
        raise SystemExit("Set DRIVE_ROOT_FOLDER_ID or pass --root-folder-id")

    if args.once:
        uploaded = run_once(args.root_folder_id)
        log.info("Manual Drive poll complete. Uploaded/updated %s file(s).", uploaded)
        return

    run_polling_loop(args.root_folder_id, args.interval_seconds)
