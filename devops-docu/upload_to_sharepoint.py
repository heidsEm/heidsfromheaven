import os
import requests
from msal import ConfidentialClientApplication

tenant_id = os.environ["TENANT_ID"]
client_id = os.environ["CLIENT_ID"]
client_secret = os.environ["CLIENT_SECRET"]
site = os.environ["SHAREPOINT_SITE"]
doc_lib = os.environ["SHAREPOINT_DOC_LIB"]

# Get access token
authority = f"https://login.microsoftonline.com/{tenant_id}"
app = ConfidentialClientApplication(client_id, authority=authority, client_credential=client_secret)
token = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])["access_token"]

# Upload file (example, adjust path as needed)
headers = {"Authorization": f"Bearer {token}"}
file_path = "output.docx"
file_name = os.path.basename(file_path)

# Example endpoint (replace with your actual site/drive/folder)
url = f"https://graph.microsoft.com/v1.0/sites/{site}/drive/root:/{doc_lib}/{file_name}:/content"

with open(file_path, "rb") as f:
    response = requests.put(url, headers=headers, data=f)
    response.raise_for_status()

print("Upload complete:", response.json())