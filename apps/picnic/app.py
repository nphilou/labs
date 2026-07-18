import json
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_PATH = Path(__file__).parent / "places.json"

st.set_page_config(page_title="Picnic Places - Jura Trois-Lacs", page_icon="🧺", layout="wide")


@st.cache_data
def load_places() -> pd.DataFrame:
    data = json.loads(DATA_PATH.read_text())
    df = pd.DataFrame(data["places"])
    return df, data["title"], data["source"], data["count"]


df, title, source, count = load_places()

st.title("🧺 " + title)
st.caption(f"{count} picnic places · source: [PDF]({source})")

with st.sidebar:
    st.header("Filters")

    search = st.text_input("Search (locality, situation, description)")

    localities = sorted(df["locality"].dropna().unique())
    picked_localities = st.multiselect("Locality", localities)

    covered = st.selectbox("Covered", ["Any", "Yes", "No"])
    reservation = st.selectbox("Reservation required", ["Any", "Yes", "No"])

filtered = df.copy()

if search:
    needle = search.lower()
    mask = (
        filtered["locality"].str.lower().str.contains(needle, na=False)
        | filtered["situation"].str.lower().str.contains(needle, na=False)
        | filtered["description"].str.lower().str.contains(needle, na=False)
    )
    filtered = filtered[mask]

if picked_localities:
    filtered = filtered[filtered["locality"].isin(picked_localities)]

if covered != "Any":
    filtered = filtered[filtered["covered"] == ("oui" if covered == "Yes" else "non")]

if reservation != "Any":
    filtered = filtered[filtered["reservation"] == ("oui" if reservation == "Yes" else "non")]

st.subheader(f"{len(filtered)} place(s)")

map_df = filtered.dropna(subset=["lat", "lon"])
if not map_df.empty:
    st.map(map_df.rename(columns={"lat": "latitude", "lon": "longitude"}), size=30)

for _, row in filtered.iterrows():
    with st.expander(f"{row['locality']} — {row['situation'] or row['description']}"):
        cols = st.columns(2)
        with cols[0]:
            st.markdown(f"**Description:** {row['description'] or '—'}")
            st.markdown(f"**Access:** {row['access'] or '—'}")
            st.markdown(f"**Infrastructure:** {row['infrastructure'] or '—'}")
            st.markdown(f"**Capacity:** {row['capacity'] or '—'}")
        with cols[1]:
            st.markdown(f"**Covered:** {row['covered'] or '—'}")
            st.markdown(f"**Reservation required:** {row['reservation'] or '—'}")
            st.markdown(f"**Responsible:** {row['responsible'] or '—'}")
            st.markdown(f"**Phone:** {row['phone'] or '—'}")
            if pd.notna(row["lat"]) and pd.notna(row["lon"]):
                gmaps_url = f"https://www.google.com/maps?q={row['lat']},{row['lon']}"
                st.markdown(f"[Open in Google Maps]({gmaps_url})")
