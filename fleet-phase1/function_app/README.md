# Function App – BRT Fleet Phase 1

## Overview
Azure Durable Functions skeleton (Python v2 model).

| Component | Name | Trigger |
|---|---|---|
| HTTP Starter | `http_start` | `POST /api/start?runId=<id>` |
| Orchestrator | `fleet_orchestrator` | Called by starter |
| Activity | `print_start_activity` | Called by orchestrator |

## Local Development

### Prerequisites
- Python 3.11
- [Azure Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local)
- Azurite (local storage emulator) **or** a real Azure Storage connection string

### Steps

```bash
# 1. Navigate to this folder
cd fleet-phase1/function_app

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and edit local settings
cp local.settings.json.example local.settings.json
# Edit AzureWebJobsStorage – use "UseDevelopmentStorage=true" with Azurite

# 5. Start Azurite (in a separate terminal)
azurite --silent --location /tmp/azurite --debug /tmp/azurite.log

# 6. Start the function host
func start
```

The starter endpoint will be available at:
`http://localhost:7071/api/start`

### Manual test
```bash
curl -X POST "http://localhost:7071/api/start?runId=BRT-TEST-001"
```
