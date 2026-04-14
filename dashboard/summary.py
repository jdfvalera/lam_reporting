import streamlit as st
import pandas as pd
from charts.summary_charts import overview_chart


def show_summary(df, target_impressions, target_clicks, target_ctr, palette):

    st.subheader("Weekly Campaign Performance Summary")

    impressions = df["Impressions"].sum()
    clicks = df["Clicks"].sum()
    ctr = clicks / impressions if impressions else 0

    over_imp = impressions - target_impressions
    over_clicks = clicks - target_clicks
    over_ctr = ctr - target_ctr

    pct_imp = over_imp / target_impressions if target_impressions else 0
    pct_clicks = over_clicks / target_clicks if target_clicks else 0
    pct_ctr = over_ctr / target_ctr if target_ctr else 0

    table = pd.DataFrame({
        "Impressions": [target_impressions, impressions, over_imp, pct_imp],
        "Clicks":      [target_clicks, clicks, over_clicks, pct_clicks],
        "CTR":         [target_ctr, ctr, over_ctr, pct_ctr],
    }, index=["Target", "Delivery", "Over Delivery", "% of Over Delivery"])

    display = table.copy()
    display.loc["Target":"Over Delivery", "Impressions"] = \
        display.loc["Target":"Over Delivery", "Impressions"].map(lambda x: f"{int(x):,}")
    display.loc["Target":"Over Delivery", "Clicks"] = \
        display.loc["Target":"Over Delivery", "Clicks"].map(lambda x: f"{int(x):,}")
    display["CTR"] = display["CTR"].map(lambda x: f"{x:.2%}")
    display.loc["% of Over Delivery", "Impressions"] = f"{pct_imp:.2%}"
    display.loc["% of Over Delivery", "Clicks"] = f"{pct_clicks:.2%}"
    display.loc["% of Over Delivery", "CTR"] = f"{pct_ctr:.2%}"

    left, right = st.columns([1.1, 1])

    with left:
        st.markdown("### Campaign Highlights")
        st.text_area(
            "Write campaign highlights",
            label_visibility="collapsed",
            height=150,
            key="campaign_highlights",
        )
        st.markdown("####")
        styled = display.style.set_table_styles([
            {"selector": "th", "props": [
                ("background-color", palette["primary"]),
                ("color", "white"),
                ("font-weight", "bold"),
            ]},
            {"selector": "td", "props": [("text-align", "center")]},
        ])
        st.dataframe(styled, use_container_width=True)

    with right:
        date_label = (
            df["Date"].min().strftime("%b %d")
            + " - "
            + df["Date"].max().strftime("%b %d")
        )
        fig = overview_chart(impressions, clicks, ctr, date_label, palette)
        st.pyplot(fig)
