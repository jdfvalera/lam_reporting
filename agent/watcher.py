import logging
import re
import threading
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from agent.folder_parser import parse_campaign, load_config, BRAND_KEY_MAP
from agent.orchestrator import habanero_ready, full_ready
from agent import orchestrator
from agent import foodtown_orchestrator
from agent.foodtown_orchestrator import is_foodtown_month
from agent import riesbecks_orchestrator
from agent.riesbecks_orchestrator import is_riesbecks_month

log = logging.getLogger(__name__)

_WEEK_RE = re.compile(r'^[Ww]\d+$')
_RIESBECKS_WEEK_RE = re.compile(r'^(?:[Ww])?\d+$')


def _campaign_key(campaign_dir: Path) -> str:
    return f"{campaign_dir.parent.name}/{campaign_dir.name}"


def _month_key(month_dir: Path) -> str:
    return f"Foodtown/{month_dir.name}"


class InboxHandler(FileSystemEventHandler):
    """
    Watches inbox/{Brand}/{Campaign}/ for standard brands.
    Watches inbox/Foodtown/{Month}/{Week}/ for Foodtown multi-week campaigns.

    Standard brands — two stages:
        Stage 1: weekly + frequency → Habanero report
        Stage 2: + FT/GS file      → full CS pipeline

    Foodtown — state-machine driven via .foodtown_state.json:
        Per-week Habanero → Bi-weekly CS → Monthly CS
    """

    def __init__(self, inbox: Path) -> None:
        super().__init__()
        self.inbox    = inbox
        self._hab_done:  set[str] = set()
        self._full_done: set[str] = set()
        self._ft_running: set[str] = set()
        self._ft_snapshot: dict[str, frozenset] = {}  # month_key → input files at last run
        self._lock = threading.Lock()

    def _foodtown_input_snapshot(self, month_dir: Path) -> frozenset:
        """Collect names of all non-output files across week subfolders."""
        files = set()
        for child in month_dir.iterdir():
            if child.is_dir() and re.match(r'[Ww]\d+', child.name):
                for f in child.iterdir():
                    name = f.name
                    if not (name.startswith("(")
                            or name.endswith("_Internal_Raw_File_for_CS.xlsx")
                            or name.startswith(".")):
                        files.add(f"{child.name}/{name}")
        return frozenset(files)

    # ── Standard brand processing ─────────────────────────────────────────────

    def _try_process(self, campaign_dir: Path) -> None:
        if campaign_dir.parent.parent != self.inbox:
            return
        if not campaign_dir.is_dir() or campaign_dir.name.startswith("."):
            return

        brand_folder = campaign_dir.parent.name
        if brand_folder not in BRAND_KEY_MAP:
            return

        # Foodtown month folders are handled separately
        if brand_folder == "Foodtown" and is_foodtown_month(campaign_dir):
            self._try_foodtown(campaign_dir)
            return

        # Riesbecks month folders are handled separately
        if brand_folder == "Riesbecks" and is_riesbecks_month(campaign_dir):
            self._try_riesbecks(campaign_dir)
            return

        key      = _campaign_key(campaign_dir)
        run_hab  = False
        run_full = False

        # Check disk: if expected outputs already exist, mark done and skip
        has_cs       = any(f.name.endswith("_Internal_Raw_File_for_CS.xlsx")
                           for f in campaign_dir.iterdir() if f.is_file())
        has_habanero = any(f.name.startswith("(") and f.suffix.lower() == ".xlsx"
                           for f in campaign_dir.iterdir() if f.is_file())

        with self._lock:
            if has_cs:
                self._full_done.add(key)
                self._hab_done.add(key)
            elif has_habanero:
                self._hab_done.add(key)

            if full_ready(campaign_dir) and key not in self._full_done:
                self._full_done.add(key)
                self._hab_done.add(key)
                run_full = True
            elif habanero_ready(campaign_dir) and key not in self._hab_done:
                self._hab_done.add(key)
                run_hab = True

        if not run_hab and not run_full:
            return

        try:
            config = load_config(campaign_dir)
            meta   = parse_campaign(brand_folder, campaign_dir.name, config)
        except ValueError as exc:
            log.error(f"Cannot parse '{key}': {exc}")
            with self._lock:
                self._hab_done.discard(key)
                self._full_done.discard(key)
            return

        if run_full:
            log.info(f"[{key}] FT file detected — running full pipeline...")
            try:
                orchestrator.run_campaign(campaign_dir, meta)
            except Exception:
                log.exception(f"Full pipeline failed for {key}")
                with self._lock:
                    self._full_done.discard(key)

        elif run_hab:
            log.info(f"[{key}] Weekly + Frequency detected — generating Habanero...")
            try:
                orchestrator.run_habanero_only(campaign_dir, meta)
            except Exception:
                log.exception(f"Habanero generation failed for {key}")
                with self._lock:
                    self._hab_done.discard(key)

    # ── Foodtown multi-week processing ────────────────────────────────────────

    def _try_foodtown(self, month_dir: Path) -> None:
        key      = _month_key(month_dir)
        snapshot = self._foodtown_input_snapshot(month_dir)

        with self._lock:
            if key in self._ft_running:
                return
            if snapshot == self._ft_snapshot.get(key):
                return  # No new input files since last run — skip
            self._ft_running.add(key)
            self._ft_snapshot[key] = snapshot

        try:
            config = load_config(month_dir)
            meta   = parse_campaign("Foodtown", month_dir.name, config)
            foodtown_orchestrator.try_advance(month_dir, meta)
        except Exception:
            log.exception(f"Foodtown processing failed for {month_dir.name}")
        finally:
            with self._lock:
                self._ft_running.discard(key)

    # ── Riesbecks multi-week processing ──────────────────────────────────────

    def _try_riesbecks(self, month_dir: Path) -> None:
        key      = f"Riesbecks/{month_dir.name}"
        snapshot = self._foodtown_input_snapshot(month_dir)

        with self._lock:
            if key in self._ft_running:
                return
            if snapshot == self._ft_snapshot.get(key):
                return
            self._ft_running.add(key)
            self._ft_snapshot[key] = snapshot

        try:
            config = load_config(month_dir)
            meta   = parse_campaign("Riesbecks", month_dir.name, config)
            riesbecks_orchestrator.try_advance(month_dir, meta)
        except Exception:
            log.exception(f"Riesbecks processing failed for {month_dir.name}")
        finally:
            with self._lock:
                self._ft_running.discard(key)

    # ── watchdog callbacks ────────────────────────────────────────────────────

    def _dispatch(self, path: Path) -> None:
        """Route a file event to the correct handler based on depth."""
        # Standard: inbox/{Brand}/{Campaign}/file  (parent is 2 levels from inbox)
        if path.parent.parent.parent == self.inbox:
            self._try_process(path.parent)

        # Foodtown: inbox/Foodtown/{Month}/{Week}/file  (parent is 3 levels from inbox)
        elif path.parent.parent.parent.parent == self.inbox:
            brand_dir = path.parent.parent.parent
            week_dir  = path.parent
            month_dir = path.parent.parent
            name = path.name
            is_output = (
                name.startswith("(")
                or name.endswith("_Internal_Raw_File_for_CS.xlsx")
                or name.startswith(".")
            )
            if brand_dir.name == "Foodtown" and _WEEK_RE.match(week_dir.name) and not is_output:
                self._try_foodtown(month_dir)
            elif brand_dir.name == "Riesbecks" and _RIESBECKS_WEEK_RE.match(week_dir.name) and not is_output:
                self._try_riesbecks(month_dir)

    def on_created(self, event):
        path = Path(event.src_path)
        if event.is_directory:
            # macOS sometimes emits DirCreated instead of DirMoved for renames
            if path.parent.parent == self.inbox:
                self._try_process(path)
                if path.parent.name == "Foodtown":
                    self._try_foodtown(path)
                elif path.parent.name == "Riesbecks":
                    self._try_riesbecks(path)
            elif path.parent.parent.parent == self.inbox and path.parent.parent.name == "Foodtown":
                self._try_foodtown(path.parent)
            elif path.parent.parent.parent == self.inbox and path.parent.parent.name == "Riesbecks":
                self._try_riesbecks(path.parent)
        else:
            self._dispatch(path)

    def on_modified(self, event):
        if not event.is_directory:
            self._dispatch(Path(event.src_path))

    def on_moved(self, event):
        dest = Path(event.dest_path)
        if event.is_directory:
            if dest.parent.parent == self.inbox:
                # Standard campaign folder renamed: inbox/{Brand}/{Campaign}/
                self._try_process(dest)
                if dest.parent.name == "Foodtown":
                    self._try_foodtown(dest)
                elif dest.parent.name == "Riesbecks":
                    self._try_riesbecks(dest)
            elif dest.parent.parent.parent == self.inbox and dest.parent.parent.name == "Foodtown":
                self._try_foodtown(dest.parent)
            elif dest.parent.parent.parent == self.inbox and dest.parent.parent.name == "Riesbecks":
                self._try_riesbecks(dest.parent)
        else:
            self._dispatch(dest)


def _scan_existing(inbox: Path, handler: InboxHandler) -> None:
    for brand_dir in sorted(inbox.iterdir()):
        if not brand_dir.is_dir() or brand_dir.name.startswith("."):
            continue
        if brand_dir.name not in BRAND_KEY_MAP:
            continue

        for child in sorted(brand_dir.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            if brand_dir.name == "Foodtown" and is_foodtown_month(child):
                handler._try_foodtown(child)
            elif brand_dir.name == "Riesbecks" and is_riesbecks_month(child):
                handler._try_riesbecks(child)
            else:
                handler._try_process(child)


def start_watcher(inbox: Path) -> Observer:
    handler = InboxHandler(inbox)
    _scan_existing(inbox, handler)

    observer = Observer()
    observer.schedule(handler, str(inbox), recursive=True)
    observer.start()
    log.info("Watchdog observer started.")
    return observer
