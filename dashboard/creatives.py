import streamlit as st
from charts.creative_charts import creative_chart


def show_creatives(df, palette):

    creative = (
        df.groupby("Creative Size")
        .agg(Impressions=("Impressions", "sum"), Clicks=("Clicks", "sum"))
    )
    creative["CTR"] = creative["Clicks"] / creative["Impressions"]

    st.dataframe(creative)

    fig = creative_chart(creative, palette)
    st.pyplot(fig)

    st.text_area("Creative Insights", key="creative_insights")
