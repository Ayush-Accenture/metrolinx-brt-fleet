# ServiceNow SR — MCP Server

MCP server that raises the **Ad-hoc "Device Monitoring" Service Request** for the BRT
Fleet Movement flow, and looks up SR/RITM status. Built with FastMCP over the
ServiceNow Service Catalog + Table APIs.

> Owner: Somnath (SNOW MCP layer). This is the integrated copy in the fleet repo,
> alongside `soti_mcp_server/`. The `.py` logic is unchanged from Somnath's delivery —
> only docs/helpers (`README.md`, `.env.example`, `check_access.py`) were added around it.

---

## TL;DR — what's left to make it work

Everything is in place **except one value**: the Service Catalog item sys_id.

1. Fill `SNOW_CATALOG_ITEM_SYS_ID` in `.env` once SNOW provides it.
2. `python check_access.py`  → should print `HTTP 200 ... OK`.
3. `python server.py`        → starts the MCP server.

That's it.

---

## Files

| File | What it is |
|------|------------|
| `server.py` | FastMCP server — exposes 2 tools (Somnath's code, unchanged) |
| `snow_client.py` | ServiceNow REST client — catalog order + record reads (unchanged) |
| `requirements.txt` | `fastmcp`, `httpx`, `python-dotenv` |
| `.env.example` | Template for credentials + the catalog sys_id |
| `check_access.py` | **Read-only** connectivity/auth check (safe to run anytime) |

## Tools exposed

| Tool | Purpose |
|------|---------|
| `create_device_monitoring_sr(short_description, description)` | Orders the catalog item → creates **REQ + RITM + SCTASK**, returns all three numbers |
| `get_sr_status(record_number)` | Looks up a `REQ...` or `RITM...` record |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # then fill in the values
python check_access.py      # READ-ONLY: confirms instance + credentials work
python server.py            # starts the MCP server
```

### Environment variables (`.env`)

| Var | Notes |
|-----|-------|
| `SNOW_API_BASE_URL` | Instance URL **including** trailing `/api` (client appends `/now/...`). e.g. `https://<instance>.service-now.com/api` |
| `SNOW_USERNAME` / `SNOW_PASSWORD` | Service account |
| `SNOW_CATALOG_ITEM_SYS_ID` | **The one value still needed** — sys_id of the "Device Monitoring" catalog item to order |
| `SNOW_REQUESTED_FOR` | Who the SR is requested for (sys_id / user id) |

> **Never commit `.env`.** It holds the password and is git-ignored. Only `.env.example` is committed.

## How the SR is created (flow)

```
create_device_monitoring_sr(short_description, description)
   ├─ resolve the catalog item's real variable names      (GET item, cached per session)
   ├─ POST order_now   — auto-tries now/v1 → now/v2 → sn_sc  →  REQ
   ├─ GET sc_req_item?request={req_sys_id}                   →  RITM
   └─ GET sc_task?request_item={ritm_sys_id}                 →  SCTASK
   returns { sr_number, ritm_number, sctask_number, sr_sys_id, ritm_sys_id, sctask_sys_id, variables_used }
```

The earlier open questions are now **handled in code**:
- **order_now namespace** — tries the three known variants and uses whichever responds.
- **SCTASK number** — fetched in Step 4 (this is the number recorded in Fleet.xlsx).
- **catalog variable names** — resolved from the item's metadata, with `short_description`/`description` defaults as fallback.

Residual caveats (only verifiable once the sys_id is in and a real order runs):
- assumes the catalog item's workflow actually generates an SCTASK under the RITM;
- assumes one of the three namespace variants is enabled on the instance.

### Where `short_description` / `description` come from

This server does **not** generate the SR content — the **orchestrator** (fleet-agents)
builds the two strings from the reconciliation result (which buses moved, and in which
direction) per the SOP format, then calls this tool. Example `description`:

```
Contact Type: Device Monitoring
Note: This is device movement and not device deletion. Please do not remove these devices from SNOW.

List of BRT vehicles moved from LTM to PROD:
1234
1235

List of BRT vehicles moved from PROD to LTM:
9001
```

(If there is no device movement, the orchestrator does not call this tool — per SOP, no SR.)

## Security

- `.env` is git-ignored — do not commit real credentials.
- The password was shared in chat during setup; rotate it once configuration is stable.
