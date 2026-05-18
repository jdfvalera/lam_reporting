import pandas as pd
import re


# --------------------------------------------------
# Wide → Long Click Tags
# --------------------------------------------------
def default_clicktag_longform(df: pd.DataFrame) -> pd.DataFrame:
    click_tag_cols = [
        c for c in df.columns
        if c.lower().startswith("click tag ")
    ]

    if not click_tag_cols:
        raise ValueError("No Click Tag columns found.")

    id_cols = [c for c in df.columns if c not in click_tag_cols]

    long_df = df.melt(
        id_vars=id_cols,
        value_vars=click_tag_cols,
        var_name="Click Tag",
        value_name="Clicks"
    )

    long_df["Click Tag"] = (
        long_df["Click Tag"]
        .str.replace("Click Tag ", "", regex=False)
        .astype(int)
    )

    return long_df



# --------------------------------------------------
# Generic Processor (with optional guide)
# --------------------------------------------------
def generic_process(
    df: pd.DataFrame,
    guide_df: pd.DataFrame | None = None
) -> pd.DataFrame:

    long_df = default_clicktag_longform(df)

    # Normalize Ad Size if present
    if "Ad Size" in long_df.columns:
        long_df["Ad Size"] = long_df["Ad Size"].apply(clean_ad_size)

    # If no guide, return base output
    if guide_df is None:
        return long_df

    # Rename expected guide columns
    guide = guide_df.rename(
        columns={
            "Banner": "Brand",
            "Sizes": "Ad Size",
        }
    )

    if "Ad Size" in guide.columns:
        guide["Ad Size"] = guide["Ad Size"].apply(clean_ad_size)

    click_cols = [
        c for c in guide.columns
        if c.lower().startswith("click tag ")
    ]

    if not click_cols:
        raise ValueError("Click Tag Guide missing Click Tag columns.")

    guide_long = guide.melt(
        id_vars=[c for c in ["Brand", "Ad Size"] if c in guide.columns],
        value_vars=click_cols,
        var_name="Click Tag",
        value_name="Product",
    )

    guide_long["Click Tag"] = (
        guide_long["Click Tag"]
        .str.replace("Click Tag ", "", regex=False)
        .astype(int)
    )

    guide_long = guide_long.dropna(subset=["Product"])

    # Determine join keys dynamically
    join_keys = ["Click Tag"]

    if "Campaign" in long_df.columns and "Campaign" in guide_long.columns:
        join_keys.append("Campaign")

    if "Brand" in long_df.columns and "Brand" in guide_long.columns:
        join_keys.append("Brand")

    if "Ad Size" in long_df.columns and "Ad Size" in guide_long.columns:
        join_keys.append("Ad Size")

    enriched = long_df.merge(
        guide_long,
        on=join_keys,
        how="left",
    )
    
    unmapped_df = enriched[enriched["Product"].isna()].copy()

    enriched.dropna(inplace=True, subset=["Product"])

    return enriched, unmapped_df


# --------------------------------------------------
# Campaign label builder
# --------------------------------------------------
def build_campaign_label(
    date_range: str,
    campaign_name: str | None = None,
    week_number: int | None = None,
) -> str:
    """
    W{N}_{campaign_name}_{date_range}  — with week number
    {campaign_name}_{date_range}       — without week number
    W{N}_{date_range}                  — without campaign name
    {date_range}                       — neither
    """
    if week_number is not None and campaign_name:
        return f"W{week_number}_{campaign_name}_{date_range}"
    elif campaign_name:
        return f"{campaign_name}_{date_range}"
    elif week_number is not None:
        return f"W{week_number}_{date_range}"
    return date_range


# --------------------------------------------------
# Utility
# --------------------------------------------------
def clean_ad_size(val):
    if not isinstance(val, str):
        return None

    match = re.search(r"\d+\s*x\s*\d+", val)
    return match.group(0).replace(" ", "") if match else None