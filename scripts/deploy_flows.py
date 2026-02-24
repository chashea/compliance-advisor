"""Deploy prompt flows to the AI Foundry project using identity-based auth."""
import sys
from azure.identity import DefaultAzureCredential
from promptflow.azure import PFClient

SUBSCRIPTION_ID = "2a71b66d-0453-47ed-a081-b0863b91a2e0"
RESOURCE_GROUP = "rg-compliance-advisor-dev"
WORKSPACE_NAME = "aip-compliance-advisor-dev"

FLOWS = [
    "./prompt_flows/compliance_advisor",
    "./prompt_flows/executive_briefing",
    "./prompt_flows/weekly_digest",
]

def main():
    credential = DefaultAzureCredential()
    pf = PFClient(
        credential=credential,
        subscription_id=SUBSCRIPTION_ID,
        resource_group_name=RESOURCE_GROUP,
        workspace_name=WORKSPACE_NAME,
    )

    for flow_path in FLOWS:
        flow_name = flow_path.split("/")[-1]
        print(f"Deploying {flow_name}...")
        try:
            result = pf.flows.create_or_update(flow=flow_path)
            print(f"  ✓ {flow_name} deployed: {result.name}")
        except Exception as e:
            print(f"  ✗ {flow_name} failed: {e}")
            # Continue with remaining flows
            continue

    print("\nDone.")

if __name__ == "__main__":
    main()
