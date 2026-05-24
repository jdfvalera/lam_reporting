import pandas as pd
from .base import generic_process, derive_date_range_and_label


# --------------------------------------------------
# Products to exclude
# --------------------------------------------------
EXCLUDED_PRODUCTS = {
    "Opening Frame",
    "End Frame",
}


# --------------------------------------------------
# Core Processing
# --------------------------------------------------
def process(
    df: pd.DataFrame,
    guide_df: pd.DataFrame | None = None
) -> pd.DataFrame:

    # Use generic engine first
    long_df, unmapped_df = generic_process(df, guide_df)

    # -------------------------------
    # Parse Store from Version
    # -------------------------------
    if "Version" in long_df.columns:
        long_df["Store"] = (
            long_df["Version"]
            .astype(str)
            .str.replace("_", " ")
        )
    else:
        long_df["Store"] = None
        
    # -------------------------------
    # Exclude Opening / End Frames
    # -------------------------------
    if "Product" in long_df.columns:
        long_df["Product"] = long_df["Product"].astype(str).str.strip()
        long_df = long_df[
            ~long_df["Product"].isin(EXCLUDED_PRODUCTS)
        ]

    return long_df, unmapped_df


# --------------------------------------------------
# Final Export
# --------------------------------------------------
def build_final_export(
    df: pd.DataFrame,
    week_number: int | None = None,
    campaign_type: str | None = None,
    **kwargs
) -> pd.DataFrame:

    if campaign_type is None:
        raise ValueError("McCaffrey's requires a Campaign Type.")

    df, _, campaign = derive_date_range_and_label(df, campaign_type, week_number)

    return pd.DataFrame({
        "Date": df["Date"].dt.strftime("%Y/%m/%d"),
        "Campaign": campaign,
        "Store": df["Store"],
        "Product": df["Product"],
        "Ad Size": df.get("Ad Size"),
        "Clicks": df["Clicks"],
    })