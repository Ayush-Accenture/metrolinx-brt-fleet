"""ServiceNow REST API client."""

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

_BASE_URL = os.environ["SNOW_API_BASE_URL"]
_AUTH = (os.environ["SNOW_USERNAME"], os.environ["SNOW_PASSWORD"])
_HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}
# Optional — operator can override at the HITL gate; empty string is fine at startup.
_REQUESTED_FOR = os.environ.get("SNOW_REQUESTED_FOR", "")

# ── Catalog item resolution ───────────────────────────────────────────────────
# Either set SNOW_CATALOG_ITEM_SYS_ID directly (if known), OR set
# SNOW_CATALOG_ITEM_NAME and the code will discover the sys_id at runtime.
_CATALOG_ITEM_SYS_ID_ENV: str = os.environ.get("SNOW_CATALOG_ITEM_SYS_ID", "").strip()
_CATALOG_ITEM_NAME: str = os.environ.get("SNOW_CATALOG_ITEM_NAME", "").strip()

# Resolved at first use and cached for the process lifetime
_resolved_catalog_sys_id: str | None = _CATALOG_ITEM_SYS_ID_ENV or None

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


# ── Catalog item sys_id discovery ─────────────────────────────────────────────

async def _get_catalog_item_sys_id(client: httpx.AsyncClient) -> str:
    """
    Return the catalog item sys_id to use for ordering.

    Resolution order:
      1. SNOW_CATALOG_ITEM_SYS_ID env var (if set)
      2. Auto-discover from SNOW by searching SNOW_CATALOG_ITEM_NAME
         against the sc_cat_item table (result cached for process lifetime).

    Raises RuntimeError with a helpful message if neither env var is set,
    or if the name search returns zero or multiple matches (in the multi-match
    case all candidates are listed so the operator can pick the right one).
    """
    global _resolved_catalog_sys_id

    if _resolved_catalog_sys_id:
        return _resolved_catalog_sys_id

    if not _CATALOG_ITEM_NAME:
        raise RuntimeError(
            "Cannot determine catalog item sys_id.\n"
            "Set either:\n"
            "  SNOW_CATALOG_ITEM_SYS_ID=<32-char hex>   — if you already know it\n"
            "  SNOW_CATALOG_ITEM_NAME=<display name>     — to auto-discover it\n"
            "Example: SNOW_CATALOG_ITEM_NAME=Device Monitoring"
        )

    items = await _search_catalog_items(client, _CATALOG_ITEM_NAME)

    if not items:
        # Name didn't match anything — fetch all active items so the operator
        # can see exactly what's available and set the right name/sys_id.
        all_items = await _search_catalog_items(client, "")
        all_names = "\n".join(
            f"  sys_id={i['sys_id']}  name={i['name']!r}"
            for i in all_items[:30]
        )
        raise RuntimeError(
            f"No active catalog item found matching '{_CATALOG_ITEM_NAME}'.\n\n"
            f"Available catalog items in this SNOW instance ({len(all_items)} total, showing up to 30):\n"
            f"{all_names}\n\n"
            "Set SNOW_CATALOG_ITEM_NAME to one of the names above (partial match is fine),\n"
            "or set SNOW_CATALOG_ITEM_SYS_ID directly."
        )

    if len(items) > 1:
        choices = "\n".join(
            f"  sys_id={i['sys_id']}  name={i['name']!r}  desc={i.get('short_description','')!r}"
            for i in items
        )
        raise RuntimeError(
            f"Multiple catalog items match '{_CATALOG_ITEM_NAME}':\n{choices}\n\n"
            "Narrow SNOW_CATALOG_ITEM_NAME or set SNOW_CATALOG_ITEM_SYS_ID to one of the sys_ids above."
        )

    _resolved_catalog_sys_id = items[0]["sys_id"]
    return _resolved_catalog_sys_id


# ── Catalog search helper ─────────────────────────────────────────────────────

async def _search_catalog_items(
    client: httpx.AsyncClient,
    name_filter: str,
    limit: int = 30,
) -> list[dict]:
    """
    Query sc_cat_item for active items.
    Pass an empty name_filter to return all active items (up to limit).
    Uses nameLIKE so partial matches work (e.g. "monitoring" matches
    "Device Monitoring", "BRT Monitoring Alert", etc.).
    """
    query = "active=true"
    if name_filter:
        query = f"nameLIKE{name_filter}^{query}"

    resp = await client.get(
        f"{_BASE_URL}/now/table/sc_cat_item",
        params={
            "sysparm_query": query,
            "sysparm_fields": "name,sys_id,short_description,category",
            "sysparm_limit": str(limit),
        },
        auth=_AUTH,
        headers={"Accept": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("result", [])


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _try_paths(
    client: httpx.AsyncClient,
    paths: list[str],
    method: str,
    catalog_sys_id: str,
    **kwargs,
) -> dict:
    """Try each path variant in order; move to next only on 404/405."""
    last_error = None
    for path_tpl in paths:
        url = f"{_BASE_URL}/{path_tpl.format(sys_id=catalog_sys_id)}"
        resp = await getattr(client, method)(url, **kwargs)
        if resp.status_code in (404, 405):
            last_error = resp
            continue
        resp.raise_for_status()
        return resp.json()["result"]
    last_error.raise_for_status()


async def _resolve_variable_names(
    client: httpx.AsyncClient,
    catalog_sys_id: str,
) -> dict[str, str]:
    """Return the real catalog variable names for our fields (cached after first call)."""
    global _var_name_cache
    if _var_name_cache is not None:
        return _var_name_cache

    try:
        result = await _try_paths(
            client, _ITEM_PATHS, "get", catalog_sys_id,
            auth=_AUTH, headers={"Accept": "application/json"}, timeout=30,
        )
        variables = result.get("variables", [])
        name_map  = {v.get("name",  "").lower(): v["name"] for v in variables if v.get("name")}
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


# ── Public API ────────────────────────────────────────────────────────────────

async def list_catalog_items(name_filter: str = "") -> list[dict]:
    """
    Return active Service Catalog items from this SNOW instance.

    Pass a name_filter for a partial-match search (e.g. "monitoring"),
    or leave it empty to list ALL active catalog items (up to 30).

    Each returned dict has: sys_id, name, short_description, category.
    Use this to discover the right SNOW_CATALOG_ITEM_NAME / SYS_ID value.
    """
    async with httpx.AsyncClient() as client:
        return await _search_catalog_items(client, name_filter)


async def get_catalog_item_variables() -> list[dict]:
    """Return the raw variable definitions on the catalog item (name, label, type)."""
    async with httpx.AsyncClient() as client:
        catalog_sys_id = await _get_catalog_item_sys_id(client)
        result = await _try_paths(
            client, _ITEM_PATHS, "get", catalog_sys_id,
            auth=_AUTH, headers={"Accept": "application/json"}, timeout=30,
        )
    return result.get("variables", [])


async def create_sr(
    short_description: str,
    description: str,
    requested_for: str | None = None,
) -> dict:
    """
    Create a Service Catalog SR.

    Parameters
    ----------
    short_description : One-line SR summary.
    description       : Full body text.
    requested_for     : Optional override for the SNOW 'requested_for' field
                        (username or sys_id). Falls back to SNOW_REQUESTED_FOR env var.
    """
    # requested_for is optional — if empty, omit it from the body and let SNOW
    # default to the authenticated service account.
    snow_requested_for = requested_for or _REQUESTED_FOR

    async with httpx.AsyncClient() as client:
        # Step 1 — resolve catalog item sys_id (from env or auto-discovered by name)
        catalog_sys_id = await _get_catalog_item_sys_id(client)

        # Step 2 — resolve real variable names from the catalog item (cached)
        var_names = await _resolve_variable_names(client, catalog_sys_id)

        # Step 3 — order via Service Catalog (tries all 3 path variants)
        body: dict = {
            "sysparm_quantity": "1",
            "variables": {
                var_names["short_description"]: short_description,
                var_names["description"]: description,
            },
        }
        if snow_requested_for:
            # Only include if a valid SNOW username / sys_id is known.
            # Omitting it lets SNOW default to the authenticated service account.
            body["requested_for"] = snow_requested_for

        sr = await _try_paths(
            client,
            _ORDER_PATHS,
            "post",
            catalog_sys_id,
            json=body,
            auth=_AUTH,
            headers=_HEADERS,
            timeout=30,
        )
        sr_sys_id = sr["sys_id"]

        # Step 4 — fetch the RITM auto-created under the REQ
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

        # Step 5 — fetch the SCTASK auto-created under the RITM by the workflow
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
        "sr_number":      sr.get("number", sr_sys_id),
        "sr_sys_id":      sr_sys_id,
        "ritm_number":    ritm.get("number", ""),
        "ritm_sys_id":    ritm_sys_id,
        "sctask_number":  sctask.get("number", ""),
        "sctask_sys_id":  sctask.get("sys_id", ""),
        "catalog_sys_id": catalog_sys_id,
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
