# Scheduler Job – BRT Fleet Phase 1

## Overview
A minimal Docker container that fires a `curl` POST to the Azure Durable Functions
HTTP starter every night at **12:30 AM EST** via an Azure Container Apps Job cron schedule.

## Files
| File | Purpose |
|---|---|
| `Dockerfile` | Builds the scheduler image from `mcr.microsoft.com/azure-cli:latest` |
| `trigger.sh` | Shell script executed on each cron run |

## Environment Variables
| Variable | Description | Example |
|---|---|---|
| `FUNC_APP_URL` | Base URL of the deployed Function App | `https://brt-func.azurewebsites.net` |

## Local Test (without Docker)
```bash
export FUNC_APP_URL="http://localhost:7071"
bash trigger.sh
```

## Build & Push (manual – see deploy/deploy_job.sh for full automation)
```bash
az acr build \
  --registry <ACR_NAME> \
  --image brt-scheduler:latest \
  scheduler_job/
```
