# BRT Fleet Movement – Phase 1

End-to-end skeleton: Azure Container Apps Job → Azure Durable Functions.

```
Azure Container Apps Job  (cron: 5:30 AM UTC / 12:30 AM EST)
         │
         │  POST /api/start?runId=BRT-YYYY-MM-DD
         ▼
Azure Functions HTTP Starter  (http_start)
         │
         │  start_new("fleet_orchestrator")
         ▼
Durable Orchestrator  (fleet_orchestrator)
         │
         │  call_activity("print_start_activity")
         ▼
Activity  (print_start_activity)
  → logs "Flow started at <UTC> | runId=<id>"
```

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Azure CLI | ≥ 2.60 | https://learn.microsoft.com/cli/azure/install-azure-cli |
| Functions Core Tools | v4 | `npm i -g azure-functions-core-tools@4` |
| Python | 3.11 | https://python.org |
| Docker (optional) | any | Only needed for local image builds; ACR Tasks handles cloud builds |

```bash
# Verify versions
az version
func --version
python3 --version
```

---

## Folder Structure

```
fleet-phase1/
├── function_app/
│   ├── function_app.py          # Starter + Orchestrator + Activity (Python v2)
│   ├── host.json                # Durable Functions task hub config
│   ├── requirements.txt
│   ├── local.settings.json.example
│   └── README.md
├── scheduler_job/
│   ├── Dockerfile               # Based on mcr.microsoft.com/azure-cli:latest
│   ├── trigger.sh               # curl POST to Function App starter
│   └── README.md
├── deploy/
│   ├── deploy_function.sh       # Step 1 – deploy Azure Functions
│   ├── deploy_job.sh            # Step 2 – build image + create Container Apps Job
│   └── test_local.sh            # Local and Azure manual trigger helpers
└── README.md                    # ← you are here
```

---

## Step-by-Step Deploy Order

> Run all scripts from the **repo root** (`fleet-phase1/`).

### Step 1 – Log in to Azure

```bash
az login
az account set --subscription "<your-subscription-id>"
```

### Step 2 – Deploy the Function App

```bash
bash deploy/deploy_function.sh
```

This creates:
- Resource group `rg-brt-fleet-phase1`
- Storage account (identity-based, no connection string secret)
- Application Insights workspace
- Linux Consumption Function App with system-assigned Managed Identity
- Deploys `function_app/` code via `func azure functionapp publish`

### Step 3 – Deploy the Container Apps Job

```bash
bash deploy/deploy_job.sh
```

This creates:
- Azure Container Registry `brtfleetacr001`
- Builds the scheduler Docker image via ACR Tasks (no local Docker required)
- Container Apps Environment
- Scheduled Container Apps Job (`30 5 * * *` UTC)
- Grants AcrPull role to the job's Managed Identity

---

## How to Manually Trigger the Job

### Option A – trigger the Function App directly (fastest)
```bash
curl -X POST \
  "https://brt-fleet-func.azurewebsites.net/api/start?runId=BRT-MANUAL-$(date +%Y-%m-%d)"
```

### Option B – trigger the Container Apps Job (tests the full path)
```bash
az containerapp job start \
  --name brt-fleet-scheduler-job \
  --resource-group rg-brt-fleet-phase1
```

### Option C – use the test helper script
```bash
# Local (requires func start running in another terminal)
bash deploy/test_local.sh local

# Azure manual trigger
bash deploy/test_local.sh azure
```

---

## How to View Logs

### Function App – Application Insights

```bash
# Last 50 traces (includes activity output)
az monitor app-insights query \
  --app brt-fleet-appinsights \
  --resource-group rg-brt-fleet-phase1 \
  --analytics-query "traces | order by timestamp desc | take 50"

# Live stream (requires app-insights extension)
az webapp log tail \
  --name brt-fleet-func \
  --resource-group rg-brt-fleet-phase1
```

### Container Apps Job

```bash
# List recent executions
az containerapp job execution list \
  --name brt-fleet-scheduler-job \
  --resource-group rg-brt-fleet-phase1 \
  --output table

# Stream logs for the most recent execution
az containerapp job logs show \
  --name brt-fleet-scheduler-job \
  --resource-group rg-brt-fleet-phase1
```

---

## DST Note

The cron expression `30 5 * * *` runs at **5:30 AM UTC**, which maps to:

| Season | Local Time |
|---|---|
| Winter (EST, UTC-5) | **12:30 AM** ✓ |
| Summer (EDT, UTC-4) | **1:30 AM** |

If strict 12:30 AM local time is required year-round, the cron must be updated seasonally:
- Winter: `30 5 * * *`
- Summer: `30 4 * * *`

Azure Container Apps Jobs do not natively support timezone-aware cron expressions.
Consider an Azure Logic App with timezone support for a production hardened schedule.

---

## What's NOT in Phase 1

- Cosmos DB / Blob Storage
- SOTI / ServiceNow / Microsoft Graph integration
- HITL (Human-in-the-Loop) approval gates
- AI/ML components
- Unit tests

These will be added in subsequent phases.
