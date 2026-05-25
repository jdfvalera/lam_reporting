import re

import pandas as pd


_CAMPAIGN_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")
_DV360_SUFFIX_RE    = re.compile(r"_DV360\s*$", re.IGNORECASE)
_CLICK_TAG_RE       = re.compile(r"^Click Tag \d+$")
_SIZE_PREFIX_RE     = re.compile(r"^(\S+)")


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


def _normalize_ft_campaign(campaign_str):
    """Strip both (FT_CPC) style suffixes and _DV360 suffix."""
    s = _normalize_campaign(campaign_str)
    if isinstance(s, str):
        s = _DV360_SUFFIX_RE.sub("", s).strip()
    return s


def _week_label(date, week_num: int) -> str:
    """Return 'W18_May 4 - 10' (Mon–Sun range) for a given date."""
    monday = date - pd.Timedelta(days=date.weekday())
    sunday = monday + pd.Timedelta(days=6)
    if monday.month == sunday.month:
        date_range = f"{monday.strftime('%b')} {monday.day} - {sunday.day}"
    else:
        date_range = f"{monday.strftime('%b')} {monday.day} - {sunday.strftime('%b')} {sunday.day}"
    return f"W{week_num}_{date_range}"


# ── FT data builder ────────────────────────────────────────────────────────────

_FT_COLUMNS = [
    "Date", "Week", "Campaign", "Banner", "Store Name",
    "Location", "Ad Size", "Product Name", "Clicks",
]


def _build_guide_map(guide_df: pd.DataFrame) -> dict:
    """Build {(banner, ad_size): {click_tag_col: product_name}} from Sheet2."""
    click_cols = [c for c in guide_df.columns if _CLICK_TAG_RE.match(str(c))]
    guide_map: dict = {}
    for _, row in guide_df.iterrows():
        banner_raw = str(row.get("Banner", ""))
        banner = "3DS" if "3d" in banner_raw.lower() else "Regular"
        size_raw = str(row.get("Sizes", ""))
        m = _SIZE_PREFIX_RE.match(size_raw)
        if not m:
            continue
        size = m.group(1)
        products = {
            col: str(row[col]).strip()
            for col in click_cols
            if pd.notna(row.get(col)) and str(row.get(col, "")).strip()
        }
        guide_map[(banner, size)] = products
    return guide_map


def build_ft_data_from_file(
    ft_df: pd.DataFrame, guide_df: pd.DataFrame, week_num: int
) -> pd.DataFrame:
    """Transform a wide-format Riesbecks FT file into ft_data rows."""
    df = ft_df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    click_cols = [c for c in df.columns if _CLICK_TAG_RE.match(str(c))]
    guide_map  = _build_guide_map(guide_df)

    df["Banner"] = df["Campaign"].apply(
        lambda c: "3DS" if isinstance(c, str) and re.search(r"3ds", c, re.IGNORECASE) else "Regular"
    )
    df["Location"] = df["Placement"].apply(
        lambda p: p.split("_")[1] if isinstance(p, str) and len(p.split("_")) >= 2 else None
    )
    df["Store Name"] = df["Version"]
    df["Campaign"]   = df["Campaign"].apply(_normalize_ft_campaign)

    id_vars = ["Date", "Campaign", "Banner", "Ad Size", "Location", "Store Name"]
    melted  = df.melt(
        id_vars=id_vars, value_vars=click_cols,
        var_name="_click_col", value_name="Clicks",
    )
    melted = melted[melted["Clicks"] > 0].copy()

    melted["Product Name"] = melted.apply(
        lambda row: guide_map.get((row["Banner"], row["Ad Size"]), {}).get(row["_click_col"]),
        axis=1,
    )
    melted["Week"] = melted["Date"].apply(lambda d: _week_label(d, week_num))
    melted["Date"] = melted["Date"].dt.strftime("%Y/%m/%d")

    return melted[_FT_COLUMNS].copy()


# ── DV360 data builder ─────────────────────────────────────────────────────────

def build_dv360_from_hab(
    hab_df: pd.DataFrame, banner: str, region: str, week_num: int
) -> pd.DataFrame:
    """Build Riesbecks dv360_data rows from a habanero DataFrame."""
    df = hab_df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    if region == "US":
        df["Date"] = df["Date"] - pd.Timedelta(days=1)

    if "Click Rate (CTR)" in df.columns:
        df["Click Rate (CTR)"] = df["Click Rate (CTR)"].apply(
            lambda v: f"{float(v) * 100:.2f}%" if pd.notna(v) else v
        )

    parsed_io     = df["Insertion Order"].apply(_parse_insertion_order)
    parsed_li     = df["Line Item"].apply(_parse_line_item)
    campaign_orig = df["Campaign"]
    campaigns     = campaign_orig.apply(_normalize_campaign)
    week_labels   = df["Date"].apply(lambda d: _week_label(d, week_num))

    return pd.DataFrame({
        "Date":               df["Date"].dt.strftime("%Y/%m/%d"),
        "Week":               week_labels,
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
    })
