import pandas as pd
from .base import generic_process


# --------------------------------------------------
# Core Processing
# --------------------------------------------------
def _parse_zone(placement):
    """'QLD_Zone 01 - Apr 8 - 21_300x250' → 'Zone 01'"""
    if not isinstance(placement, str):
        return None
    parts = placement.split("_", 2)
    if len(parts) < 2:
        return None
    return parts[1].split(" - ")[0].strip()


def process(
    df: pd.DataFrame,
    guide_df: pd.DataFrame | None = None
) -> pd.DataFrame:

    long_df, unmapped_df = generic_process(df, guide_df)

    # -------------------------------
    # Parse Zone from Placement
    # -------------------------------
    if "Placement" in long_df.columns:
        long_df["Zone"] = long_df["Placement"].apply(_parse_zone)
    else:
        long_df["Zone"] = None

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

    if week_number is None:
        raise ValueError("Bottlemart requires a Week Number.")

    if campaign_type is None:
        raise ValueError("Bottlemart requires a Campaign Type.")

    df = df.copy()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])

    start = df["Date"].min()
    end = df["Date"].max()

    if start.month == end.month:
        date_range = f"{start.strftime('%b')} {start.day} - {end.day}"
    else:
        date_range = f"{start.strftime('%b')} {start.day} - {end.strftime('%b')} {end.day}"

    campaign = f"W{week_number} {campaign_type}_{date_range}"

    return pd.DataFrame({
        "Date": df["Date"].dt.strftime("%Y/%m/%d"),
        "Campaign": campaign,
        "Zone": df.get("Zone"),
        "Product": df.get("Product"),
        "Ad Size": df.get("Ad Size"),
        "Clicks": df["Clicks"],
    })
