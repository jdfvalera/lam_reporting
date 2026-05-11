import pandas as pd
import re
from .base import default_clicktag_longform


# --------------------------------------------------
# Core processing — FT
# --------------------------------------------------
def process(
    df: pd.DataFrame,
    guide_df: pd.DataFrame | None = None
) -> pd.DataFrame:

    # -------------------------------
    # FT → long-form click tags
    # -------------------------------
    long_df = default_clicktag_longform(df)

    # -------------------------------
    # Rename existing Version → Store
    # -------------------------------
    if "Version" in long_df.columns:
        long_df = long_df.rename(columns={"Version": "Store"})

    # -------------------------------
    # Placement → Version
    # -------------------------------
    def parse_version(val):
        if not isinstance(val, str):
            return None
        return val.split("_", 1)[0].strip().upper()

    long_df["Version"] = long_df["Placement"].apply(parse_version)

    # -------------------------------
    # Version → Guide Version
    # -------------------------------
    def map_to_guide_version(v):
        if v == "S96":
            return "S96"
        return "Others"

    long_df["Guide Version"] = long_df["Version"].apply(map_to_guide_version)

    # -------------------------------
    # Ad Size normalization
    # -------------------------------
    def clean_ad_size(val):
        if not isinstance(val, str):
            return None
        m = re.search(r"\d+\s*x\s*\d+", val)
        return m.group(0).replace(" ", "") if m else None

    long_df["Ad Size"] = long_df["Ad Size"].apply(clean_ad_size)

    # -------------------------------
    # If no guide, return base output
    # -------------------------------
    if guide_df is None:
        return long_df

    # -------------------------------
    # Normalize Click Tag Guide
    # -------------------------------
    guide = guide_df.rename(
        columns={
            "Banner": "Guide Version",
            "Sizes": "Ad Size",
        }
    )

    guide["Guide Version"] = guide["Guide Version"].astype(str).str.strip()
    guide["Ad Size"] = guide["Ad Size"].apply(clean_ad_size)

    click_cols = [
        c for c in guide.columns
        if c.lower().startswith("click tag ")
    ]

    if not click_cols:
        raise ValueError("Click Tag Guide missing Click Tag columns.")

    # -------------------------------
    # Unpivot guide
    # -------------------------------
    guide_long = guide.melt(
        id_vars=["Guide Version", "Ad Size"],
        value_vars=click_cols,
        var_name="Click Tag",
        value_name="Product Name",
    )

    guide_long["Click Tag"] = (
        guide_long["Click Tag"]
        .str.replace("Click Tag ", "", regex=False)
        .astype(int)
    )

    guide_long = guide_long.dropna(subset=["Product Name"])

    # -------------------------------
    # Normalize join keys
    # -------------------------------
    for col in ["Guide Version", "Ad Size"]:
        long_df[col] = long_df[col].astype(str).str.strip()
        guide_long[col] = guide_long[col].astype(str).str.strip()

    # -------------------------------
    # Join FT → guide
    # -------------------------------
    enriched = long_df.merge(
        guide_long,
        on=["Guide Version", "Ad Size", "Click Tag"],
        how="left",
    )

    # -------------------------------
    # Flag unmapped clicks, then drop
    # -------------------------------
    unmapped_df = enriched[enriched["Product Name"].isna()].copy()

    enriched = enriched.dropna(subset=["Product Name"])
    enriched["Product Name"] = enriched["Product Name"].astype(str).str.strip()
    enriched = enriched[enriched["Product Name"] != ""]

    return enriched, unmapped_df


# --------------------------------------------------
# GS file helpers
# --------------------------------------------------
def read_gs_data_sheet(xls: pd.ExcelFile) -> pd.DataFrame:
    """Read the GS 'Data' sheet, auto-detecting the actual header row."""
    raw = pd.read_excel(xls, sheet_name="Data", header=None)
    header_row = None
    for i, row in raw.iterrows():
        if str(row.iloc[0]).strip() == "Date":
            header_row = i
            break
    if header_row is None:
        raise ValueError("Could not find 'Date' header row in GS Data sheet.")
    return pd.read_excel(xls, sheet_name="Data", header=header_row)


# --------------------------------------------------
# Core processing — GS
# --------------------------------------------------
def process_gs(
    data_df: pd.DataFrame,
    product_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Process a Redner's GS Product Clicks file.

    data_df   — the 'Data' sheet read via read_gs_data_sheet()
    product_df — the 'Sheet1' product lookup (Product No., LIST OF PRODUCTS, Store)
    """
    df = data_df.copy()

    # -------------------------------
    # DV360 Insertion Order → Version, Store
    # e.g. "S10_PA_Ephrata" → Version="S10", Store="Ephrata"
    # -------------------------------
    def parse_insertion_order(val):
        if not isinstance(val, str):
            return pd.Series({"Version": None, "Store": None})
        parts = [p.strip() for p in val.split("_")]
        return pd.Series({"Version": parts[0].upper(), "Store": parts[-1]})

    parsed = df["DV360 Insertion Order"].apply(parse_insertion_order)
    df["Version"] = parsed["Version"]
    df["Store"] = parsed["Store"]

    # -------------------------------
    # Rich Media Event → Click Tag
    # e.g. "Exit : Product_1" → "Product_1"
    #      "Exit : end"       → "end"
    #      "Exit : opening"   → "opening"
    # -------------------------------
    df["Click Tag"] = (
        df["Rich Media Event"]
        .astype(str)
        .str.replace(r"^Exit\s*:\s*", "", regex=True)
        .str.strip()
    )

    # -------------------------------
    # Ad Size
    # -------------------------------
    def clean_ad_size(val):
        if not isinstance(val, str):
            return None
        m = re.search(r"\d+\s*x\s*\d+", val)
        return m.group(0).replace(" ", "") if m else None

    df["Ad Size"] = df["Creative Pixel Size"].apply(clean_ad_size)

    # -------------------------------
    # Clicks
    # -------------------------------
    df["Clicks"] = pd.to_numeric(df["Exits"], errors="coerce").fillna(0).astype(int)

    # -------------------------------
    # Date
    # -------------------------------
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])

    # -------------------------------
    # Build product lookup
    # {(product_no: int, store_key: "Dundalk"|"Others"): product_name}
    # -------------------------------
    product_lookup: dict[tuple[int, str], str] = {}
    for _, row in product_df.iterrows():
        try:
            no = int(row["Product No."])
        except (ValueError, TypeError):
            continue
        store_key = str(row["Store"]).strip()
        product_lookup[(no, store_key)] = str(row["LIST OF PRODUCTS"]).strip()

    # -------------------------------
    # Map Click Tag → Product Name
    # -------------------------------
    _SPECIAL = {
        "end": "End Frame",
        "opening": "Opening Frame",
    }

    def get_product_name(click_tag: str, store: str) -> str | None:
        ct = str(click_tag).strip()
        lower = ct.lower()
        if lower in _SPECIAL:
            return _SPECIAL[lower]
        m = re.search(r"(\d+)$", ct)
        if m:
            no = int(m.group(1))
            key = "Dundalk" if str(store).strip() == "Dundalk" else "Others"
            return product_lookup.get((no, key))
        return None

    df["Product Name"] = df.apply(
        lambda r: get_product_name(r["Click Tag"], r["Store"]), axis=1
    )

    # -------------------------------
    # Split mapped / unmapped
    # -------------------------------
    unmapped_df = df[df["Product Name"].isna()].copy()
    mapped_df = df.dropna(subset=["Product Name"]).copy()
    mapped_df["Product Name"] = mapped_df["Product Name"].str.strip()

    out_cols = ["Date", "Version", "Store", "Ad Size", "Click Tag", "Product Name", "Clicks"]
    return mapped_df[out_cols], unmapped_df[out_cols]


def build_final_export(
    df: pd.DataFrame,
    week_number: int | None = None,
    **kwargs
) -> pd.DataFrame:

    if week_number is None:
        raise ValueError("Redner's export requires a week number.")

    df = df.copy()

    # --------------------------------------------------
    # Ensure Date is datetime (CRITICAL)
    # --------------------------------------------------
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])

    start = df["Date"].min()
    end = df["Date"].max()

    if start.month == end.month:
        date_range = f"{start.strftime('%b %-d')} - {end.strftime('%-d')}"
    else:
        date_range = f"{start.strftime('%b %-d')} - {end.strftime('%b %-d')}"

    week_label = f"Week {week_number}: {date_range}"

    return pd.DataFrame({
        "Date": df["Date"].dt.strftime("%Y/%m/%d"),
        "Week": week_label,
        "Version": df["Version"],
        "Store": df["Store"],
        "Ad Size": df["Ad Size"],
        "Click Tag": df["Click Tag"],
        "Product": df.get("Product Name"),
        "Clicks": df["Clicks"],
    })
