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


async def create_sr(short_description: str, description: str) -> dict:
    async with httpx.AsyncClient() as client:
        # Order via Service Catalog — creates REQ + RITM automatically
        order_resp = await client.post(
            f"{_BASE_URL}/now/v1/servicecatalog/items/{_CATALOG_ITEM_SYS_ID}/order_now",
            json={
                "sysparm_quantity": "1",
                "requested_for": _REQUESTED_FOR,
                "variables": {
                    "short_description": short_description,
                    "description": description,
                },
            },
            auth=_AUTH,
            headers=_HEADERS,
            timeout=30,
        )
        order_resp.raise_for_status()
        sr = order_resp.json()["result"]
        sr_sys_id = sr["sys_id"]

        # Fetch the RITM auto-created under the SR
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

    return {
        "sr_number": sr.get("number", sr_sys_id),
        "sr_sys_id": sr_sys_id,
        "ritm_number": ritm.get("number", ""),
        "ritm_sys_id": ritm.get("sys_id", ""),
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
