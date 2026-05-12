import pandas as pd
from .base import generic_process, build_campaign_label


def _parse_store(placement):
    """'Bradenton - Apr 30 - May 6_300x250' → 'Bradenton'"""
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

    result = generic_process(df, guide_df)

    if isinstance(result, tuple):
        long_df, unmapped_df = result
    else:
        long_df = result
        unmapped_df = pd.DataFrame()

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

    df = df.copy()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])

    start = df["Date"].min()
    end = df["Date"].max()

    if start.month == end.month:
        date_range = f"{start.strftime('%b')} {start.day} - {end.day}"
    else:
        date_range = f"{start.strftime('%b')} {start.day} - {end.strftime('%b')} {end.day}"

    campaign = build_campaign_label(date_range, campaign_type, week_number)

    return pd.DataFrame({
        "Date": df["Date"].dt.strftime("%Y/%m/%d"),
        "Campaign": campaign,
        "Store": df.get("Store"),
        "Product": df.get("Product"),
        "Ad Size": df.get("Ad Size"),
        "Clicks": df["Clicks"],
    })
