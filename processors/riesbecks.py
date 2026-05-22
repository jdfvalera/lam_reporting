import re

import pandas as pd


_CAMPAIGN_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")


def _parse_insertion_order(io_str):
    """'East_OH_Riesbeck's Barnesville' → (store_area, store_name)"""
    if not isinstance(io_str, str):
        return None, None
    parts = io_str.split("_", 2)
    area  = parts[0].strip() if parts else None
    store = re.sub(r"^Riesbeck.s\s+", "", parts[2]).strip() if len(parts) > 2 else None
    return area, store


def _parse_line_item(li_str):
    """'F 25 - 44' → ('F', '25 - 44')"""
    if not isinstance(li_str, str):
        return None, None
    li  = li_str.strip()
    sex = li[0] if li else None
    age = li[2:].strip() if len(li) > 2 else None
    return sex, age


def _normalize_campaign(campaign_str):
    """'3DS_May 14 - 16 (FT_CPC)' → '3DS_May 14 - 16'"""
    if not isinstance(campaign_str, str):
        return campaign_str
    return _CAMPAIGN_SUFFIX_RE.sub("", campaign_str).strip()


def _week_campaign_label(date) -> str:
    """Return 'Apr 06 - Apr 12' (Mon–Sun range) for a given date."""
    monday = date - pd.Timedelta(days=date.weekday())
    sunday = monday + pd.Timedelta(days=6)
    return f"{monday.strftime('%b %d')} - {sunday.strftime('%b %d')}"


def build_dv360_from_hab(hab_df: pd.DataFrame, banner: str, region: str) -> pd.DataFrame:
    """
    Build Riesbecks dv360_data rows from a habanero DataFrame.

    banner: 'Regular' or '3DS'
    """
    df = hab_df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    if region == "US":
        df["Date"] = df["Date"] - pd.Timedelta(days=1)

    if "Click Rate (CTR)" in df.columns:
        df["Click Rate (CTR)"] = df["Click Rate (CTR)"].apply(
            lambda v: f"{float(v) * 100:.2f}%" if pd.notna(v) else v
        )

    parsed_io   = df["Insertion Order"].apply(_parse_insertion_order)
    parsed_li   = df["Line Item"].apply(_parse_line_item)
    campaign_orig = df["Campaign"]
    campaigns     = campaign_orig.apply(_normalize_campaign)
    week_labels   = df["Date"].apply(_week_campaign_label)

    return pd.DataFrame({
        "Date":               df["Date"].dt.strftime("%Y/%m/%d"),
        "Campaign":           campaigns,
        "Banner":             banner,
        "Store Name":         parsed_io.apply(lambda x: x[1]),
        "Store Area":         parsed_io.apply(lambda x: x[0]),
        "Sex":                parsed_li.apply(lambda x: x[0]),
        "Age":                parsed_li.apply(lambda x: x[1]),
        "Creative Size":      df["Creative Size"],
        "Device Type":        df["Device Type"],
        "Impressions":        df["Impressions"],
        "Clicks":             df["Clicks"],
        "Click Rate (CTR)":   df["Click Rate (CTR)"],
        "Campaign_Original":  campaign_orig,
        "Line Item":          df["Line Item"],
        "Frequency":          df.get("Frequency"),
        "Reach":              df.get("Reach"),
        "Week Campaign":      week_labels,
    })
