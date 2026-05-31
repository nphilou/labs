import datetime as dt
import os
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import streamlit as st


STATUSES = [
    "To review",
    "Contacted",
    "Scheduled",
    "Visited",
    "Applied",
    "Rejected",
    "Archived",
]

DB_PATH = Path(os.environ.get("APARTMENT_TRACKER_DB", "apartments.sqlite3"))


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS apartments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL DEFAULT '',
                price_chf INTEGER,
                size_m2 REAL,
                rooms REAL,
                time_to_work_min INTEGER,
                time_to_badminton_min INTEGER,
                status TEXT NOT NULL DEFAULT 'To review',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def normalize_url(value: str) -> str:
    value = value.strip()
    if value and "://" not in value:
        return f"https://{value}"
    return value


def title_from_url(link: str) -> str:
    parsed = urlparse(link)
    host = parsed.netloc.replace("www.", "")
    path_parts = parsed.path.strip("/").split("/")
    suffix = (
        path_parts[-1].replace("-", " ").replace("_", " ")
        if path_parts and path_parts[-1]
        else ""
    )
    if suffix:
        return f"{host} - {suffix[:60]}"
    return host or "Apartment"


def none_if_nan(value):
    if pd.isna(value):
        return None
    return value


def clean_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def add_apartment(values: dict) -> None:
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    link = normalize_url(values["link"])
    title = values["title"].strip() or title_from_url(link)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO apartments (
                link, title, price_chf, size_m2, rooms, time_to_work_min,
                time_to_badminton_min, status, notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                link,
                title,
                values["price_chf"],
                values["size_m2"],
                values["rooms"],
                values["time_to_work_min"],
                values["time_to_badminton_min"],
                values["status"],
                values["notes"].strip(),
                now,
                now,
            ),
        )


def load_apartments() -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql_query(
            """
            SELECT
                id,
                link,
                title,
                price_chf,
                size_m2,
                rooms,
                time_to_work_min,
                time_to_badminton_min,
                status,
                notes,
                updated_at
            FROM apartments
            ORDER BY updated_at DESC, id DESC
            """,
            conn,
        )


def save_apartments(df: pd.DataFrame) -> None:
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    with connect() as conn:
        for row in df.to_dict(orient="records"):
            if row.get("delete"):
                conn.execute("DELETE FROM apartments WHERE id = ?", (int(row["id"]),))
                continue

            conn.execute(
                """
                UPDATE apartments
                SET
                    link = ?,
                    title = ?,
                    price_chf = ?,
                    size_m2 = ?,
                    rooms = ?,
                    time_to_work_min = ?,
                    time_to_badminton_min = ?,
                    status = ?,
                    notes = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    normalize_url(str(row["link"])),
                    clean_text(row["title"]),
                    none_if_nan(row["price_chf"]),
                    none_if_nan(row["size_m2"]),
                    none_if_nan(row["rooms"]),
                    none_if_nan(row["time_to_work_min"]),
                    none_if_nan(row["time_to_badminton_min"]),
                    row["status"],
                    clean_text(row["notes"]),
                    now,
                    int(row["id"]),
                ),
            )


init_db()

st.set_page_config(page_title="Apartment Tracker", page_icon=":material/home:", layout="wide")
st.title("Apartment tracker")

with st.sidebar:
    st.header("Add apartment")
    with st.form("add_apartment", clear_on_submit=True):
        link = st.text_input("Listing link")
        title = st.text_input("Title")
        price_chf = st.number_input("Price CHF", min_value=0, step=50, value=None)
        col_a, col_b = st.columns(2)
        with col_a:
            size_m2 = st.number_input("Size m2", min_value=0.0, step=1.0, value=None)
        with col_b:
            rooms = st.number_input("Rooms", min_value=0.0, step=0.5, value=None)
        col_c, col_d = st.columns(2)
        with col_c:
            time_to_work_min = st.number_input("Work min", min_value=0, step=1, value=None)
        with col_d:
            time_to_badminton_min = st.number_input(
                "Badminton min", min_value=0, step=1, value=None
            )
        status = st.selectbox("Status", STATUSES)
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Add")

    if submitted:
        if not link.strip():
            st.error("A listing link is required.")
        else:
            try:
                add_apartment(
                    {
                        "link": link,
                        "title": title,
                        "price_chf": price_chf,
                        "size_m2": size_m2,
                        "rooms": rooms,
                        "time_to_work_min": time_to_work_min,
                        "time_to_badminton_min": time_to_badminton_min,
                        "status": status,
                        "notes": notes,
                    }
                )
                st.success("Apartment added.")
            except sqlite3.IntegrityError:
                st.error("That link is already in the tracker.")

df = load_apartments()

if df.empty:
    st.info("Paste an apartment listing link in the sidebar to start tracking.")
else:
    metric_cols = st.columns(4)
    active = df[~df["status"].isin(["Rejected", "Archived"])]
    metric_cols[0].metric("Apartments", len(df))
    metric_cols[1].metric("Active", len(active))
    metric_cols[2].metric("Contacted", int((df["status"] == "Contacted").sum()))
    metric_cols[3].metric("Visited", int((df["status"] == "Visited").sum()))

    status_filter = st.multiselect("Status filter", STATUSES, default=STATUSES)
    visible = df[df["status"].isin(status_filter)].copy()
    visible.insert(0, "delete", False)

    edited = st.data_editor(
        visible,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "delete": st.column_config.CheckboxColumn("Delete"),
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "link": st.column_config.LinkColumn("Link", display_text="open"),
            "title": st.column_config.TextColumn("Title", width="medium"),
            "price_chf": st.column_config.NumberColumn("Price", format="CHF %d", step=50),
            "size_m2": st.column_config.NumberColumn("Size", format="%.1f m2", step=1.0),
            "rooms": st.column_config.NumberColumn("Rooms", step=0.5),
            "time_to_work_min": st.column_config.NumberColumn("Work", format="%d min", step=1),
            "time_to_badminton_min": st.column_config.NumberColumn(
                "Badminton", format="%d min", step=1
            ),
            "status": st.column_config.SelectboxColumn("Status", options=STATUSES),
            "notes": st.column_config.TextColumn("Notes", width="large"),
            "updated_at": st.column_config.TextColumn("Updated", disabled=True),
        },
        disabled=["id", "updated_at"],
    )

    if st.button("Save table changes", type="primary"):
        try:
            save_apartments(edited)
            st.success("Saved.")
            st.rerun()
        except sqlite3.IntegrityError as exc:
            st.error(f"Could not save changes: {exc}")

st.caption(f"SQLite database: {DB_PATH}")
