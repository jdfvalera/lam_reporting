import logging
from io import BytesIO
from pathlib import Path

import pandas as pd

from habanero.generator import generate_habanero_report
from reporting.ft_builder import build_ft_data
from reporting.dv360_builder import build_dv360_data
from processors import usm, redners, mccaffreys, bottlemart, wrays, repco, detwilers, foodtown
from processors.base import generic_process
from agent.categorizer import auto_categorize

log = logging.getLogger(__name__)


def _is_output_file(name: str) -> bool:
    """Skip files this agent already wrote into the folder."""
    return name.startswith("(") or name.endswith("_Internal_Raw_File_for_CS.xlsx")


def _is_ft_file(name_lower: str) -> bool:
    """Match FT filenames: ft.xlsx, *FTData*, 'Wray's FT File', etc."""
    import re
    return bool(re.search(r"(^ft\b|[_ ]ft[_ .]|ftdata|ft_data)", name_lower))


def find_campaign_files(folder: Path) -> dict[str, Path | None]:
    """
    Detect which xlsx file is which regardless of filename.
    Output files written by this agent (Habanero, CS raw) are excluded.

    Matching priority (case-insensitive filename):
      weekly    — contains "weekly"
      frequency — contains "frequency" or "freq"
      gs        — named gs.xlsx, or contains "gs_product" / "product_clicks"
      ft        — FTData, "FT File", ft.xlsx, or any remaining xlsx
    """
    xlsx = [
        f for f in folder.iterdir()
        if f.suffix.lower() == ".xlsx"
        and not f.name.startswith("~")
        and not _is_output_file(f.name)
    ]
    result: dict[str, Path | None] = {"weekly": None, "frequency": None, "ft": None, "gs": None}
    unmatched = []

    for f in xlsx:
        n = f.name.lower()
        if "weekly" in n:
            result["weekly"] = f
        elif "frequency" in n or "freq" in n:
            result["frequency"] = f
        elif n == "gs.xlsx" or "gs_product" in n or "product_clicks" in n or "product clicks" in n:
            result["gs"] = f
        elif _is_ft_file(n):
            result["ft"] = f
        else:
            unmatched.append(f)

    for f in unmatched:
        if result["ft"] is None:
            result["ft"] = f

    return result


def habanero_ready(folder: Path) -> bool:
    f = find_campaign_files(folder)
    return f["weekly"] is not None and f["frequency"] is not None


def full_ready(folder: Path) -> bool:
    f = find_campaign_files(folder)
    has_habanero = f["weekly"] is not None and f["frequency"] is not None
    has_clicks   = f["ft"] is not None or f["gs"] is not None  # GS alone is enough for Redner's
    return has_habanero and has_clicks


PROCESSORS = {
    "USM":         usm,
    "Redner's":    redners,
    "McCaffrey's": mccaffreys,
    "Bottlemart":  bottlemart,
    "Wray's":      wrays,
    "Repco":       repco,
    "Detwiler's":  detwilers,
    "Foodtown":    foodtown,
}


def run_habanero_only(folder_path: Path, meta: dict, output_root: Path) -> None:
    """Generate and write only the Habanero report (weekly + frequency files only)."""
    client        = meta["client"]
    report_number = meta["report_number"]
    region        = meta["region"]

    tag            = folder_path.name
    habanero_label = meta["habanero_label"]
    files          = find_campaign_files(folder_path)
    log.info(f"[{tag}] Generating Habanero report (FT not yet available)...")
    log.info(f"[{tag}]   weekly    → {files['weekly'].name}")
    log.info(f"[{tag}]   frequency → {files['frequency'].name}")

    _, hab_buffer, hab_filename = generate_habanero_report(
        files["weekly"], files["frequency"], client, report_number, region,
        label=habanero_label,
    )

    (folder_path / hab_filename).write_bytes(hab_buffer.getvalue())
    log.info(f"[{tag}] Habanero ready → {folder_path / hab_filename}")


def run_campaign(folder_path: Path, meta: dict, output_root: Path) -> None:
    client        = meta["client"]
    brand         = meta["brand"]
    week_number   = meta["week_number"]
    campaign_type = meta.get("campaign_type")
    report_number = meta["report_number"]
    region        = meta["region"]

    tag            = folder_path.name
    habanero_label = meta["habanero_label"]
    files          = find_campaign_files(folder_path)
    log.info(f"[{tag}] Starting — client={client!r}, brand={brand!r}, region={region}")
    log.info(f"[{tag}]   weekly    → {files['weekly'].name}")
    log.info(f"[{tag}]   frequency → {files['frequency'].name}")
    if files["ft"]:
        log.info(f"[{tag}]   ft        → {files['ft'].name}")
    if files["gs"]:
        log.info(f"[{tag}]   gs        → {files['gs'].name}")

    weekly_file    = files["weekly"]
    frequency_file = files["frequency"]
    ft_file        = files["ft"]
    gs_file        = files["gs"]

    # ── Habanero ──────────────────────────────────────────────────────────────
    log.info(f"[{tag}] Generating Habanero report...")
    habanero_df, hab_buffer, hab_filename = generate_habanero_report(
        weekly_file, frequency_file, client, report_number, region,
        label=habanero_label,
    )
    log.info(f"[{tag}] Habanero → {hab_filename}")

    # ── Product clicks ────────────────────────────────────────────────────────
    processor   = PROCESSORS.get(brand)
    long_df     = pd.DataFrame()
    unmapped_df = pd.DataFrame()

    if brand == "Redner's":
        ft_long, gs_long     = None, None
        ft_unmapped          = pd.DataFrame()
        gs_unmapped          = pd.DataFrame()

        if ft_file is not None:
            xls      = pd.ExcelFile(ft_file)
            wide_df  = pd.read_excel(xls, sheet_name=0)
            guide_df = pd.read_excel(xls, sheet_name=1) if len(xls.sheet_names) > 1 else None
            result   = redners.process(wide_df, guide_df)
            if isinstance(result, tuple):
                ft_long, ft_unmapped = result
            else:
                ft_long = result

        if gs_file is not None:
            gs_xls     = pd.ExcelFile(gs_file)
            data_df    = redners.read_gs_data_sheet(gs_xls)
            product_df = pd.read_excel(gs_xls, sheet_name="Sheet1")
            gs_long, gs_unmapped = redners.process_gs(data_df, product_df)

        parts    = [p for p in [ft_long, gs_long] if p is not None and not p.empty]
        long_df  = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

        u_parts      = [p for p in [ft_unmapped, gs_unmapped] if not p.empty]
        unmapped_df  = pd.concat(u_parts, ignore_index=True) if u_parts else pd.DataFrame()

    else:
        xls      = pd.ExcelFile(ft_file)
        wide_df  = pd.read_excel(xls, sheet_name=0)
        guide_df = pd.read_excel(xls, sheet_name=1) if len(xls.sheet_names) > 1 else None

        result = processor.process(wide_df, guide_df) if processor else generic_process(wide_df, guide_df)
        if isinstance(result, tuple):
            long_df, unmapped_df = result
        else:
            long_df = result

    # ── USM auto-categorization ───────────────────────────────────────────────
    if brand == "USM" and usm.needs_manual_categorization(long_df):
        product_names = long_df["Product"].dropna().unique().tolist()
        log.info(f"[{tag}] Auto-categorizing {len(product_names)} USM products via Claude...")
        category_map = auto_categorize(product_names)
        long_df = usm.apply_category_map(long_df, category_map)

    # ── Unmapped summary ──────────────────────────────────────────────────────
    if not unmapped_df.empty:
        dropped = int(unmapped_df["Clicks"].sum()) if "Clicks" in unmapped_df.columns else "?"
        log.warning(f"[{tag}] {dropped} click(s) dropped — unmapped click tags.")

    # ── build_final_export ────────────────────────────────────────────────────
    if processor:
        final_clicks = processor.build_final_export(
            long_df, week_number=week_number, campaign_type=campaign_type
        )
    else:
        final_clicks = long_df

    # ── ft_data / dv360_data ──────────────────────────────────────────────────
    # Note: ft_builder and dv360_builder use `client` param as the brand name
    # for schema selection (naming inconsistency in legacy code, preserved here)
    ft_data, campaign_name = build_ft_data(
        final_clicks, week_number, campaign_type,
        client=brand, exclude_frames=(brand != "Redner's"),
    )

    dv360_data = build_dv360_data(
        habanero_df, campaign_name, region,
        client=brand, week_number=week_number,
    )

    # ── Write outputs into the same folder as the input files ─────────────────
    (folder_path / hab_filename).write_bytes(hab_buffer.getvalue())
    log.info(f"[{tag}] Wrote: {hab_filename}")

    cs_buffer = BytesIO()
    with pd.ExcelWriter(cs_buffer, engine="openpyxl") as writer:
        ft_data.to_excel(writer, sheet_name="ft_data", index=False)
        if isinstance(dv360_data, dict):
            for sheet_name, sheet_df in dv360_data.items():
                sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)
        else:
            dv360_data.to_excel(writer, sheet_name="dv360_data", index=False)

    cs_filename = f"{client}_Internal_Raw_File_for_CS.xlsx"
    (folder_path / cs_filename).write_bytes(cs_buffer.getvalue())
    log.info(f"[{tag}] Wrote: {cs_filename}")

    log.info(f"[{tag}] Done → {folder_path}")
