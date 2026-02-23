"""
Timer trigger — fires daily at 02:00 UTC and starts the Durable orchestrator.
"""
import logging
import azure.functions as func
import azure.durable_functions as df

async def main(mytimer: func.TimerRequest, starter: str) -> None:
    if mytimer.past_due:
        logging.warning("Timer trigger is running late")

    client = df.DurableOrchestrationClient(starter)
    instance_id = await client.start_new("orchestrator", None, None)
    logging.info("Started orchestration: %s", instance_id)
