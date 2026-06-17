# Temporary script to discover Azure AI Foundry workspace connection string
import os
import requests
import sys

# Ensure Azure CLI is on PATH for AzureCliCredential
az_wbin = r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin"
if az_wbin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = az_wbin + ";" + os.environ.get("PATH", "")

from azure.identity import AzureCliCredential

try:
    cred = AzureCliCredential()
    token = cred.get_token("https://management.azure.com/.default").token
    headers = {"Authorization": "Bearer " + token}
    sub = "074c201a-554f-4966-a1c3-087b2286c878"
    url = f"https://management.azure.com/subscriptions/{sub}/providers/Microsoft.MachineLearningServices/workspaces?api-version=2024-04-01"
    r = requests.get(url, headers=headers)
    print("HTTP Status:", r.status_code)
    data = r.json()
    workspaces = data.get("value", [])
    print("Workspace count:", len(workspaces))
    for ws in workspaces:
        name = ws.get("name", "?")
        loc = ws.get("location", "?")
        rg = ws["id"].split("/resourceGroups/")[1].split("/")[0]
        disc = ws.get("properties", {}).get("discoveryUrl", "")
        print(f"Name: {name}")
        print(f"  Location: {loc}")
        print(f"  ResourceGroup: {rg}")
        print(f"  DiscoveryUrl: {disc}")
        # Build connection string
        if disc:
            # discoveryUrl is like https://canadacentral.api.azureml.ms/discovery
            endpoint = disc.replace("/discovery", "").replace("https://", "")
            conn_str = f"{endpoint};{sub};{rg};{name}"
            print(f"  ConnectionString: {conn_str}")
        print()
except Exception as e:
    print("Error:", e, file=sys.stderr)
    raise
