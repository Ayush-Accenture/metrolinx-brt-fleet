# SOTI MobiControl MCP Server

An MCP (Model Context Protocol) server that exposes all 16 SOTI MobiControl REST APIs as callable tools.

## File structure

```
soti-mcp-server/
├── server.py          # MCP server entry point
├── soti_client.py     # Async HTTP client + token management
├── tools.py           # Tool schemas (inputSchema) + handler functions
├── requirements.txt
├── .env.example       # Credential template
└── mcp_config.json    # Claude Desktop / MCP client config snippet
```

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set credentials (choose one approach)

# Option A – environment variables
export SOTI_BASE_URL=https://20.220.205.86/MobiControl/api
export SOTI_USERNAME=<username>
export SOTI_PASSWORD=<password>
export SOTI_CLIENT_ID=<client_id>
export SOTI_CLIENT_SECRET=<client_secret>

# Option B – .env file (requires python-dotenv)
cp .env.example .env
# edit .env, then add at top of server.py:
#   from dotenv import load_dotenv; load_dotenv()

# 3. Start the server
python server.py
```

## Connecting to an MCP client

Copy the block in `mcp_config.json` into your MCP client's configuration
(e.g. `~/Library/Application Support/Claude/claude_desktop_config.json`).
Fill in the credentials and update `cwd`.

## Available tools (16 total)

| # | Tool name | API | Used in |
|---|-----------|-----|---------|
| 1 | `get_token_api` | POST /api/token | VFO, CCMS, Function App, SMA |
| 2 | `get_token_oauth` | POST /oauth/token | VFO, CCMS, Function App, SMA |
| 3 | `get_all_devices` | GET /api/devices | Device Topology Function App |
| 4 | `get_device_info` | GET /api/devices/{deviceId} | VFO/SMA |
| 5 | `search_devices_by_reference_id` | GET /api/devices/search?groupPath=referenceId:{id} | VFO/SMA |
| 6 | `search_devices_by_group_path` | GET /api/devices/search?groupPath={path} | VFO/SMA |
| 7 | `get_last_known_location` | GET /api/devicegroups/referenceId:{id}/members/lastKnownLocation | CCMS |
| 8 | `search_devices_by_group_path_flat` | GET /api/devices/search?groupPath={}&includeSubgroups=false&verifyAndSync=false | CCMS |
| 9 | `filter_devices_by_logical_id` | GET /api/devices/search?filter=CustomData['LogicalDeviceID'] | VFO |
| 10 | `send_action_to_device` | POST /api/devices/{deviceId}/actions | VFO |
| 11 | `send_action_to_device_group_by_reference_id` | POST /api/devicegroups/referenceId:{id}/members/actions | VFO |
| 12 | `send_action_to_device_group_by_path` | POST /api/devicegroups/{path}/members/actions | VFO |
| 13 | `send_action_to_device_list` | POST /api/devices/actions | VFO |
| 14 | `delete_device` | DELETE /api/devices/{deviceId} | VFO |
| 15 | `move_device_by_id` | PUT /api/devices/{deviceId}/parentPath | VFO |
| 16 | `move_device_by_mac` | PUT /api/devices/mac:{mac}/parentPath | VFO |

## Authentication details

`SotiClient` automatically acquires and caches a bearer token before
every request. It tries `/oauth/token` first; if that fails it falls
back to `/api/token`. Tokens are refreshed 30 seconds before expiry.

The server uses `verify=False` on the HTTPS client because the SOTI
host uses a self-signed certificate. Switch to `verify=True` (or supply
a CA bundle path) in production.
