import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from tgtg import TgtgClient


DEFAULT_ITEM_ID = "1198174"
DEFAULT_MIN_AVAILABLE = 3
DEFAULT_MAX_PRICE_CHF = 11.0


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def price_amount(value: dict[str, Any] | None) -> tuple[float | None, str]:
    if not value:
        return None, ""

    minor_units = value.get("minor_units")
    decimals = value.get("decimals", 2)
    code = value.get("code", "")
    if minor_units is None:
        return None, code

    return minor_units / (10**decimals), code


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True))


def credential(state: dict[str, Any], key: str, env_name: str) -> str:
    state_credentials = state.get("credentials")
    if isinstance(state_credentials, dict):
        value = str(state_credentials.get(key, "")).strip()
        if value:
            return value
    return required_env(env_name)


def send_telegram(message: str) -> None:
    if os.environ.get("TGTG_MONITOR_DRY_RUN") == "1":
        print(message)
        return

    token = required_env("TELEGRAM_BOT_TOKEN")
    chat_id = required_env("TELEGRAM_CHAT_ID")
    data = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": "true",
        }
    ).encode()
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status >= 400:
            raise RuntimeError(f"Telegram send failed with HTTP {response.status}")


def main() -> int:
    item_id = os.environ.get("TGTG_MONITOR_ITEM_ID", DEFAULT_ITEM_ID).strip()
    min_available = int(os.environ.get("TGTG_MONITOR_MIN_AVAILABLE", DEFAULT_MIN_AVAILABLE))
    max_price_chf = float(os.environ.get("TGTG_MONITOR_MAX_PRICE_CHF", DEFAULT_MAX_PRICE_CHF))
    state_path = Path(
        os.environ.get("TGTG_MONITOR_STATE", "/var/lib/labs-tgtg-monitor/state.json")
    )
    state = load_state(state_path)

    client = TgtgClient(
        access_token=credential(state, "access_token", "TGTG_ACCESS_TOKEN"),
        refresh_token=credential(state, "refresh_token", "TGTG_REFRESH_TOKEN"),
        cookie=credential(state, "cookie", "TGTG_COOKIE"),
    )
    result = client.get_item(item_id=item_id)
    state["credentials"] = client.credentials()

    item = result.get("item") or {}
    store = result.get("store") or {}
    pickup = result.get("pickup_interval") or {}

    available = int(result.get("items_available") or 0)
    price, currency = price_amount(item.get("price_including_taxes") or item.get("item_price"))
    display_name = result.get("display_name") or store.get("store_name") or f"TGTG item {item_id}"
    address = ((result.get("pickup_location") or {}).get("address") or {}).get("address_line", "")

    qualifies = (
        available >= min_available
        and price is not None
        and currency == "CHF"
        and price < max_price_chf
    )
    alert_key = f"{item_id}:{available}:{price}:{pickup.get('start')}:{pickup.get('end')}"

    if qualifies and state.get("last_alert_key") != alert_key:
        message = "\n".join(
            [
                f"{display_name}: {available} paniers available",
                f"Price: {price:.2f} {currency}",
                f"Pickup: {pickup.get('start', '?')} - {pickup.get('end', '?')}",
                f"Address: {address}",
                f"https://share.toogoodtogo.com/item/{item_id}/",
            ]
        )
        send_telegram(message)
        state["last_alert_key"] = alert_key
        state["last_status"] = "alerted"
    elif not qualifies:
        state["last_status"] = "below_threshold"

    state["last_seen"] = {
        "item_id": item_id,
        "display_name": display_name,
        "available": available,
        "price": price,
        "currency": currency,
        "qualifies": qualifies,
    }
    save_state(state_path, state)
    print(
        f"{display_name}: available={available} price={price} {currency} "
        f"qualifies={qualifies}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"tgtg monitor failed: {exc}", file=sys.stderr)
        raise
