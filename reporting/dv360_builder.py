import pandas as pd


def build_dv360_data(habanero_df, campaign, region):

    df = habanero_df.copy()

    if region == "US":
        df["Date"] = df["Date"] - pd.Timedelta(days=1)

    df["Store"] = (
        df["Insertion Order"]
        .astype(str)
        .str.split("_")
        .str[-1]
    )

    dv360 = pd.DataFrame({
        "Date": df["Date"],
        "Campaign": campaign,
        "Store": df["Store"],
        "Demographics": df["Line Item"],
        "Creative Size": df["Creative Size"],
        "Device Type": df["Device Type"],
        "Impressions": df["Impressions"],
        "Clicks": df["Clicks"],
        "Click Rate (CTR)": df["Click Rate (CTR)"],
    })

    return dv360