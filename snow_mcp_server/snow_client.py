"""ServiceNow REST API client."""

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

_BASE_URL = os.environ["SNOW_API_BASE_URL"]
_AUTH = (os.environ["SNOW_USERNAME"], os.environ["SNOW_PASSWORD"])
_HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}
_CATALOG_ITEM_SYS_ID = os.environ["SNOW_CATALOG_ITEM_SYS_ID"]
_REQUESTED_FOR = os.environ["SNOW_REQUESTED_FOR"]

_ORDER_PATHS = [
    "now/v1/servicecatalog/items/{sys_id}/order_now",
    "now/v2/servicecatalog/items/{sys_id}/order_now",
    "sn_sc/servicecatalog/items/{sys_id}/order_now",
]

_ITEM_PATHS = [
    "now/v1/servicecatalog/items/{sys_id}",
    "now/v2/servicecatalog/items/{sys_id}",
    "sn_sc/servicecatalog/items/{sys_id}",
]

# Cached after first fetch so we only hit the catalog metadata endpoint once per session
_var_name_cache: dict[str, str] | None = None


async def _try_paths(client: httpx.AsyncClient, paths: list[str], method: str, **kwargs) -> dict:
    """Try each path in order; move to next only on 404/405, raise immediately on other errors."""
    last_error = None
    for path_tpl in paths:
        url = f"{_BASE_URL}/{path_tpl.format(sys_id=_CATALOG_ITEM_SYS_ID)}"
        resp = await getattr(client, method)(url, **kwargs)
        if resp.status_code in (404, 405):
            last_error = resp
            continue
        resp.raise_for_status()
        return resp.json()["result"]
    last_error.raise_for_status()


async def _resolve_variable_names(client: httpx.AsyncClient) -> dict[str, str]:
    """Return the real catalog variable names for our fields, with sensible defaults as fallback."""
    global _var_name_cache
    if _var_name_cache is not None:
        return _var_name_cache

    try:
        result = await _try_paths(
            client, _ITEM_PATHS, "get",
            auth=_AUTH, headers={"Accept": "application/json"}, timeout=30,
        )
        variables = result.get("variables", [])

        name_map = {v.get("name", "").lower(): v["name"] for v in variables if v.get("name")}
        label_map = {v.get("label", "").lower(): v["name"] for v in variables if v.get("label")}

        resolved = {
            "short_description": (
                name_map.get("short_description")
                or label_map.get("short description")
                or "short_description"
            ),
            "description": (
                name_map.get("description")
                or label_map.get("description")
                or name_map.get("details")
                or label_map.get("details")
                or "description"
            ),
        }
    except Exception:
        resolved = {"short_description": "short_description", "description": "description"}

    _var_name_cache = resolved
    return resolved


async def get_catalog_item_variables() -> list[dict]:
    """Return the raw variable definitions on the catalog item (name, label, type)."""
    async with httpx.AsyncClient() as client:
        result = await _try_paths(
            client, _ITEM_PATHS, "get",
            auth=_AUTH, headers={"Accept": "application/json"}, timeout=30,
        )
    return result.get("variables", [])


async def create_sr(short_description: str, description: str) -> dict:
    async with httpx.AsyncClient() as client:
        # Step 1 — resolve real variable names from the catalog item (cached after first call)
        var_names = await _resolve_variable_names(client)

        # Step 2 — order via Service Catalog (tries all 3 path variants)
        sr = await _try_paths(
            client,
            _ORDER_PATHS,
            "post",
            json={
                "sysparm_quantity": "1",
                "requested_for": _REQUESTED_FOR,
                "variables": {
                    var_names["short_description"]: short_description,
                    var_names["description"]: description,
                },
            },
            auth=_AUTH,
            headers=_HEADERS,
            timeout=30,
        )
        sr_sys_id = sr["sys_id"]

        # Step 3 — fetch the RITM auto-created under the SR
        ritm_resp = await client.get(
            f"{_BASE_URL}/now/table/sc_req_item",
            params={
                "sysparm_query": f"request={sr_sys_id}",
                "sysparm_fields": "number,sys_id",
                "sysparm_limit": "1",
            },
            auth=_AUTH,
            headers={"Accept": "application/json"},
            timeout=30,
        )
        ritm_resp.raise_for_status()
        ritms = ritm_resp.json().get("result", [])
        ritm = ritms[0] if ritms else {}
        ritm_sys_id = ritm.get("sys_id", "")

        # Step 4 — fetch the SCTASK under the RITM
        sctask: dict = {}
        if ritm_sys_id:
            task_resp = await client.get(
                f"{_BASE_URL}/now/table/sc_task",
                params={
                    "sysparm_query": f"request_item={ritm_sys_id}",
                    "sysparm_fields": "number,sys_id",
                    "sysparm_limit": "1",
                },
                auth=_AUTH,
                headers={"Accept": "application/json"},
                timeout=30,
            )
            task_resp.raise_for_status()
            tasks = task_resp.json().get("result", [])
            sctask = tasks[0] if tasks else {}

    return {
        "sr_number": sr.get("number", sr_sys_id),
        "sr_sys_id": sr_sys_id,
        "ritm_number": ritm.get("number", ""),
        "ritm_sys_id": ritm_sys_id,
        "sctask_number": sctask.get("number", ""),
        "sctask_sys_id": sctask.get("sys_id", ""),
        "variables_used": var_names,
    }


async def get_record(record_number: str) -> dict | None:
    table = "sc_request" if record_number.upper().startswith("REQ") else "sc_req_item"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_BASE_URL}/now/table/{table}",
            params={
                "sysparm_query": f"number={record_number}",
                "sysparm_fields": "number,short_description,state,assignment_group,sys_created_on",
                "sysparm_limit": "1",
            },
            auth=_AUTH,
            headers={"Accept": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        results = resp.json().get("result", [])
    return results[0] if results else None
