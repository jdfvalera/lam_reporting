import logging
import re
from io import BytesIO
from pathlib import Path

import pandas as pd

from habanero.generator import generate_habanero_report
from processors import riesbecks

log = logging.getLogger(__name__)

_WEEK_RE        = re.compile(r'^(?:[Ww])?(\d+)$')
_CAMPAIGN_3DS_RE = re.compile(r'^3ds', re.IGNORECASE)
_FT_RE          = re.compile(r'(^ft\b|[_ ]ft[_. ]|ftdata|ft_data|ft file)', re.IGNORECASE)


# ── Folder helpers ─────────────────────────────────────────────────────────────

def is_riesbecks_month(folder: Path) -> bool:
    """True if folder contains W## subdirectories (month container)."""
    return folder.is_dir() and any(
        _WEEK_RE.match(child.name) for child in folder.iterdir() if child.is_dir()
    )


def get_week_folders(month_dir: Path) -> dict[int, Path]:
    """Return {week_num: path} for all W## subfolders present."""
    result = {}
    for child in month_dir.iterdir():
        if child.is_dir():
            m = _WEEK_RE.match(child.name)
            if m:
                result[int(m.group(1))] = child
    return result


# ── Input file detection ───────────────────────────────────────────────────────

def _is_output_file(name: str) -> bool:
    return name.startswith("(") or name.endswith("_Internal_Raw_File_for_CS.xlsx")


def _detect_weekly_banner(path: Path) -> str:
    """Return '3DS' or 'Regular' by peeking at the Campaign column."""
    try:
        df = pd.read_excel(path, sheet_name="Data", nrows=5)
        if "Campaign" in df.columns and len(df) > 0:
            camp = str(df["Campaign"].dropna().iloc[0])
            if _CAMPAIGN_3DS_RE.match(camp):
                return "3DS"
    except Exception:
        pass
    return "Regular"


def _freq_row_count(path: Path) -> int:
    """Count data rows in a frequency xlsx file."""
    try:
        df = pd.read_excel(path, sheet_name="Data")
        return len(df)
    except Exception:
        return 0


def _find_riesbecks_input_pairs(week_dir: Path) -> dict[str, dict]:
    """
    Return {"Regular": {"weekly": path, "frequency": path}, "3DS": {...}}.
    Detects banner from Campaign column in weekly files; pairs frequency files
    by row count (fewer rows = 3DS, more rows = Regular).
    """
    weekly_files = sorted(
        [f for f in week_dir.iterdir()
         if f.suffix.lower() == ".xlsx"
         and "weekly" in f.name.lower()
         and not _is_output_file(f.name)],
        key=lambda f: f.name,
    )
    freq_files = sorted(
        [f for f in week_dir.iterdir()
         if f.suffix.lower() == ".xlsx"
         and "frequency" in f.name.lower()
         and not _is_output_file(f.name)],
        key=lambda f: f.name,
    )

    pairs: dict[str, dict] = {
        "Regular": {"weekly": None, "frequency": None},
        "3DS":     {"weekly": None, "frequency": None},
    }

    for wf in weekly_files:
        banner = _detect_weekly_banner(wf)
        pairs[banner]["weekly"] = wf

    if len(freq_files) == 2:
        by_rows = sorted(freq_files, key=_freq_row_count)
        pairs["3DS"]["frequency"]     = by_rows[0]   # fewer rows = 3DS
        pairs["Regular"]["frequency"] = by_rows[1]
    elif len(freq_files) == 1:
        f = freq_files[0]
        target = "3DS" if pairs["3DS"]["frequency"] is None else "Regular"
        pairs[target]["frequency"] = f

    return pairs


def _has_both_inputs(week_dir: Path) -> bool:
    """True if week dir has ≥2 weekly pull files and ≥2 frequency files."""
    weekly_count = sum(
        1 for f in week_dir.iterdir()
        if f.suffix.lower() == ".xlsx"
        and "weekly" in f.name.lower()
        and not _is_output_file(f.name)
    )
    freq_count = sum(
        1 for f in week_dir.iterdir()
        if f.suffix.lower() == ".xlsx"
        and "frequency" in f.name.lower()
        and not _is_output_file(f.name)
    )
    return weekly_count >= 2 and freq_count >= 2


# ── Habanero output lookup ─────────────────────────────────────────────────────

def _find_habanero_file(week_dir: Path, week_num: int, banner: str) -> Path | None:
    """Find a habanero output file for the given week + banner ('Regular' or '3DS')."""
    prefix = f"(W{week_num} {banner})"
    for f in week_dir.iterdir():
        if f.name.startswith(prefix) and f.suffix.lower() == ".xlsx":
            return f
    return None


def _find_ft_file(week_dir: Path) -> Path | None:
    """Find the single FT data file for a week (contains both banners)."""
    for f in week_dir.iterdir():
        if (f.suffix.lower() == ".xlsx"
                and _FT_RE.search(f.name)
                and not _is_output_file(f.name)
                and not f.name.startswith("~$")):
            return f
    return None


def _find_partial_cs(week_dir: Path, week_num: int) -> Path | None:
    prefix = f"(W{week_num})"
    for f in week_dir.iterdir():
        if f.name.startswith(prefix) and f.name.endswith("_Internal_Raw_File_for_CS.xlsx"):
            return f
    return None


def _find_monthly_cs(month_dir: Path) -> Path | None:
    for f in month_dir.iterdir():
        if f.is_file() and f.name.endswith("Monthly_Internal_Raw_File_for_CS.xlsx"):
            return f
    return None


# ── Per-week Habanero generation ───────────────────────────────────────────────

def run_week_habaneros(week_num: int, week_dir: Path, meta: dict) -> None:
    client        = meta["client"]
    report_number = meta["report_number"]
    region        = meta["region"]

    pairs = _find_riesbecks_input_pairs(week_dir)

    for banner, files in pairs.items():
        weekly_file = files.get("weekly")
        freq_file   = files.get("frequency")

        if weekly_file is None or freq_file is None:
            log.warning(f"[Riesbecks W{week_num}] Missing {banner} input files, skipping")
            continue

        label = f"W{week_num} {banner}"
        log.info(f"[Riesbecks W{week_num}] Generating Habanero for {banner}...")
        log.info(f"[Riesbecks W{week_num}]   weekly    → {weekly_file.name}")
        log.info(f"[Riesbecks W{week_num}]   frequency → {freq_file.name}")

        _, hab_buffer, hab_filename = generate_habanero_report(
            weekly_file, freq_file, client, report_number, region,
            label=label,
        )

        (week_dir / hab_filename).write_bytes(hab_buffer.getvalue())
        log.info(f"[Riesbecks W{week_num}] Habanero → {hab_filename}")


# ── Per-week partial CS generation ────────────────────────────────────────────

def run_partial_cs(week_num: int, week_dir: Path, meta: dict) -> None:
    client = meta["client"]
    region = meta["region"]

    log.info(f"[Riesbecks W{week_num}] Building partial CS file...")

    dv_frames = []
    for banner in ("Regular", "3DS"):
        hab_file = _find_habanero_file(week_dir, week_num, banner)
        df = pd.read_excel(hab_file, sheet_name="Data")
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        dv_frames.append(riesbecks.build_dv360_from_hab(df, banner, region, week_num))

    weekly_dv = pd.concat(dv_frames, ignore_index=True)

    ft_file  = _find_ft_file(week_dir)
    xls      = pd.ExcelFile(ft_file, engine="openpyxl")
    ft_df    = pd.read_excel(xls, sheet_name=0)
    guide_df = pd.read_excel(xls, sheet_name=1) if len(xls.sheet_names) > 1 else pd.DataFrame()
    weekly_ft = riesbecks.build_ft_data_from_file(ft_df, guide_df, week_num)

    cs_buffer = BytesIO()
    with pd.ExcelWriter(cs_buffer, engine="openpyxl") as writer:
        weekly_ft.to_excel(writer, sheet_name="ft_data", index=False)
        weekly_dv.to_excel(writer, sheet_name="dv360_data", index=False)

    cs_filename = f"(W{week_num}) {client}_Internal_Raw_File_for_CS.xlsx"
    (week_dir / cs_filename).write_bytes(cs_buffer.getvalue())
    log.info(f"[Riesbecks W{week_num}] Partial CS → {cs_filename}")


# ── Monthly CS generation ──────────────────────────────────────────────────────

def run_monthly_cs(month_dir: Path, week_folders: dict[int, Path], meta: dict) -> None:
    client = meta["client"]

    log.info("[Riesbecks Monthly] Building monthly CS file...")

    ft_frames = []
    dv_frames = []

    for week_num in sorted(week_folders.keys()):
        partial = _find_partial_cs(week_folders[week_num], week_num)
        log.info(f"[Riesbecks Monthly]   W{week_num} → {partial.name}")
        xls = pd.ExcelFile(partial, engine="openpyxl")
        ft_frames.append(pd.read_excel(xls, sheet_name="ft_data"))
        dv_frames.append(pd.read_excel(xls, sheet_name="dv360_data"))

    cs_buffer = BytesIO()
    with pd.ExcelWriter(cs_buffer, engine="openpyxl") as writer:
        pd.concat(ft_frames, ignore_index=True).to_excel(writer, sheet_name="ft_data",   index=False)
        pd.concat(dv_frames, ignore_index=True).to_excel(writer, sheet_name="dv360_data", index=False)

    cs_filename = f"{client}_Monthly_Internal_Raw_File_for_CS.xlsx"
    (month_dir / cs_filename).write_bytes(cs_buffer.getvalue())
    log.info(f"[Riesbecks Monthly] Wrote: {cs_filename}")


# ── Main entry point ───────────────────────────────────────────────────────────

def try_advance(month_dir: Path, meta: dict) -> None:
    """
    Re-evaluates all stages on every call.
    Habanero files are written per-week; the monthly CS is written once all
    4 week folders each have both banner habaneros.
    Existing outputs are skipped (not overwritten).
    """
    week_folders = get_week_folders(month_dir)
    if not week_folders:
        return

    for week_num in sorted(week_folders.keys()):
        week_dir = week_folders[week_num]

        hab_regular = _find_habanero_file(week_dir, week_num, "Regular")
        hab_3ds     = _find_habanero_file(week_dir, week_num, "3DS")

        if _has_both_inputs(week_dir) and (hab_regular is None or hab_3ds is None):
            run_week_habaneros(week_num, week_dir, meta)
            hab_regular = _find_habanero_file(week_dir, week_num, "Regular")
            hab_3ds     = _find_habanero_file(week_dir, week_num, "3DS")

        if (hab_regular is not None and hab_3ds is not None
                and _find_ft_file(week_dir) is not None
                and _find_partial_cs(week_dir, week_num) is None):
            run_partial_cs(week_num, week_dir, meta)

    # Monthly CS: requires all 4 weeks to have a partial CS
    if len(week_folders) >= 4:
        first_four = dict(list(sorted(week_folders.items()))[:4])
        all_partials_done = all(
            _find_partial_cs(week_folders[n], n) is not None
            for n in sorted(first_four.keys())
        )
        if all_partials_done and _find_monthly_cs(month_dir) is None:
            run_monthly_cs(month_dir, first_four, meta)
