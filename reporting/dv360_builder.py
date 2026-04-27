import pandas as pd
import re


# --------------------------------------------------
# USM helpers
# --------------------------------------------------
_BRAND_MAP = {
    "ALB": "Albertsons",
    "MS":  "Market Street",
    "USM": "United Supermarkets",
}


def _parse_insertion_order(io_str):
    """'ALB_665_Carlsbad, NM' → (brand, store_no, area)"""
    if not isinstance(io_str, str):
        return None, None, None

    parts = io_str.split("_", 2)
    if len(parts) < 3:
        return None, None, None

    prefix    = parts[0].strip().upper()
    store_no  = parts[1].strip()
    area_raw  = parts[2].strip()

    brand = _BRAND_MAP.get(prefix)
    # Strip state code: "Carlsbad, NM" → "Carlsbad"
    area = re.sub(r",\s*[A-Z]{2}$", "", area_raw).strip()

    return brand, store_no, area


def _parse_gender(line_item):
    if isinstance(line_item, str):
        s = line_item.strip()
        if s.startswith("F"):
            return "Females"
        else:
            return "Males"
    return "Unknown"


def _fmt_ctr(impressions, clicks):
    """Return 'x.xx%' string, safe against divide-by-zero."""
    if impressions > 0:
        return f"{clicks / impressions * 100:.2f}%"
    return "0.00%"


def _agg(df, group_cols):
    g = df.groupby(group_cols, sort=False).agg(
        Impressions=("Impressions", "sum"),
        Clicks=("Clicks", "sum"),
    ).reset_index()
    g["CTR"] = g.apply(lambda r: _fmt_ctr(r["Impressions"], r["Clicks"]), axis=1)
    return g


def _campaign_label(df):
    start = df["Date"].min()
    end   = df["Date"].max()
    if start.month == end.month:
        return f"{start.strftime('%b')} {start.day} - {end.day}"
    return f"{start.strftime('%b')} {start.day} - {end.strftime('%b')} {end.day}"


# --------------------------------------------------
# USM multi-table builder
# --------------------------------------------------
def _build_usm_dv360(df):

    # Parse Insertion Order
    parsed         = df["Insertion Order"].apply(_parse_insertion_order)
    df["Brand"]    = parsed.apply(lambda x: x[0])
    df["Store No."]= parsed.apply(lambda x: x[1])
    df["Area"]     = parsed.apply(lambda x: x[2])
    df["Gender"]   = df["Line Item"].apply(_parse_gender)

    label = _campaign_label(df)

    # --- Table 1: Daily summary ---
    t1 = _agg(df, ["Date"])
    t1.columns = ["Date (adjusted)", "Impressions", "Clicks", "CTR (%)"]
    t1["Date (adjusted)"] = t1["Date (adjusted)"].dt.strftime("%Y/%m/%d")

    # --- Table 2: Gender breakdown ---
    t2 = _agg(df, ["Gender"])
    t2.columns = ["", "Impressions", "Clicks", "CTR"]

    # --- Table 3: Ad Size breakdown (sorted by Impressions desc) ---
    t3 = _agg(df, ["Creative Size"])
    t3 = t3.sort_values("Impressions", ascending=False).reset_index(drop=True)
    t3.columns = ["Ad Size", "Impressions", "Clicks", "CTR"]

    # --- Table 4: Store detail by date ---
    t4 = _agg(df, ["Date", "Brand", "Store No.", "Area"])
    t4.columns = ["Date", "Brand", "Store No.", "Area", "Impressions", "Clicks", "Click Rate (CTR)"]
    t4["Date"] = t4["Date"].dt.strftime("%Y/%m/%d")

    # --- Table 6: Daily by Ad Size ---
    t6 = _agg(df, ["Date", "Creative Size"])
    t6.columns = ["Date", "Creative Size", "Impressions", "Clicks", "Click Rate (CTR)"]
    t6["Date"] = t6["Date"].dt.strftime("%Y/%m/%d")

    # --- Table 7: Area totals (campaign period) ---
    t7 = _agg(df, ["Area"])
    t7.insert(0, "Date", label)
    t7.columns = ["Date", "Area", "Impressions", "Clicks", "Click Rate (CTR)"]

    # --- Table 8: Brand + Area totals (campaign period) ---
    t8 = _agg(df, ["Brand", "Area"])
    t8.insert(0, "Date", label)
    t8.columns = ["Date", "Brand", "Area", "Impressions", "Clicks", "Click Rate (CTR)"]

    # --- Table 9: Store + Demographics (campaign period) ---
    t9 = _agg(df, ["Store No.", "Area", "Line Item"])
    t9.insert(0, "Date", label)
    t9.columns = ["Date", "Store No.", "Area", "Demographics", "Impressions", "Clicks", "CTR (%)"]

    return {
        "1_Daily Summary":      t1,
        "2_Gender":             t2,
        "3_Ad Size":            t3,
        "4_Store Detail":       t4,
        "6_Daily by Ad Size":   t6,
        "7_Area Totals":        t7,
        "8_Brand Area Totals":  t8,
        "9_Store Demographics": t9,
    }


# --------------------------------------------------
# Redner's multi-table builder
# --------------------------------------------------
def _parse_redners_io(io_str):
    """'VERSION_STATE_Location City' → (version, state, location)"""
    if not isinstance(io_str, str):
        return None, None, None
    parts = io_str.split("_", 2)
    version  = parts[0].strip() if len(parts) > 0 else None
    state    = parts[1].strip() if len(parts) > 1 else None
    location = parts[2].strip() if len(parts) > 2 else None
    return version, state, location


def _build_redners_dv360(df, week_number):
    parsed          = df["Insertion Order"].apply(_parse_redners_io)
    df["Version"]   = parsed.apply(lambda x: x[0])
    df["State"]     = parsed.apply(lambda x: x[1])
    df["Location"]  = parsed.apply(lambda x: x[2])

    start = df["Date"].min()
    end   = df["Date"].max()
    if start.month == end.month:
        date_range = f"{start.strftime('%b %-d')} - {end.strftime('%-d')}"
    else:
        date_range = f"{start.strftime('%b %-d')} - {end.strftime('%b %-d')}"
    week_label = f"Week {week_number}: {date_range}"

    return pd.DataFrame({
        "Date":             df["Date"].dt.strftime("%Y/%m/%d"),
        "Week":             week_label,
        "Version":          df["Version"],
        "State":            df["State"],
        "Location":         df["Location"],
        "Demographics":     df["Line Item"],
        "Creative Size":    df["Creative Size"],
        "Device Type":      df["Device Type"],
        "Impressions":      df["Impressions"],
        "Clicks":           df["Clicks"],
        "Click Rate (CTR)": df["Click Rate (CTR)"],
    })


# --------------------------------------------------
# Bottlemart helpers
# --------------------------------------------------
def _parse_bottlemart_zone(io_str):
    """'Z1_something' → 'Zone 01'"""
    if not isinstance(io_str, str):
        return None
    token = io_str.split("_")[0].strip().upper()
    m = re.match(r"^Z(\d+)$", token)
    if m:
        return f"Zone {int(m.group(1)):02d}"
    return None


def _build_bottlemart_dv360(df, campaign):
    df["Zone"] = df["Insertion Order"].apply(_parse_bottlemart_zone)
    df["Store"] = df["Insertion Order"].astype(str).str.split("_").str[-1]

    return pd.DataFrame({
        "Date":             df["Date"].dt.strftime("%Y/%m/%d"),
        "Campaign":         campaign,
        "Store":            df["Store"],
        "Zone":             df["Zone"],
        "Demographics":     df["Line Item"],
        "Creative Size":    df["Creative Size"],
        "Device Type":      df["Device Type"],
        "Impressions":      df["Impressions"],
        "Clicks":           df["Clicks"],
        "Click Rate (CTR)": df["Click Rate (CTR)"],
    })


# --------------------------------------------------
# Public entry point
# --------------------------------------------------
def build_dv360_data(habanero_df, campaign, region, client=None, week_number=None):

    df = habanero_df.copy()

    if region == "US":
        df["Date"] = df["Date"] - pd.Timedelta(days=1)

    if "Click Rate (CTR)" in df.columns:
        df["Click Rate (CTR)"] = df["Click Rate (CTR)"].apply(
            lambda v: f"{float(v) * 100:.2f}%" if pd.notna(v) else v
        )

    if client == "USM":
        return _build_usm_dv360(df)

    if client == "Redner's":
        return _build_redners_dv360(df, week_number)

    if client == "Bottlemart":
        return _build_bottlemart_dv360(df, campaign)

    # Generic (all other clients)
    df["Store"] = (
        df["Insertion Order"]
        .astype(str)
        .str.split("_")
        .str[-1]
    )

    return pd.DataFrame({
        "Date":             df["Date"].dt.strftime("%Y/%m/%d"),
        "Campaign":         campaign,
        "Store":            df["Store"],
        "Demographics":     df["Line Item"],
        "Creative Size":    df["Creative Size"],
        "Device Type":      df["Device Type"],
        "Impressions":      df["Impressions"],
        "Clicks":           df["Clicks"],
        "Click Rate (CTR)": df["Click Rate (CTR)"],
    })
