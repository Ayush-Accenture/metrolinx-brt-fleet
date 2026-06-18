"""ServiceNow MCP Server."""

from fastmcp import FastMCP
import snow_client

mcp = FastMCP("ServiceNow SR Server")


@mcp.tool()
async def create_device_monitoring_sr(
    short_description: str,
    description: str,
    requested_for: str = "",
) -> dict:
    """Create a Service Request in ServiceNow via the Service Catalog.

    Returns the REQ, RITM, and SCTASK numbers created.

    Args:
        short_description: One-line summary for the SR.
        description: Full body text of the request (pre-formatted).
        requested_for: Optional SNOW username or sys_id to override the default
                       SNOW_REQUESTED_FOR env value.  Pass empty string to use default.
    """
    result = await snow_client.create_sr(
        short_description,
        description,
        requested_for=requested_for or None,
    )
    return {
        "success": True,
        **result,
        "message": (
            f"Created {result['sr_number']} / {result['ritm_number']}"
            + (f" / {result['sctask_number']}" if result.get("sctask_number") else "")
        ),
    }


@mcp.tool()
async def list_catalog_items(name_filter: str = "") -> dict:
    """List active Service Catalog items from this SNOW instance.

    Use this to discover the right catalog item name or sys_id when
    SNOW_CATALOG_ITEM_NAME / SNOW_CATALOG_ITEM_SYS_ID are unknown.

    Args:
        name_filter: Optional partial name to filter results (e.g. "monitoring").
                     Leave empty to return all active catalog items (up to 30).

    Returns a dict with:
        count  — number of items found
        items  — list of {sys_id, name, short_description, category}
        hint   — how to use the result to configure .env
    """
    items = await snow_client.list_catalog_items(name_filter)
    hint = (
        "Set SNOW_CATALOG_ITEM_SYS_ID=<sys_id> in .env to use a specific item, "
        "or set SNOW_CATALOG_ITEM_NAME=<name> for partial-match auto-discovery."
    )
    return {"count": len(items), "items": items, "hint": hint}


@mcp.tool()
async def get_sr_status(record_number: str) -> dict:
    """Get the status of a ServiceNow SR (REQ...) or RITM (RITM...).

    Args:
        record_number: The REQ or RITM number to look up.
    """
    record = await snow_client.get_record(record_number)
    if not record:
        return {"found": False, "record_number": record_number}
    return {"found": True, **record}


if __name__ == "__main__":
    mcp.run()
