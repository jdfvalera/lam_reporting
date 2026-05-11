import pandas as pd
import streamlit as st
from charts.area_charts import area_chart


def show_area_performance(df, palette):

    st.subheader("Summary – Area Level.")

    area = (
        df.groupby("Store")
        .agg(Impressions=("Impressions", "sum"), Clicks=("Clicks", "sum"))
    )
    area["CTR"] = area["Clicks"] / area["Impressions"]
    area_sorted = area.sort_values("Impressions", ascending=False)

    dates = pd.to_datetime(df["Date"], format="%Y/%m/%d")
    date_label = (
        dates.min().strftime("%b %d")
        + " – "
        + dates.max().strftime("%b %d")
    )

    left, right = st.columns([1.4, 1])

    with left:
        fig = area_chart(area, palette)
        st.pyplot(fig, use_container_width=True)

    with right:
        st.markdown(
            f"""<div style="
                border: 1.5px dashed {palette['primary']};
                border-radius: 6px;
                padding: 12px 14px;
                margin-bottom: 16px;
            ">
            <b style="color:{palette['primary']};">Area Performance ({date_label})</b>
            </div>""",
            unsafe_allow_html=True,
        )
        st.text_area(
            "Area Insights",
            label_visibility="collapsed",
            height=140,
            key="area_insights",
            placeholder="Write area insights here…",
        )

        styled = area_sorted.style.format({
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
