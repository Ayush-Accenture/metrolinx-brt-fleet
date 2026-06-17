"""
READ-ONLY ServiceNow access check.

Verifies the instance is reachable and the credentials work, using the SAME URL
shape that snow_client.get_record() uses: {SNOW_API_BASE_URL}/now/table/{table}.

Performs ONLY a GET — it creates/changes nothing and does NOT call order_now,
so it is safe to run before SNOW_CATALOG_ITEM_SYS_ID is filled in.

Run:  python check_access.py
Expected on success:  "HTTP 200 ... OK - instance reachable & authenticated".
"""
import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE = os.environ["SNOW_API_BASE_URL"].rstrip("/")
AUTH = (os.environ["SNOW_USERNAME"], os.environ["SNOW_PASSWORD"])


async def main() -> None:
    url = f"{BASE}/now/table/sc_request"
    print(f"GET {url}?sysparm_limit=1")
    async with httpx.AsyncClient() as c:
        try:
            r = await c.get(
                url,
                params={"sysparm_limit": "1", "sysparm_fields": "number"},
                auth=AUTH,
                headers={"Accept": "application/json"},
                timeout=30,
            )
            print(f"HTTP {r.status_code}")
            if r.status_code == 200:
                n = len(r.json().get("result", []))
                print(f"OK - instance reachable & authenticated. Records returned: {n}")
            else:
                print(f"Body (first 300): {r.text[:300]}")
                if r.status_code == 401:
                    print("-> 401 = reached instance, credentials rejected.")
                elif r.status_code == 404:
                    print("-> 404 = wrong path/namespace for this instance.")
        except Exception as e:
            print(f"FAILED: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
