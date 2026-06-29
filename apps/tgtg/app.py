import json
from http import HTTPStatus
from typing import Any

import pandas as pd
import streamlit as st
from tgtg import AUTH_BY_EMAIL_ENDPOINT, TgtgClient


st.set_page_config(page_title="Too Good To Go API", layout="wide")


def money(value: dict[str, Any] | None) -> str:
    if not value:
        return ""

    minor_units = value.get("minor_units")
    decimals = value.get("decimals", 2)
    code = value.get("code", "")
    if minor_units is None:
        return code

    amount = minor_units / (10**decimals)
    return f"{amount:.{decimals}f} {code}".strip()


def nested(value: dict[str, Any], *keys: str, default: Any = "") -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def make_client(credentials: dict[str, str]) -> TgtgClient:
    return TgtgClient(
        access_token=credentials["access_token"],
        refresh_token=credentials["refresh_token"],
        cookie=credentials["cookie"],
    )


def request_login_pin(email: str) -> str:
    client = TgtgClient(email=email)
    response = client._post(
        client._get_url(AUTH_BY_EMAIL_ENDPOINT),
        json={
            "device_type": client.device_type,
            "email": email,
        },
    )

    if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
        raise RuntimeError("Too many login requests. Try again later.")
    if response.status_code != HTTPStatus.OK:
        raise RuntimeError(f"Login request failed: {response.status_code} {response.content!r}")

    payload = response.json()
    state = payload.get("state")
    if state == "TERMS":
        raise RuntimeError(f"{email} is not linked to a Too Good To Go account.")
    if state != "WAIT" or not payload.get("polling_id"):
        raise RuntimeError(f"Unexpected login response: {payload!r}")

    return payload["polling_id"]


def login_with_pin(email: str, polling_id: str, pin: str) -> dict[str, str]:
    client = TgtgClient(email=email)
    client._auth_by_pin(polling_id, pin)
    return {
        "access_token": client.access_token,
        "refresh_token": client.refresh_token,
        "cookie": client.cookie,
    }


def credentials_ready() -> bool:
    credentials = st.session_state.get("credentials")
    return bool(
        credentials
        and credentials.get("access_token")
        and credentials.get("refresh_token")
        and credentials.get("cookie")
    )


def item_rows(items: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for result in items:
        store = result.get("store") or {}
        item = result.get("item") or {}
        address = nested(result, "pickup_location", "address", "address_line")
        location = nested(result, "pickup_location", "location", default={})
        pickup = result.get("pickup_interval") or {}

        rows.append(
            {
                "item_id": item.get("item_id"),
                "store": result.get("display_name") or store.get("store_name"),
                "item": item.get("name") or item.get("description", "")[:70],
                "available": result.get("items_available"),
                "price": money(item.get("price_including_taxes") or item.get("item_price")),
                "value": money(item.get("value_including_taxes") or item.get("value")),
                "distance_km": round(result.get("distance", 0) / 1000, 2)
                if result.get("distance") is not None
                else None,
                "favorite": result.get("favorite"),
                "sales_window": result.get("in_sales_window"),
                "pickup_start": pickup.get("start"),
                "pickup_end": pickup.get("end"),
                "address": address,
                "latitude": location.get("latitude") if isinstance(location, dict) else None,
                "longitude": location.get("longitude") if isinstance(location, dict) else None,
            }
        )

    return pd.DataFrame(rows)


def show_exception(message: str, exc: Exception) -> None:
    st.error(message)
    with st.expander("Error details"):
        st.code(str(exc))


def load_saved_credentials() -> dict[str, str] | None:
    try:
        saved = st.secrets.get("tgtg", None)
    except Exception:
        return None

    if not saved:
        return None
    return {
        "access_token": saved["access_token"],
        "refresh_token": saved["refresh_token"],
        "cookie": saved["cookie"],
    }


if "credentials" not in st.session_state:
    st.session_state["credentials"] = {}
if "items" not in st.session_state:
    st.session_state["items"] = []
if "last_item" not in st.session_state:
    st.session_state["last_item"] = None
if "login_email" not in st.session_state:
    st.session_state["login_email"] = ""
if "login_polling_id" not in st.session_state:
    st.session_state["login_polling_id"] = ""
if "login_pin" not in st.session_state:
    st.session_state["login_pin"] = ""

st.title("Too Good To Go API")
st.caption("Browse your favorites or search nearby Too Good To Go bags with tgtg-python.")

with st.sidebar:
    st.header("Connection")

    saved_credentials = load_saved_credentials()
    if saved_credentials and not credentials_ready():
        if st.button("Use Streamlit secrets"):
            st.session_state["credentials"] = saved_credentials
            st.success("Loaded credentials from secrets.")

    auth_mode = st.radio("Authentication", ["Paste tokens", "Email login"], horizontal=True)

    if auth_mode == "Paste tokens":
        access_token = st.text_input("Access token", type="password")
        refresh_token = st.text_input("Refresh token", type="password")
        cookie = st.text_input("Cookie", type="password")

        if st.button("Connect with tokens", type="primary"):
            if not access_token or not refresh_token or not cookie:
                st.warning("Access token, refresh token, and cookie are required.")
            else:
                st.session_state["credentials"] = {
                    "access_token": access_token.strip(),
                    "refresh_token": refresh_token.strip(),
                    "cookie": cookie.strip(),
                }
                st.success("Credentials stored for this browser session.")
    else:
        email = st.text_input("Account email", key="login_email")
        st.info("Request a login PIN, then enter the code from the Too Good To Go email.")

        if st.button("Send login PIN", type="primary"):
            if not email:
                st.warning("Email is required.")
            else:
                try:
                    with st.spinner("Requesting login PIN..."):
                        st.session_state["login_polling_id"] = request_login_pin(email.strip())
                    st.success("PIN requested. Check your email.")
                except Exception as exc:
                    show_exception("Could not request login PIN.", exc)

        pin = st.text_input("Login PIN", max_chars=6, key="login_pin")
        if st.button("Submit PIN"):
            if not st.session_state["login_polling_id"]:
                st.warning("Request a login PIN first.")
            elif not pin:
                st.warning("PIN is required.")
            else:
                try:
                    with st.spinner("Logging in..."):
                        st.session_state["credentials"] = login_with_pin(
                            st.session_state["login_email"],
                            st.session_state["login_polling_id"],
                            pin.strip(),
                        )
                    st.session_state["login_polling_id"] = ""
                    st.success("Logged in.")
                except Exception as exc:
                    show_exception("Login failed.", exc)

    if credentials_ready():
        st.success("Connected")
        with st.expander("Session credentials"):
            st.code(json.dumps(st.session_state["credentials"], indent=2), language="json")
        if st.button("Forget credentials"):
            st.session_state["credentials"] = {}
            st.session_state["items"] = []
            st.session_state["last_item"] = None
            st.rerun()
    else:
        st.warning("Not connected")

if not credentials_ready():
    st.subheader("How to start")
    st.markdown(
        """
        1. Use email login once to retrieve Too Good To Go credentials.
        2. Keep the returned token JSON somewhere private if you want to reuse it.
        3. Paste those tokens on later visits, or configure them in Streamlit secrets.
        """
    )
    st.stop()

client = make_client(st.session_state["credentials"])

st.subheader("Items")
favorites_only = st.toggle("Favorites only", value=True)

latitude = longitude = radius = None
if not favorites_only:
    loc_a, loc_b, loc_c = st.columns(3)
    with loc_a:
        latitude = st.number_input("Latitude", value=46.2044, format="%.6f")
    with loc_b:
        longitude = st.number_input("Longitude", value=6.1432, format="%.6f")
    with loc_c:
        radius = st.number_input("Radius km", min_value=1, max_value=50, value=10)

if st.button("Load items", type="primary"):
    try:
        with st.spinner("Loading items..."):
            if favorites_only:
                st.session_state["items"] = client.get_items(page_size=100)
            else:
                st.session_state["items"] = client.get_items(
                    favorites_only=False,
                    latitude=latitude,
                    longitude=longitude,
                    radius=radius,
                    page_size=100,
                )
        st.success(f"Loaded {len(st.session_state['items'])} items.")
    except Exception as exc:
        show_exception("Could not load items.", exc)

items = st.session_state["items"]
if items:
    df = item_rows(items)
    available_count = int(pd.to_numeric(df["available"], errors="coerce").fillna(0).sum())
    first, second, third = st.columns(3)
    first.metric("Items", len(df))
    second.metric("Available bags", available_count)
    third.metric("Favorites", int(df["favorite"].fillna(False).sum()))

    st.dataframe(
        df.drop(columns=["latitude", "longitude"]),
        use_container_width=True,
        hide_index=True,
    )

    map_df = df.dropna(subset=["latitude", "longitude"])[["latitude", "longitude"]]
    if not map_df.empty:
        st.map(map_df, latitude="latitude", longitude="longitude", zoom=12)

    item_options = {
        f"{row.store} - {row.item_id}": row.item_id
        for row in df.itertuples()
        if row.item_id
    }
    if item_options:
        selected_label = st.selectbox("Inspect item", list(item_options.keys()))
        if st.button("Load item details"):
            try:
                st.session_state["last_item"] = client.get_item(item_id=item_options[selected_label])
            except Exception as exc:
                show_exception("Could not load item details.", exc)

    if st.session_state["last_item"]:
        st.subheader("Item detail")
        st.json(st.session_state["last_item"], expanded=False)
else:
    st.info("Load items to see results.")
