import logging
import re
from io import BytesIO
from pathlib import Path

import pandas as pd

from habanero.generator import generate_habanero_report
from reporting.ft_builder import build_ft_data
from reporting.dv360_builder import build_dv360_data
from processors import foodtown
from agent.orchestrator import find_campaign_files, habanero_ready, full_ready

log = logging.getLogger(__name__)

_WEEK_RE = re.compile(r'^[Ww](\d+)$')


# ── Folder helpers ─────────────────────────────────────────────────────────────

def is_foodtown_month(folder: Path) -> bool:
    """True if folder contains W## subdirectories (i.e. it's a month container)."""
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


def _get_pairs(week_nums: list[int]) -> list[tuple[int, int]]:
    """
    Group sorted week numbers into consecutive odd+even pairs.
    [1,2,3,4] → [(1,2),(3,4)]   [5,6,7,8] → [(5,6),(7,8)]
    Incomplete pairs (odd only) are silently skipped until the even arrives.
    """
    sorted_weeks = sorted(week_nums)
    pairs = []
    i = 0
    while i < len(sorted_weeks) - 1:
        odd, even = sorted_weeks[i], sorted_weeks[i + 1]
        if even == odd + 1:
            pairs.append((odd, even))
            i += 2
        else:
            i += 1
    return pairs


# ── Per-week Habanero ─────────────────────────────────────────────────────────

def _find_habanero_file(week_dir: Path, week_num: int) -> Path | None:
    prefix = f"(W{week_num})"
    for f in week_dir.iterdir():
        if f.name.startswith(prefix) and f.suffix.lower() == ".xlsx":
            return f
    return None


def run_week_habanero(week_num: int, week_dir: Path, meta: dict) -> None:
    files = find_campaign_files(week_dir)
    client        = meta["client"]
    report_number = meta["report_number"]
    region        = meta["region"]

    log.info(f"[Foodtown W{week_num}] Generating Habanero...")
    log.info(f"[Foodtown W{week_num}]   weekly    → {files['weekly'].name}")
    log.info(f"[Foodtown W{week_num}]   frequency → {files['frequency'].name}")

    _, hab_buffer, hab_filename = generate_habanero_report(
        files["weekly"], files["frequency"],
        client, report_number, region,
        label=f"W{week_num}",
    )

    (week_dir / hab_filename).write_bytes(hab_buffer.getvalue())
    log.info(f"[Foodtown W{week_num}] Habanero → {hab_filename}")


# ── Bi-weekly CS file ─────────────────────────────────────────────────────────

def _week_date_range(hab_df: pd.DataFrame, region: str) -> str:
    """Build a date range string from a habanero DataFrame, applying region shift."""
    dates = hab_df["Date"].dropna()
    if region == "US":
        dates = dates - pd.Timedelta(days=1)
    start, end = dates.min(), dates.max()
    if start.month == end.month:
        return f"{start.strftime('%b %-d')} - {end.strftime('%-d')}"
    return f"{start.strftime('%b %-d')} - {end.strftime('%b %-d')}"


def _month_label(month_dir: Path) -> str:
    """Extract month number from folder name: 'Month 1' → 'M1', 'Month 2' → 'M2'."""
    m = re.search(r'\d+', month_dir.name)
    return f"M{m.group()}" if m else month_dir.name


def run_biweekly_cs(
    pair_num: int,
    odd_week_num: int,
    even_week_num: int,
    odd_week_dir: Path,
    even_week_dir: Path,
    meta: dict,
) -> None:
    client = meta["client"]
    region = meta["region"]
    month_dir = odd_week_dir.parent

    log.info(f"[Foodtown Biweekly{pair_num}] Building CS file (W{odd_week_num}+W{even_week_num})...")

    # Read both week habaneros back from disk
    hab_odd  = _find_habanero_file(odd_week_dir,  odd_week_num)
    hab_even = _find_habanero_file(even_week_dir, even_week_num)

    if hab_odd is None or hab_even is None:
        raise FileNotFoundError(
            f"Could not find habanero files for W{odd_week_num} or W{even_week_num}"
        )

    df_odd  = pd.read_excel(hab_odd,  sheet_name="Data")
    df_even = pd.read_excel(hab_even, sheet_name="Data")

    for df in (df_odd, df_even):
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Build per-week campaign labels: M1_W1_May 1 - 7, M1_W2_May 8 - 14
    mn          = _month_label(month_dir)
    odd_range   = _week_date_range(df_odd,  region)
    even_range  = _week_date_range(df_even, region)
    odd_label   = f"{mn}_W{odd_week_num}_{odd_range}"
    even_label  = f"{mn}_W{even_week_num}_{even_range}"

    log.info(f"[Foodtown Biweekly{pair_num}]   odd  label → {odd_label}")
    log.info(f"[Foodtown Biweekly{pair_num}]   even label → {even_label}")

    # Process FT file from even week folder
    files = find_campaign_files(even_week_dir)
    ft_file = files["ft"]
    if ft_file is None:
        raise FileNotFoundError(f"No FT file found in {even_week_dir}")

    log.info(f"[Foodtown Biweekly{pair_num}]   ft → {ft_file.name}")

    xls      = pd.ExcelFile(ft_file)
    wide_df  = pd.read_excel(xls, sheet_name=0)
    guide_df = pd.read_excel(xls, sheet_name=1) if len(xls.sheet_names) > 1 else None

    result = foodtown.process(wide_df, guide_df)
    long_df = result[0] if isinstance(result, tuple) else result

    # Split FT rows by Campaign column — more reliable than date-based split
    # because a campaign string can span dates across both weeks.
    # Sort the two unique campaign strings by their earliest date to determine odd vs even.
    long_df["Date"] = pd.to_datetime(long_df["Date"], errors="coerce")
    camp_col = "Campaign" if "Campaign" in long_df.columns else None

    if camp_col and long_df[camp_col].nunique() >= 2:
        camp_order = (
            long_df.groupby(camp_col)["Date"].min()
            .sort_values()
            .index.tolist()
        )
        long_odd  = long_df[long_df[camp_col] == camp_order[0]]
        long_even = long_df[long_df[camp_col] == camp_order[1]]
    else:
        # Fallback: split by date if Campaign column is absent or has only one value
        shift    = pd.Timedelta(days=1) if region == "US" else pd.Timedelta(0)
        odd_end  = df_odd["Date"].max() - shift
        long_odd  = long_df[long_df["Date"] <= odd_end]
        long_even = long_df[long_df["Date"] >  odd_end]

    # Build ft_data per week, override campaign label, then concat
    def _ft_week(subset: pd.DataFrame, label: str) -> pd.DataFrame:
        final = foodtown.build_final_export(subset)
        ft, _ = build_ft_data(final, None, None, client="Foodtown", exclude_frames=True)
        ft["Campaign"] = label
        return ft

    ft_data = pd.concat([_ft_week(long_odd, odd_label), _ft_week(long_even, even_label)],
                        ignore_index=True)

    # Build dv360_data per week with the correct label, then concat
    dv_odd  = build_dv360_data(df_odd,  odd_label,  region, client="Foodtown")
    dv_even = build_dv360_data(df_even, even_label, region, client="Foodtown")
    dv360_data = pd.concat([dv_odd, dv_even], ignore_index=True)

    cs_buffer = BytesIO()
    with pd.ExcelWriter(cs_buffer, engine="openpyxl") as writer:
        ft_data.to_excel(writer,    sheet_name="ft_data",    index=False)
        dv360_data.to_excel(writer, sheet_name="dv360_data", index=False)

    cs_filename = f"{client}_Biweekly{pair_num}_Internal_Raw_File_for_CS.xlsx"
    (even_week_dir / cs_filename).write_bytes(cs_buffer.getvalue())
    log.info(f"[Foodtown Biweekly{pair_num}] Wrote: {cs_filename}")


# ── Monthly CS file ───────────────────────────────────────────────────────────

def _find_biweekly_cs(week_dir: Path, pair_num: int) -> Path | None:
    target = f"Biweekly{pair_num}_Internal_Raw_File_for_CS.xlsx"
    for f in week_dir.iterdir():
        if f.name.endswith(target):
            return f
    return None


def run_monthly_cs(month_dir: Path, week_folders: dict[int, Path], meta: dict) -> None:
    client = meta["client"]
    pairs  = _get_pairs(sorted(week_folders.keys()))

    log.info(f"[Foodtown Monthly] Building monthly CS file...")

    ft_frames  = []
    dv_frames  = []
    dv_is_dict = False

    for pair_num, (_, even) in enumerate(pairs, 1):
        cs_path = _find_biweekly_cs(week_folders[even], pair_num)
        if cs_path is None:
            raise FileNotFoundError(
                f"Biweekly{pair_num} CS file not found in {week_folders[even]}"
            )
        xls = pd.ExcelFile(cs_path)
        ft_frames.append(pd.read_excel(xls, sheet_name="ft_data"))

        # dv360 may be a single sheet or multiple sheets (USM-style dict — not for Foodtown)
        remaining = [s for s in xls.sheet_names if s != "ft_data"]
        if remaining:
            dv_frames.append(pd.read_excel(xls, sheet_name=remaining[0]))

    monthly_ft  = pd.concat(ft_frames,  ignore_index=True) if ft_frames  else pd.DataFrame()
    monthly_dv  = pd.concat(dv_frames,  ignore_index=True) if dv_frames  else pd.DataFrame()

    cs_buffer = BytesIO()
    with pd.ExcelWriter(cs_buffer, engine="openpyxl") as writer:
        monthly_ft.to_excel(writer, sheet_name="ft_data",   index=False)
        monthly_dv.to_excel(writer, sheet_name="dv360_data", index=False)

    cs_filename = f"{client}_Monthly_Internal_Raw_File_for_CS.xlsx"
    (month_dir / cs_filename).write_bytes(cs_buffer.getvalue())
    log.info(f"[Foodtown Monthly] Wrote: {cs_filename}")


# ── Main entry point ──────────────────────────────────────────────────────────

def try_advance(month_dir: Path, meta: dict) -> None:
    """
    Re-runs every stage on each call — no state file.
    Habanero and CS files are overwritten each time the agent restarts.
    Sequencing is enforced by file existence: biweekly CS requires both
    habanero files to exist, monthly CS requires both biweekly CS files.
    """
    week_folders = get_week_folders(month_dir)
    if not week_folders:
        return

    pairs = _get_pairs(sorted(week_folders.keys()))

    for pair_num, (odd, even) in enumerate(pairs, 1):
        odd_dir  = week_folders.get(odd)
        even_dir = week_folders.get(even)

        # W{odd} Habanero
        if odd_dir and habanero_ready(odd_dir):
            run_week_habanero(odd, odd_dir, meta)

        # W{even} Habanero
        if even_dir and habanero_ready(even_dir):
            run_week_habanero(even, even_dir, meta)

        # Biweekly CS — only if both habanero files exist and FT is ready
        odd_hab  = _find_habanero_file(odd_dir,  odd)  if odd_dir  else None
        even_hab = _find_habanero_file(even_dir, even) if even_dir else None
        if odd_hab and even_hab and even_dir and full_ready(even_dir):
            run_biweekly_cs(pair_num, odd, even, odd_dir, even_dir, meta)

    # Monthly CS — only if all biweekly CS files exist on disk
    if len(pairs) == 2:
        bi1 = _find_biweekly_cs(week_folders.get(pairs[0][1]), 1)
        bi2 = _find_biweekly_cs(week_folders.get(pairs[1][1]), 2)
        if bi1 and bi2:
            run_monthly_cs(month_dir, week_folders, meta)
