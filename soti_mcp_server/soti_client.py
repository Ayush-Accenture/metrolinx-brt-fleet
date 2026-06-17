import logging
import os
import time
from typing import Any, Optional
from urllib.parse import urlencode
import httpx

logger = logging.getLogger(__name__)

# Configuration 
SOTI_BASE_URL   = os.getenv("SOTI_BASE_URL", "")
SOTI_USERNAME   = os.getenv("SOTI_USERNAME", "")
SOTI_PASSWORD   = os.getenv("SOTI_PASSWORD", "")
SOTI_CLIENT_ID  = os.getenv("SOTI_CLIENT_ID", "")
SOTI_CLIENT_SECRET = os.getenv("SOTI_CLIENT_SECRET", "")
SOTI_GRANT_TYPE = os.getenv("SOTI_GRANT_TYPE", "password")

# Strip trailing slash from base URL so we can always prepend "/"
SOTI_BASE_URL = SOTI_BASE_URL.rstrip("/")

class TokenStore:
    """Holds one bearer token and its expiry time."""
    def __init__(self):
        self.access_token: Optional[str] = None
        self.expires_at: float = 0.0          # unix timestamp

    def is_valid(self, buffer_seconds: int = 30) -> bool:
        return (
            self.access_token is not None
            and time.time() < (self.expires_at - buffer_seconds)
        )

    def store(self, token: str, expires_in: int):
        self.access_token = token
        self.expires_at = time.time() + expires_in

class SotiClient:
    """
    Async SOTI MobiControl API client.

    Authentication strategy
    -----------------------
    SOTI supports two token endpoints:
      1. POST /api/token          – legacy form-encoded endpoint
      2. POST /oauth/token        – OAuth2 client_credentials endpoint

    We try (2) first; if it fails we fall back to (1).
    """

    def __init__(self):
        # httpx AsyncClient created lazily so the class is safe to
        # instantiate at import time without a running event-loop.
        self._http: Optional[httpx.AsyncClient] = None
        self._token_store = TokenStore()

    # Lifecycle helpers
    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                verify=False,            # Self-signed cert on the test host
                timeout=httpx.Timeout(30.0),
            )
        return self._http

    async def close(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    # Token acquisition
    async def _fetch_token_oauth(self, http: httpx.AsyncClient) -> Optional[TokenStore]:
        """Try POST /oauth/token (OAuth2 client_credentials flow)."""
        url = SOTI_BASE_URL.replace("/MobiControl/api", "/MobiControl/oauth/token")
        payload = {
            "grant_type":    SOTI_GRANT_TYPE,
            "username":      SOTI_USERNAME,
            "password":      SOTI_PASSWORD,
            "client_id":     SOTI_CLIENT_ID,
            "client_secret": SOTI_CLIENT_SECRET,
        }
        try:
            resp = await http.post(url, data=payload)
            resp.raise_for_status()
            data = resp.json()
            ts = TokenStore()
            ts.store(data["access_token"], int(data.get("expires_in", 3600)))
            logger.info("Token acquired via /oauth/token")
            return ts
        except Exception as exc:
            logger.warning(f"/oauth/token failed: {exc}")
            return None

    async def _fetch_token_api(self, http: httpx.AsyncClient) -> TokenStore:
        """Fallback: POST /api/token (legacy SOTI endpoint)."""
        url = f"{SOTI_BASE_URL}/token"
        payload = {
            "grant_type":    SOTI_GRANT_TYPE,
            "username":      SOTI_USERNAME,
            "password":      SOTI_PASSWORD,
            "client_id":     SOTI_CLIENT_ID,
            "client_secret": SOTI_CLIENT_SECRET,
        }
        resp = await http.post(url, data=payload)
        resp.raise_for_status()
        data = resp.json()
        ts = TokenStore()
        ts.store(data["access_token"], int(data.get("expires_in", 3600)))
        logger.info("Token acquired via /api/token")
        return ts

    async def _ensure_token(self):
        if self._token_store.is_valid():
            return
        http = await self._get_http()
        result = await self._fetch_token_oauth(http)
        if result is None:
            result = await self._fetch_token_api(http)
        self._token_store = result

    # Low-level request helper
    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json_body: Optional[Any] = None,
        raw_path: bool = False,
    ) -> Any:
        """
        Execute an authenticated request against the SOTI API.

        Parameters
        ----------
        method    : HTTP verb (GET / POST / PUT / DELETE)
        path      : API path relative to SOTI_BASE_URL, e.g. "/devices"
        params    : URL query parameters
        json_body : Request body (serialised as JSON)
        raw_path  : If True, ``path`` is used as-is (already includes base)
        """
        await self._ensure_token()
        http = await self._get_http()
        headers = {
            "Authorization": f"Bearer {self._token_store.access_token}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        }
        url = path if raw_path else f"{SOTI_BASE_URL}/{path.lstrip('/')}"

        resp = await http.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json_body,
        )
        resp.raise_for_status()

        # 204 No Content or empty body
        if resp.status_code == 204 or not resp.content:
            return {"status": "success", "http_status": resp.status_code}

        return resp.json()

    # Public API methods – one per row in the specification table
    # Token (exposed for diagnostics / pre-warm)
    async def get_token_api(self) -> dict:
        """POST /api/token – acquire token via legacy endpoint."""
        http = await self._get_http()
        ts = await self._fetch_token_api(http)
        return {"access_token": ts.access_token, "expires_at": ts.expires_at}

    async def get_token_oauth(self) -> dict:
        """POST /oauth/token – acquire token via OAuth2 endpoint."""
        http = await self._get_http()
        ts = await self._fetch_token_oauth(http)
        if ts is None:
            raise RuntimeError("/oauth/token failed; check credentials")
        return {"access_token": ts.access_token, "expires_at": ts.expires_at}

    # Devices
    async def get_all_devices(self, top: int = 5000, skip: int = 0) -> Any:
        """GET /api/devices?top=N&skip=N – retrieve devices with pagination."""
        return await self._request(
            "GET", "/devices", params={"top": top, "skip": skip}
        )

    async def get_device_info(self, device_id: str) -> Any:
        """GET /api/devices/{deviceId} – get a single device."""
        return await self._request("GET", f"/devices/{device_id}")

    async def search_devices_by_reference_id(self, reference_id: str) -> Any:
        """GET /api/devices/search?groupPath=referenceId:{referenceId}"""
        return await self._request(
            "GET",
            "/devices/search",
            params={"groupPath": f"referenceId:{reference_id}"},
        )

    async def search_devices_by_group_path(self, path: str) -> Any:
        """GET /api/devices/search?groupPath={path}"""
        return await self._request(
            "GET", "/devices/search", params={"groupPath": path}
        )

    async def search_devices_by_group_path_flat(
        self,
        path: str,
        include_subgroups: bool = False,
        verify_and_sync: bool = False,
    ) -> Any:
        """GET /api/devices/search – CCMS variant with extra flags."""
        return await self._request(
            "GET",
            "/devices/search",
            params={
                "groupPath":      path,
                "includeSubgroups": str(include_subgroups).lower(),
                "verifyAndSync":    str(verify_and_sync).lower(),
            },
        )

    async def search_devices_by_name(self, device_name: str) -> Any:
        """GET /api/devices/search?filter=DeviceName eq '{device_name}'"""
        return await self._request(
            "GET",
            "/devices/search",
            params={"filter": f"DeviceName eq '{device_name}'"},
        )

    async def filter_devices_by_logical_id(self, logical_device_id: str) -> Any:
        """GET /api/devices/search?filter=CustomData['LogicalDeviceID']={value}"""
        filter_expr = f"CustomData['LogicalDeviceID'] eq '{logical_device_id}'"
        return await self._request(
            "GET", "/devices/search", params={"filter": filter_expr}
        )

    async def send_action_to_device(self, device_id: str, action: dict) -> Any:
        """POST /api/devices/{deviceId}/actions"""
        return await self._request("POST", f"/devices/{device_id}/actions", json_body=action)

    async def send_action_to_device_group_by_reference_id(
        self, reference_id: str, action: dict
    ) -> Any:
        """POST /api/devicegroups/referenceId:{referenceId}/members/actions"""
        return await self._request(
            "POST",
            f"/devicegroups/referenceId%3A{reference_id}/members/actions",
            json_body=action,
        )

    async def send_action_to_device_group_by_path(
        self, path: str, action: dict
    ) -> Any:
        """POST /api/devicegroups/{path}/members/actions"""
        return await self._request(
            "POST", f"/devicegroups/{path}/members/actions", json_body=action
        )

    async def send_action_to_device_list(self, action: dict) -> Any:
        """POST /api/devices/actions – action payload must include device list."""
        return await self._request("POST", "/devices/actions", json_body=action)

    async def delete_device(self, device_id: str) -> Any:
        """DELETE /api/devices/{deviceId}"""
        return await self._request("DELETE", f"/devices/{device_id}")

    async def move_device_by_id(self, device_id: str, parent_path: str) -> Any:
        """PUT /api/devices/{deviceId}/parentPath"""
        return await self._request(
            "PUT",
            f"/devices/{device_id}/parentPath",
            json_body=parent_path,
        )

    async def move_device_by_mac(self, mac_address: str, parent_path: str) -> Any:
        """PUT /api/devices/mac:{mac}/parentPath"""
        return await self._request(
            "PUT",
            f"/devices/mac:{mac_address}/parentPath",
            json_body=parent_path,
        )

    # Device groups
    async def get_last_known_location(self, reference_id: str) -> Any:
        """GET /api/devicegroups/referenceId:{referenceId}/members/lastKnownLocation"""
        return await self._request(
            "GET",
            f"/devicegroups/referenceId:{reference_id}/members/lastKnownLocation",
        )
