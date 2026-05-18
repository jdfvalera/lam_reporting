import json
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

STATE_FILE = ".foodtown_state.json"
_WEEK_RE   = re.compile(r'^[Ww](\d+)$')


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


# ── State management ──────────────────────────────────────────────────────────

def _default_state(week_nums: list[int]) -> dict:
    state: dict = {"monthly_cs": False}
    pairs = _get_pairs(week_nums)
    for pair_num, (odd, even) in enumerate(pairs, 1):
        state[f"W{odd}_habanero"]       = False
        state[f"W{even}_habanero"]      = False
        state[f"biweekly{pair_num}_cs"] = False
    return state


def get_state(month_dir: Path, week_nums: list[int]) -> dict:
    path = month_dir / STATE_FILE
    if path.exists():
        with open(path) as f:
            saved = json.load(f)
        # Merge with default in case new weeks were added
        default = _default_state(week_nums)
        default.update(saved)
        return default
    return _default_state(week_nums)


def save_state(month_dir: Path, state: dict) -> None:
    with open(month_dir / STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


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

def run_biweekly_cs(
    pair_num: int,
    odd_week_num: int,
    even_week_num: int,
    odd_week_dir: Path,
    even_week_dir: Path,
    meta: dict,
) -> None:
    client        = meta["client"]
    campaign_type = meta.get("campaign_type")
    week_number   = meta.get("week_number")
    region        = meta["region"]

    log.info(f"[Foodtown Biweekly{pair_num}] Building CS file (W{odd_week_num}+W{even_week_num})...")

    # Read both week habaneros back from disk and concat
    hab_odd  = _find_habanero_file(odd_week_dir, odd_week_num)
    hab_even = _find_habanero_file(even_week_dir, even_week_num)

    if hab_odd is None or hab_even is None:
        raise FileNotFoundError(
            f"Could not find habanero files for W{odd_week_num} or W{even_week_num}"
        )

    df_odd  = pd.read_excel(hab_odd,  sheet_name="Data")
    df_even = pd.read_excel(hab_even, sheet_name="Data")

    for df in (df_odd, df_even):
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    combined_habanero = pd.concat([df_odd, df_even], ignore_index=True)

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
    if isinstance(result, tuple):
        long_df, _ = result
    else:
        long_df = result

    final_clicks = foodtown.build_final_export(
        long_df, week_number=week_number, campaign_type=campaign_type
    )

    ft_data, campaign_name = build_ft_data(
        final_clicks, week_number, campaign_type,
        client="Foodtown", exclude_frames=True,
    )

    dv360_data = build_dv360_data(
        combined_habanero, campaign_name, region,
        client="Foodtown", week_number=week_number,
    )

    cs_buffer = BytesIO()
    with pd.ExcelWriter(cs_buffer, engine="openpyxl") as writer:
        ft_data.to_excel(writer, sheet_name="ft_data", index=False)
        if isinstance(dv360_data, dict):
            for sheet_name, sheet_df in dv360_data.items():
                sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)
        else:
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
    Check state and advance to the next incomplete stage.
    Safe to call repeatedly — completed steps are skipped via state file.
    """
    week_folders = get_week_folders(month_dir)
    if not week_folders:
        return

    state = get_state(month_dir, list(week_folders.keys()))
    pairs = _get_pairs(sorted(week_folders.keys()))

    if not pairs:
        # Only one week present so far — process habanero if ready
        for week_num, week_dir in week_folders.items():
            key = f"W{week_num}_habanero"
            if key in state and not state[key] and habanero_ready(week_dir):
                run_week_habanero(week_num, week_dir, meta)
                state[key] = True
                save_state(month_dir, state)
        return

    for pair_num, (odd, even) in enumerate(pairs, 1):
        odd_dir  = week_folders.get(odd)
        even_dir = week_folders.get(even)

        # W{odd} Habanero
        odd_hab_key = f"W{odd}_habanero"
        if odd_hab_key in state and not state[odd_hab_key] and odd_dir and habanero_ready(odd_dir):
            run_week_habanero(odd, odd_dir, meta)
            state[odd_hab_key] = True
            save_state(month_dir, state)

        # W{even} Habanero
        even_hab_key = f"W{even}_habanero"
        if even_hab_key in state and not state[even_hab_key] and even_dir and habanero_ready(even_dir):
            run_week_habanero(even, even_dir, meta)
            state[even_hab_key] = True
            save_state(month_dir, state)

        # Biweekly CS
        bi_key = f"biweekly{pair_num}_cs"
        if bi_key in state and not state[bi_key]:
            if state.get(odd_hab_key) and state.get(even_hab_key):
                if even_dir and full_ready(even_dir):
                    run_biweekly_cs(pair_num, odd, even, odd_dir, even_dir, meta)
                    state[bi_key] = True
                    save_state(month_dir, state)

    # Monthly CS — only when ALL biweekly CS files done
    if not state.get("monthly_cs"):
        all_bi_done = all(
            state.get(f"biweekly{i}_cs", False) for i in range(1, len(pairs) + 1)
        )
        if all_bi_done:
            run_monthly_cs(month_dir, week_folders, meta)
            state["monthly_cs"] = True
            save_state(month_dir, state)
