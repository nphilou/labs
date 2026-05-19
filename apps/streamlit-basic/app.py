import datetime as dt

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Labs Streamlit Demo", page_icon="🧪", layout="wide")

st.title("🧪 Streamlit demo app")
st.caption("A basic app showing common Streamlit features.")

with st.sidebar:
    st.header("Controls")
    name = st.text_input("Your name", value="Friend")
    num_points = st.slider("Number of data points", min_value=10, max_value=300, value=120)
    show_raw = st.toggle("Show raw data", value=False)
    chart_type = st.selectbox("Chart type", ["Line", "Area", "Bar"])
    uploaded_file = st.file_uploader("Optional CSV upload", type=["csv"])

st.success(f"Welcome, {name}!")

left, right = st.columns(2)

with left:
    st.subheader("Interactive widgets")
    st.metric("Today", dt.date.today().isoformat())
    score = st.number_input("Pick a score", min_value=0, max_value=100, value=42)
    st.progress(min(score, 100) / 100)
    st.write("Selected score:", score)

with right:
    st.subheader("Quick notes")
    with st.expander("What this app includes"):
        st.markdown(
            """
            - Sidebar controls
            - Metrics and layout columns
            - Interactive dataframe
            - Chart rendering
            - File upload
            """
        )

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.info("Using uploaded CSV data.")
else:
    rng = np.random.default_rng(7)
    df = pd.DataFrame(
        {
            "x": np.arange(num_points),
            "series_a": rng.normal(0, 1, num_points).cumsum(),
            "series_b": rng.normal(0, 1, num_points).cumsum(),
        }
    )

st.subheader("Data preview")
st.dataframe(df, use_container_width=True)

if show_raw:
    st.code(df.head(15).to_csv(index=False), language="csv")

if {"x", "series_a", "series_b"}.issubset(df.columns):
    chart_df = df.set_index("x")[["series_a", "series_b"]]
else:
    numeric = df.select_dtypes(include=["number"])
    chart_df = numeric if not numeric.empty else None

st.subheader("Chart")
if chart_df is None or chart_df.empty:
    st.warning("No numeric columns available to chart.")
else:
    if chart_type == "Line":
        st.line_chart(chart_df)
    elif chart_type == "Area":
        st.area_chart(chart_df)
    else:
        st.bar_chart(chart_df)

st.subheader("Map")
map_data = pd.DataFrame(
    {
        "lat": [37.7749, 34.0522, 40.7128],
        "lon": [-122.4194, -118.2437, -74.0060],
    }
)
st.map(map_data, zoom=3)
