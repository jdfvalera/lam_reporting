import re
import pandas as pd
from .base import generic_process, derive_date_range_and_label


# --------------------------------------------------
# Core Processing
# --------------------------------------------------
def process(
    df: pd.DataFrame,
    guide_df: pd.DataFrame | None = None
) -> tuple:

    long_df, unmapped_df = generic_process(df, guide_df)

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

    store = re.sub(r"\s*store\s*$", "", campaign_type, flags=re.IGNORECASE).strip() if campaign_type else None

    return pd.DataFrame({
        "Date": df["Date"].dt.strftime("%Y/%m/%d"),
        "Campaign": campaign,
        "Store": store,
        "Ad Size": df.get("Ad Size"),
        "Product": df.get("Product"),
        "Clicks": df["Clicks"],
    })
