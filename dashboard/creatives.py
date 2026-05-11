import pandas as pd
import streamlit as st
from charts.creative_charts import creative_chart


def show_creatives(df, palette):

    st.subheader("Summary – Creatives.")

    creative = (
        df.groupby("Creative Size")
        .agg(Impressions=("Impressions", "sum"), Clicks=("Clicks", "sum"))
    )
    creative["CTR"] = creative["Clicks"] / creative["Impressions"]
    creative_sorted = creative.sort_values("Clicks", ascending=False)

    dates = pd.to_datetime(df["Date"], format="%Y/%m/%d")
    date_label = (
        dates.min().strftime("%b %d")
        + " – "
        + dates.max().strftime("%b %d")
    )

    left, right = st.columns([1, 1.4])

    with left:
        styled = creative_sorted.style.format({
            "Impressions": "{:,.0f}",
            "Clicks": "{:,.0f}",
            "CTR": "{:.2%}",
        }).set_table_styles([
            {"selector": "th", "props": [
                ("background-color", palette["primary"]),
                ("color", "white"),
                ("font-weight", "bold"),
            ]},
            {"selector": "td", "props": [("text-align", "center")]},
        ])
        st.dataframe(styled, use_container_width=True)

        st.markdown(
            f"""<div style="
                border: 1.5px dashed {palette['primary']};
                border-radius: 6px;
                padding: 12px 14px;
                margin-top: 12px;
            ">
            <b style="color:{palette['primary']};">Creative Performance ({date_label})</b>
            </div>""",
            unsafe_allow_html=True,
        )
        st.text_area(
            "Creative Insights",
            label_visibility="collapsed",
            height=140,
            key="creative_insights",
            placeholder="Write creative insights here…",
        )

    with right:
        fig = creative_chart(creative, palette)
        st.pyplot(fig, use_container_width=True)
