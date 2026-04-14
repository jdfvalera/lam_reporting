import streamlit as st
from charts.demographic_charts import demographic_chart


def show_demographics(df, palette):

    st.subheader("Summary – Demographics Level.")

    demo = (
        df.groupby("Demographics")
        .agg(Impressions=("Impressions", "sum"), Clicks=("Clicks", "sum"))
    )
    demo["CTR"] = demo["Clicks"] / demo["Impressions"]

    date_label = (
        df["Date"].min().strftime("%b %d")
        + " – "
        + df["Date"].max().strftime("%b %d")
    )

    left, right = st.columns([1, 1.4])

    with left:
        st.markdown(
            f"""<div style="
                border: 1.5px dashed {palette['primary']};
                border-radius: 6px;
                padding: 12px 14px;
                margin-bottom: 16px;
            ">
            <b style="color:{palette['primary']};">Demographics Performance ({date_label})</b>
            </div>""",
            unsafe_allow_html=True,
        )
        st.text_area(
            "Demographic Insights",
            label_visibility="collapsed",
            height=140,
            key="demographic_insights",
            placeholder="Write demographic insights here…",
        )

        styled = demo.style.format({
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

    with right:
        fig = demographic_chart(demo, palette)
        st.pyplot(fig, use_container_width=True)
