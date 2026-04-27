import pandas as pd
from .base import generic_process


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
    # Remove default stores
    # -------------------------------
    # long_df = long_df[long_df["Store"] != "default"]

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

    if week_number is None:
        raise ValueError("McCaffrey's requires a Week Number.")

    if campaign_type is None:
        raise ValueError("McCaffrey's requires a Campaign Type.")

    df = df.copy()

    # Ensure Date is datetime
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])

    start = df["Date"].min()

    end = df["Date"].max()

    # Format: "Jan 23 - Feb 5"
    if start.month == end.month:
        date_range = f"{start.strftime('%b')} {start.day} - {end.day}"
    else:
        date_range = f"{start.strftime('%b')} {start.day} - {end.strftime('%b')} {end.day}"

    campaign = f"W{week_number} {campaign_type}_{date_range}"

    return pd.DataFrame({
        "Date": df["Date"].dt.strftime("%Y/%m/%d"),
        "Campaign": campaign,
        "Store": df["Store"],
        "Product": df["Product"],
        "Ad Size": df.get("Ad Size"),
        "Clicks": df["Clicks"],
    })