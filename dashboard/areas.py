import streamlit as st
from charts.area_charts import area_chart


def show_area_performance(df, palette):

    area = (
        df.groupby("Store")
        .agg(Impressions=("Impressions", "sum"), Clicks=("Clicks", "sum"))
    )
    area["CTR"] = area["Clicks"] / area["Impressions"]

    st.dataframe(area)

    fig = area_chart(area, palette)
    st.pyplot(fig)

    st.text_area("Area Insights", key="area_insights")
