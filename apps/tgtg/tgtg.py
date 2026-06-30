import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

API_BASE_URL = "https://apptoogoodtogo.com/api"
AUTH_BY_EMAIL_ENDPOINT = "/auth/v5/authByEmail"
AUTH_POLL_ENDPOINT = "/auth/v5/authByRequestPollingId"
ITEM_ENDPOINT = "/item/v8/{item_id}"
ITEMS_ENDPOINT = "/item/v8/"


@dataclass
class Response:
    status_code: int
    content: bytes

    def json(self) -> Any:
        if not self.content:
            return {}
        return json.loads(self.content.decode("utf-8"))


class TgtgClient:
    def __init__(
        self,
        email: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        cookie: str | None = None,
    ) -> None:
        self.email = email
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.cookie = cookie
        self.device_type = "UNKNOWN"

    def _get_url(self, endpoint: str) -> str:
        if endpoint.startswith("http"):
            return endpoint
        return f"{API_BASE_URL}{endpoint}"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "TGTG/24.0.0",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        if self.cookie:
            headers["Cookie"] = self.cookie
        return headers

    def _post(self, url: str, json: dict[str, Any] | None = None) -> Response:
        data = b"" if json is None else __import__("json").dumps(json).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return Response(response.status, response.read())
        except urllib.error.HTTPError as exc:
            return Response(exc.code, exc.read())

    def _post_json(self, endpoint: str, payload: dict[str, Any]) -> Any:
        response = self._post(self._get_url(endpoint), json=payload)
        if response.status_code >= 400:
            raise RuntimeError(f"Too Good To Go API request failed: {response.status_code} {response.content!r}")
        return response.json()

    def _auth_by_pin(self, polling_id: str, pin: str) -> None:
        payload = self._post_json(
            AUTH_POLL_ENDPOINT,
            {
                "device_type": self.device_type,
                "email": self.email,
                "polling_id": polling_id,
                "pin": pin,
            },
        )
        self.access_token = payload.get("access_token")
        self.refresh_token = payload.get("refresh_token")
        self.cookie = payload.get("cookie")

    def get_item(self, item_id: str) -> dict[str, Any]:
        return self._post_json(ITEM_ENDPOINT.format(item_id=item_id), {})

    def get_items(
        self,
        favorites_only: bool = True,
        latitude: float | None = None,
        longitude: float | None = None,
        radius: int | None = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "favorites_only": favorites_only,
            "page_size": page_size,
            "page": 1,
            "origin": None,
            "radius": radius,
        }
        if latitude is not None and longitude is not None:
            payload["origin"] = {"latitude": latitude, "longitude": longitude}
        data = self._post_json(ITEMS_ENDPOINT, payload)
        if isinstance(data, list):
            return data
        return data.get("items", [])
