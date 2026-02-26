"""
Configure the weekly digest cron schedule in Microsoft Foundry.

Creates (or updates) a schedule that runs the weekly_digest prompt flow
every Monday at 08:00 UTC by submitting a CommandJob that invokes pfazure.

Usage (manual):
    export AZURE_SUBSCRIPTION_ID=<sub-id>
    export AZURE_RESOURCE_GROUP=rg-compliance-advisor-prod
    export AI_FOUNDRY_WORKSPACE=aip-compliance-advisor-prod   # Microsoft Foundry project name
    python scripts/configure_weekly_schedule.py

In CI this is called automatically after prompt flows are deployed.
The step uses continue-on-error so a first-run race condition (flow not
yet fully indexed) doesn't fail the pipeline — a subsequent deploy will
resolve it.

Prerequisites:
    pip install azure-ai-ml azure-identity
"""
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

SCHEDULE_NAME   = "weekly-digest-schedule"
FLOW_NAME       = "weekly_digest"
CRON_EXPRESSION = "0 8 * * 1"   # Every Monday at 08:00 UTC


def main() -> None:
    subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
    resource_group  = os.environ.get("AZURE_RESOURCE_GROUP")
    workspace_name  = os.environ.get("AI_FOUNDRY_WORKSPACE")

    for name, value in [
        ("AZURE_SUBSCRIPTION_ID", subscription_id),
        ("AZURE_RESOURCE_GROUP",  resource_group),
        ("AI_FOUNDRY_WORKSPACE (Microsoft Foundry project)",  workspace_name),
    ]:
        if not value:
            sys.exit(f"Error: {name} environment variable is not set.")

    from azure.ai.ml import MLClient
    from azure.ai.ml.entities import CommandJob, CronTrigger, JobSchedule
    from azure.identity import DefaultAzureCredential

    log.info("Connecting to Microsoft Foundry project: %s / %s", resource_group, workspace_name)
    client = MLClient(
        credential=DefaultAzureCredential(),
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name,
    )

    # CommandJob: invokes pfazure to run the weekly_digest flow on the
    # serverless runtime — no dedicated compute cluster needed.
    job = CommandJob(
        display_name="weekly-digest-run",
        description="AI-generated compliance digest posted to Microsoft Teams.",
        command=(
            "pip install promptflow promptflow-azure --quiet && "
            f"pfazure run create "
            f"--flow {FLOW_NAME} "
            f"--runtime serverless "
            f"--subscription $AZURE_SUBSCRIPTION_ID "
            f"--resource-group $AZURE_RESOURCE_GROUP "
            f"--workspace-name $AI_FOUNDRY_WORKSPACE"
        ),
        environment="azureml://registries/azureml/environments/promptflow-runtime/versions/latest",
        compute="serverless",
        environment_variables={
            "AZURE_SUBSCRIPTION_ID": subscription_id,
            "AZURE_RESOURCE_GROUP":  resource_group,
            "AI_FOUNDRY_WORKSPACE":  workspace_name,
        },
    )

    schedule = JobSchedule(
        name=SCHEDULE_NAME,
        display_name="Weekly Compliance Digest",
        description="Runs the weekly_digest prompt flow every Monday at 08:00 UTC.",
        trigger=CronTrigger(expression=CRON_EXPRESSION, time_zone="UTC"),
        create_job=job,
        is_enabled=True,
    )

    log.info("Creating / updating schedule '%s' (cron: %s)…", SCHEDULE_NAME, CRON_EXPRESSION)
    poller = client.schedules.begin_create_or_update(schedule)
    result = poller.result()
    log.info("Schedule '%s' is %s.", result.name, "enabled" if result.is_enabled else "disabled")


if __name__ == "__main__":
    main()
