"""
MCP tool definitions and handler functions for SOTI MobiControl.

Each tool maps 1-to-1 with an API row in the specification table.
Handlers are plain async functions: (SotiClient, dict) -> Any
"""

from typing import Any, Callable, Coroutine
import mcp.types as types
from soti_client import SotiClient

# Type alias for handler signature
Handler = Callable[[SotiClient, dict], Coroutine[Any, Any, Any]]

# Helper
def _tool(name: str, description: str, properties: dict, required: list[str]) -> types.Tool:
    return types.Tool(
        name=name,
        description=description,
        inputSchema={
            "type": "object",
            "properties": properties,
            "required": required,
        },
    )

# Tool definitions (schema)
TOOL_DEFINITIONS: list[types.Tool] = [
    # Authentication
    _tool(
        name="get_token_api",
        description="[S.N.1] Acquire an access token via POST /api/token (legacy endpoint). Used by VFO, CCMS, Function App, SMA.",
        properties={},
        required=[],
    ),

    _tool(
        name="get_token_oauth",
        description="[S.N.2] Acquire an access token via POST /oauth/token (OAuth2 endpoint). Used by VFO, CCMS, Function App, SMA.",
        properties={},
        required=[],
    ),

    # Device reads
    _tool(
        name="get_all_devices",
        description="[S.N.3] GET /api/devices?top=N&skip=N – retrieve devices with pagination. Used by Device Topology Function App.",
        properties={
            "top":  {"type": "integer", "description": "Max devices to return (default 5000)."},
            "skip": {"type": "integer", "description": "Devices to skip for pagination (default 0)."},
        },
        required=[],
    ),

    _tool(
        name="get_device_info",
        description="[S.N.4] GET /api/devices/{deviceId} – get information for a single device. Used by VFO/SMA.",
        properties={
            "device_id": {"type": "string", "description": "The unique device identifier."},
        },
        required=["device_id"],
    ),

    _tool(
        name="search_devices_by_reference_id",
        description="[S.N.5] GET /api/devices/search?groupPath=referenceId:{referenceId} – search devices by reference ID. Used by VFO/SMA.",
        properties={
            "reference_id": {"type": "string", "description": "The reference ID to search for."},
        },
        required=["reference_id"],
    ),

    _tool(
        name="search_devices_by_group_path",
        description="[S.N.6] GET /api/devices/search?groupPath={path} – search devices by group path. Used by VFO/SMA.",
        properties={
            "path": {"type": "string", "description": "Group path to search (e.g. //All Devices/MyGroup)."},
        },
        required=["path"],
    ),

    _tool(
        name="get_last_known_location",
        description="[S.N.7] GET /api/devicegroups/referenceId:{referenceId}/members/lastKnownLocation – get last known location for a device group. Used by CCMS.",
        properties={
            "reference_id": {"type": "string", "description": "Reference ID of the device group."},
        },
        required=["reference_id"],
    ),

    _tool(
        name="search_devices_by_group_path_flat",
        description="[S.N.8] GET /api/devices/search?groupPath={path}&includeSubgroups=false&verifyAndSync=false – CCMS flat group search.",
        properties={
            "path":              {"type": "string",  "description": "Group path to search."},
            "include_subgroups": {"type": "boolean", "description": "Include subgroups in results. Default false."},
            "verify_and_sync":   {"type": "boolean", "description": "Verify and sync before returning. Default false."},
        },
        required=["path"],
    ),

    _tool(
        name="search_devices_by_name",
        description="GET /api/devices/search?filter=DeviceName eq '{name}' – find a device by its display name (e.g. BRT_DCU_0601_1). Use this to look up a specific device and get its current group path.",
        properties={
            "device_name": {"type": "string", "description": "The device display name to search for (exact match)."},
        },
        required=["device_name"],
    ),

    _tool(
        name="filter_devices_by_logical_id",
        description="[S.N.9] GET /api/devices/search?filter=CustomData['LogicalDeviceID'] – filter devices by Logical Device ID. Used by VFO.",
        properties={
            "logical_device_id": {"type": "string", "description": "The LogicalDeviceID custom data value to filter on."},
        },
        required=["logical_device_id"],
    ),

    # Device actions

    _tool(
        name="send_action_to_device",
        description="[S.N.10] POST /api/devices/{deviceId}/actions – send an action to a single device. Used by VFO.",
        properties={
            "device_id": {"type": "string", "description": "Target device ID."},
            "action":    {
                "type": "object",
                "description": "Action payload (e.g. {\"ActionType\": \"LockDevice\"}).",
            },
        },
        required=["device_id", "action"],
    ),

    _tool(
        name="send_action_to_device_group_by_reference_id",
        description="POST /api/devicegroups/referenceId:{referenceId}/members/actions – send action to a device group identified by reference ID.",
        properties={
            "reference_id": {"type": "string", "description": "Reference ID of the target device group."},
            "action":       {"type": "object", "description": "Action payload."},
        },
        required=["reference_id", "action"],
    ),

    _tool(
        name="send_action_to_device_group_by_path",
        description="POST /api/devicegroups/{path}/members/actions – send action to a device group identified by path.",
        properties={
            "path":   {"type": "string", "description": "Group path of the target device group."},
            "action": {"type": "object", "description": "Action payload."},
        },
        required=["path", "action"],
    ),

    _tool(
        name="send_action_to_device_list",
        description=" POST /api/devices/actions – send an action to a list of devices (device IDs embedded in action payload).",
        properties={
            "action": {
                "type": "object",
                "description": "Action payload including target device list (e.g. {\"DeviceIds\": [...], \"ActionType\": \"...\"}).",
            },
        },
        required=["action"],
    ),

    # Device mutations
    _tool(
        name="delete_device",
        description="DELETE /api/devices/{deviceId} – delete a device from MobiControl.",
        properties={
            "device_id": {"type": "string", "description": "ID of the device to delete."},
        },
        required=["device_id"],
    ),

    _tool(
        name="move_device_by_id",
        description="PUT /api/devices/{deviceId}/parentPath – move a device to a new parent group using device ID.",
        properties={
            "device_id":   {"type": "string", "description": "ID of the device to move."},
            "parent_path": {"type": "string", "description": "Destination group path."},
        },
        required=["device_id", "parent_path"],
    ),

    _tool(
        name="move_device_by_mac",
        description="PUT /api/devices/mac:{mac}/parentPath – move a device to a new parent group using MAC address.",
        properties={
            "mac_address": {"type": "string", "description": "MAC address of the device (e.g. 00:1A:2B:3C:4D:5E)."},
            "parent_path": {"type": "string", "description": "Destination group path."},
        },
        required=["mac_address", "parent_path"],
    ),

    _tool(
        name="rename_device",
        description="PUT /api/devices/{deviceId} – rename a device by updating its DeviceName. Used to add LTM_ prefix when moving Prod→LTM, or strip it when moving LTM→Prod.",
        properties={
            "device_id": {"type": "string", "description": "The unique device identifier."},
            "new_name":  {"type": "string", "description": "The new device name (e.g. LTM_BRT_DCU_1587_1 or BRT_DCU_1587_1)."},
        },
        required=["device_id", "new_name"],
    ),
]

# Handler implementations
async def _get_token_api(client: SotiClient, args: dict) -> Any:
    return await client.get_token_api()

async def _get_token_oauth(client: SotiClient, args: dict) -> Any:
    return await client.get_token_oauth()

async def _get_all_devices(client: SotiClient, args: dict) -> Any:
    return await client.get_all_devices(
        top=int(args.get("top", 5000)),
        skip=int(args.get("skip", 0)),
    )

async def _get_device_info(client: SotiClient, args: dict) -> Any:
    return await client.get_device_info(args["device_id"])

async def _search_devices_by_reference_id(client: SotiClient, args: dict) -> Any:
    return await client.search_devices_by_reference_id(args["reference_id"])

async def _search_devices_by_group_path(client: SotiClient, args: dict) -> Any:
    return await client.search_devices_by_group_path(args["path"])

async def _get_last_known_location(client: SotiClient, args: dict) -> Any:
    return await client.get_last_known_location(args["reference_id"])

async def _search_devices_by_group_path_flat(client: SotiClient, args: dict) -> Any:
    return await client.search_devices_by_group_path_flat(
        path=args["path"],
        include_subgroups=args.get("include_subgroups", False),
        verify_and_sync=args.get("verify_and_sync", False),
    )

async def _search_devices_by_name(client: SotiClient, args: dict) -> Any:
    return await client.search_devices_by_name(args["device_name"])

async def _filter_devices_by_logical_id(client: SotiClient, args: dict) -> Any:
    return await client.filter_devices_by_logical_id(args["logical_device_id"])

async def _send_action_to_device(client: SotiClient, args: dict) -> Any:
    return await client.send_action_to_device(args["device_id"], args["action"])

async def _send_action_to_device_group_by_reference_id(client: SotiClient, args: dict) -> Any:
    return await client.send_action_to_device_group_by_reference_id(
        args["reference_id"], args["action"]
    )

async def _send_action_to_device_group_by_path(client: SotiClient, args: dict) -> Any:
    return await client.send_action_to_device_group_by_path(args["path"], args["action"])

async def _send_action_to_device_list(client: SotiClient, args: dict) -> Any:
    return await client.send_action_to_device_list(args["action"])

async def _delete_device(client: SotiClient, args: dict) -> Any:
    return await client.delete_device(args["device_id"])

async def _move_device_by_id(client: SotiClient, args: dict) -> Any:
    return await client.move_device_by_id(args["device_id"], args["parent_path"])

async def _move_device_by_mac(client: SotiClient, args: dict) -> Any:
    return await client.move_device_by_mac(args["mac_address"], args["parent_path"])

async def _rename_device(client: SotiClient, args: dict) -> Any:
    return await client.rename_device(args["device_id"], args["new_name"])

# Dispatch map  {tool_name: handler_function}
TOOL_HANDLERS: dict[str, Handler] = {
    "get_token_api":                               _get_token_api,
    "get_token_oauth":                             _get_token_oauth,
    "get_all_devices":                             _get_all_devices,
    "get_device_info":                             _get_device_info,
    "search_devices_by_reference_id":              _search_devices_by_reference_id,
    "search_devices_by_group_path":                _search_devices_by_group_path,
    "get_last_known_location":                     _get_last_known_location,
    "search_devices_by_group_path_flat":           _search_devices_by_group_path_flat,
    "search_devices_by_name":                      _search_devices_by_name,
    "filter_devices_by_logical_id":                _filter_devices_by_logical_id,
    "send_action_to_device":                       _send_action_to_device,
    "send_action_to_device_group_by_reference_id": _send_action_to_device_group_by_reference_id,
    "send_action_to_device_group_by_path":         _send_action_to_device_group_by_path,
    "send_action_to_device_list":                  _send_action_to_device_list,
    "delete_device":                               _delete_device,
    "move_device_by_id":                           _move_device_by_id,
    "move_device_by_mac":                          _move_device_by_mac,
    "rename_device":                               _rename_device,
}
