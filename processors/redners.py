import pandas as pd
import re
from .base import default_clicktag_longform


# --------------------------------------------------
# Core processing
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
    unmapped = enriched[enriched["Product Name"].isna()]
    dropped_clicks = int(unmapped["Clicks"].sum())

    enriched = enriched.dropna(subset=["Product Name"])
    enriched["Product Name"] = enriched["Product Name"].astype(str).str.strip()
    enriched = enriched[enriched["Product Name"] != ""]

    return enriched, dropped_clicks


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
        "Date": df["Date"],
        "Week": week_label,
        "Version": df["Version"],
        "Store": df["Store"],
        "Ad Size": df["Ad Size"],
        "Click Tag": df["Click Tag"],
        "Product": df.get("Product Name"),
        "Clicks": df["Clicks"],
    })
