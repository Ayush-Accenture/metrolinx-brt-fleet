"""ServiceNow MCP Server."""

from fastmcp import FastMCP
import snow_client

mcp = FastMCP("ServiceNow SR Server")


@mcp.tool()
async def create_device_monitoring_sr(
    short_description: str,
    description: str,
) -> dict:
    """Create a Service Request in ServiceNow via the Service Catalog.

    Returns the REQ, RITM, and SCTASK numbers created.

    Args:
        short_description: One-line summary for the SR.
        description: Full body text of the request (pre-formatted).
    """
    result = await snow_client.create_sr(short_description, description)
    return {
        "success": True,
        **result,
        "message": (
            f"Created {result['sr_number']} / {result['ritm_number']}"
            + (f" / {result['sctask_number']}" if result.get("sctask_number") else "")
        ),
    }


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
