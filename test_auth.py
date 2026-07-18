import os
from pathlib import Path
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth

env_path = Path('.env')
load_dotenv(env_path, override=True)

host = os.getenv("SERVICENOW_HOST").strip()
username = os.getenv("SERVICENOW_USERNAME").strip()
password = os.getenv("SERVICENOW_PASSWORD").strip()

print(f"Host: {host}")
print(f"Username: {username}")
print(f"Password length: {len(password)}")
print(f"Password ends with: {repr(password[-3:])}")

session = requests.Session()
session.auth = HTTPBasicAuth(username, password)
session.headers.update({
    "Accept": "application/json",
    "Content-Type": "application/json",
})

try:
    print("\n=== Testing Incident Table ===")
    response = session.get(f"{host}/api/now/table/incident?sysparm_limit=1", timeout=30)
    print(f"Response Status: {response.status_code}")
    if response.status_code == 200:
        print(f"SUCCESS - Incident table accessible")
    else:
        print(f"FAILED - Error: {response.text[:300]}")
    
    print("\n=== Testing Problem Table ===")
    response = session.get(f"{host}/api/now/table/problem?sysparm_limit=1", timeout=30)
    print(f"Response Status: {response.status_code}")
    if response.status_code == 200:
        print(f"SUCCESS - Problem table accessible")
    else:
        print(f"FAILED - Error: {response.text[:300]}")
        
except Exception as e:
    print(f"Request failed: {e}")
