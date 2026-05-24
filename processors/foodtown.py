import pandas as pd
from .base import generic_process, derive_date_range_and_label


def _parse_store(placement):
    """'Atlantic Highlands - May 1 - 7_300x250' → 'Atlantic Highlands'"""
    if not isinstance(placement, str):
        return None
    return placement.split(" - ")[0].strip()


# --------------------------------------------------
# Core Processing
# --------------------------------------------------
def process(
    df: pd.DataFrame,
    guide_df: pd.DataFrame | None = None
) -> tuple:

    long_df, unmapped_df = generic_process(df, guide_df)

    if "Placement" in long_df.columns:
        long_df["Store"] = long_df["Placement"].apply(_parse_store)
    else:
        long_df["Store"] = None

    if not unmapped_df.empty and "Placement" in unmapped_df.columns:
        unmapped_df["Store"] = unmapped_df["Placement"].apply(_parse_store)

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

    df, _, campaign = derive_date_range_and_label(df, campaign_type, week_number)

    return pd.DataFrame({
        "Date": df["Date"].dt.strftime("%Y/%m/%d"),
        "Campaign": campaign,
        "Store": df.get("Store"),
        "Product": df.get("Product"),
        "Ad Size": df.get("Ad Size"),
        "Clicks": df["Clicks"],
    })
