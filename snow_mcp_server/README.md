# ServiceNow SR — MCP Server

MCP server that raises the **Ad-hoc "Device Monitoring" Service Request** for the BRT
Fleet Movement flow, and looks up SR/RITM status. Built with FastMCP over the
ServiceNow Service Catalog + Table APIs.

> Owner: Somnath (SNOW MCP layer). This is the integrated copy in the fleet repo.
> The `.py` logic is unchanged from what Somnath delivered — only docs/helpers
> (`README.md`, `.env.example`, `check_access.py`) were added around it.

---

## TL;DR — what's left to make it work

Everything is in place **except one value**: the Service Catalog item sys_id.

1. Fill `SNOW_CATALOG_ITEM_SYS_ID` in `.env` once SNOW provides it.
2. `python check_access.py`  → should print `HTTP 200 ... OK`.
3. `python server.py`        → starts the MCP server.

That's it. Steps below have the detail, plus 3 things to confirm with the SNOW admin.

---

## Files

| File | What it is |
|------|------------|
| `server.py` | FastMCP server — exposes 2 tools (Somnath's code, unchanged) |
| `snow_client.py` | ServiceNow REST client — order catalog item + read records (unchanged) |
| `requirements.txt` | `fastmcp`, `httpx`, `python-dotenv` |
| `.env.example` | Template for credentials + the catalog sys_id |
| `check_access.py` | **Read-only** connectivity/auth check (safe to run anytime) |

## Tools exposed

| Tool | Purpose |
|------|---------|
| `create_device_monitoring_sr(short_description, description)` | Orders the catalog item → creates REQ + RITM, returns their numbers |
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
   └─ POST {BASE}/now/v1/servicecatalog/items/{SNOW_CATALOG_ITEM_SYS_ID}/order_now
        → ServiceNow creates  REQ  →  RITM  ( → SCTASK via the item's workflow )
   └─ GET  {BASE}/now/table/sc_req_item?request={req_sys_id}   (fetches the RITM)
   └─ returns { sr_number, sr_sys_id, ritm_number, ritm_sys_id }
```

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

## ⚠️ Confirm with the SNOW admin before relying on it end-to-end

These don't block setup, but should be verified on the live instance:

1. **Order endpoint namespace.** Code posts to `…/api/now/v1/servicecatalog/items/{id}/order_now`.
   ServiceNow's documented Service Catalog API is usually `…/api/**sn_sc**/servicecatalog/items/{id}/order_now`.
   If `order_now` returns 404, switch `now/v1` → `sn_sc` in `snow_client.py`.
2. **SCTASK number.** The SOP records `SCTASK…` numbers in Fleet.xlsx, but this tool
   returns the **REQ + RITM** only. If the SCTASK number is required, add one more read:
   `GET {BASE}/now/table/sc_task?sysparm_query=request_item={ritm_sys_id}`.
3. **Catalog variable names.** The order sends `variables: {short_description, description}`.
   These must match the variable names defined on the "Device Monitoring" catalog item.

## Security

- `.env` is git-ignored — do not commit real credentials.
- The password was shared in chat during setup; rotate it once configuration is stable.
