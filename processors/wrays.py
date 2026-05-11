import pandas as pd
from .base import generic_process, build_campaign_label


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

    # Version column contains store names (e.g. Chalet, MarketSelah, MeadowBrook)
    if "Version" in long_df.columns:
        long_df = long_df.rename(columns={"Version": "Store"})
    if not unmapped_df.empty and "Version" in unmapped_df.columns:
        unmapped_df = unmapped_df.rename(columns={"Version": "Store"})

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
        "Ad Size": df.get("Ad Size"),
        "Product": df.get("Product"),
        "Clicks": df["Clicks"],
    })
