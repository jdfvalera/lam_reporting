import json
import re
from pathlib import Path

BRAND_KEY_MAP = {
    "USM":        "USM",
    "Redners":    "Redner's",
    "McCaffreys": "McCaffrey's",
    "Bottlemart": "Bottlemart",
    "Wrays":      "Wray's",
    "Repco":      "Repco",
    "Detwilers":  "Detwiler's",
    "Foodtown":   "Foodtown",
    "Custom":     "Custom",
}

AU_BRANDS = {"Bottlemart", "Repco"}


def load_config(campaign_dir: Path) -> dict:
    """Load config.json from the campaign folder if it exists."""
    cfg_path = campaign_dir / "config.json"
    if cfg_path.exists():
        with open(cfg_path) as f:
            return json.load(f)
    return {}


def _parse_folder_label(campaign_folder: str) -> tuple[str, str | None, str]:
    """
    Split a campaign folder name into (report_number, campaign_type, habanero_label).

    Numeric-prefix folders (25, 25_Weekly, 25_WX_Weekly):
        report_number  = the leading number  → used in Habanero filename
        campaign_type  = everything after _  → used as Campaign column prefix
        habanero_label = report_number       → "(25) Client dates.xlsx"

    Non-numeric folders (FY26 Period 3 Week 3):
        report_number  = "1"                 → unused effectively
        campaign_type  = full folder name    → used as Campaign column prefix
        habanero_label = full folder name    → "(FY26 Period 3 Week 3) Client dates.xlsx"
    """
    m = re.match(r'^(\d+)(?:_(.+))?$', campaign_folder)
    if m:
        report = m.group(1)
        return report, m.group(2) or None, report
    return "1", campaign_folder, campaign_folder


def parse_campaign(brand_folder: str, campaign_folder: str, config: dict | None = None) -> dict:
    """
    Build campaign metadata from the brand folder name + optional config.json.

    brand_folder    — must match a key in BRAND_KEY_MAP (e.g. "USM", "McCaffreys")
    campaign_folder — any name; leading number parsed as report, rest as campaign type
    config          — dict loaded from config.json, or None

    config.json fields (all optional):
        client        — client name for output filenames (default: brand display name)
        week          — week number integer (required for Redner's)
        report        — overrides parsed report number
        campaign_type — overrides parsed campaign type
    """
    if brand_folder not in BRAND_KEY_MAP:
        known = ", ".join(BRAND_KEY_MAP.keys())
        raise ValueError(
            f"Unknown brand folder '{brand_folder}'. Known: {known}"
        )

    brand  = BRAND_KEY_MAP[brand_folder]
    region = "AU" if brand_folder in AU_BRANDS else "US"

    parsed_report, parsed_campaign_type, parsed_hab_label = _parse_folder_label(campaign_folder)

    cfg             = config or {}
    client          = cfg.get("client", brand)
    report_number   = str(cfg.get("report", parsed_report))
    campaign_type   = cfg.get("campaign_type", parsed_campaign_type)
    habanero_label  = cfg.get("report", None) and str(cfg["report"]) or parsed_hab_label

    # Week number: config > explicit W## in campaign_type > None
    # If campaign_type starts with W{N} (e.g. "W30" or "W30_Weekly"),
    # extract the week and strip that prefix so it doesn't double up in the campaign label.
    week_number = cfg.get("week")
    if week_number is None and campaign_type:
        m = re.match(r'^[Ww](\d+)(?:_(.+))?$', campaign_type)
        if m:
            week_number   = int(m.group(1))
            campaign_type = m.group(2)  # None if just "W30", "Weekly" if "W30_Weekly"

    return {
        "client":          client,
        "brand_key":       brand_folder,
        "brand":           brand,
        "week_number":     week_number,
        "campaign_type":   campaign_type,
        "report_number":   report_number,
        "habanero_label":  habanero_label,
        "region":          region,
    }
