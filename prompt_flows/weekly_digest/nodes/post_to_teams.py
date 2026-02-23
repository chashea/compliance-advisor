"""
Post the generated summary to a Microsoft Teams channel via Incoming Webhook.
The webhook URL is retrieved from Key Vault — never passed as a plain input.
"""
import json
import os
import requests
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient


def _get_webhook_url() -> str:
    """Retrieve the Teams webhook URL from Key Vault via managed identity."""
    kv_url = os.environ["KEY_VAULT_URL"]
    client = SecretClient(vault_url=kv_url, credential=DefaultAzureCredential())
    return client.get_secret("teams-webhook-url").value


def post_to_teams(summary: str) -> dict:
    webhook_url = _get_webhook_url()

    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "Weekly Compliance Digest",
                            "weight": "Bolder",
                            "size": "Medium",
                        },
                        {
                            "type": "TextBlock",
                            "text": summary,
                            "wrap": True,
                        },
                    ],
                },
            }
        ],
    }

    resp = requests.post(
        webhook_url,
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=15,
    )
    return {"success": resp.status_code == 200, "status_code": resp.status_code}
