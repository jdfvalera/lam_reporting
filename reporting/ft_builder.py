import pandas as pd


def build_ft_data(df, week_number, campaign_type):

    df = df.copy()

    df["Date"] = pd.to_datetime(df["Date"])

    start = df["Date"].min()
    end = df["Date"].max()

    if start.month == end.month:
        date_range = f"{start.strftime('%b %-d')} - {end.strftime('%-d')}"
    else:
        date_range = f"{start.strftime('%b %-d')} - {end.strftime('%b %-d')}"

    campaign = f"W{week_number} {campaign_type}_{date_range}"

    ft_data = pd.DataFrame({
        "Date": df["Date"],
        "Campaign": campaign,
        "Store": df.get("Store"),
        "Product": df.get("Product"),
        "Ad Size": df.get("Ad Size"),
        "Clicks": df["Clicks"],
    })

    return ft_data, campaign