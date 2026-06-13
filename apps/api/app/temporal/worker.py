import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.temporal.activities import (
    create_approval_request_activity,
    create_memory_update_proposals_activity,
    create_or_load_research_plan_activity,
    discover_competitors_activity,
    discover_sources_activity,
    embed_evidence_activity,
    finalize_sprint_activity,
    ingest_sources_activity,
    persist_memory_update_activity,
    run_langgraph_research_activity,
    run_langsmith_eval_activity,
    wait_for_optional_source_competitor_review_activity,
)
from app.temporal.workflows import ResearchSprintWorkflow

logger = logging.getLogger(__name__)
TEMPORAL_CONNECT_ATTEMPTS = 30
TEMPORAL_CONNECT_RETRY_SECONDS = 2


async def run_worker() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    client: Client | None = None
    for attempt in range(1, TEMPORAL_CONNECT_ATTEMPTS + 1):
        try:
            client = await Client.connect(
                settings.temporal_address,
                namespace=settings.temporal_namespace,
            )
            break
        except Exception:
            if attempt == TEMPORAL_CONNECT_ATTEMPTS:
                logger.exception(
                    "Temporal worker could not connect after %s attempts.",
                    TEMPORAL_CONNECT_ATTEMPTS,
                )
                raise
            logger.info(
                "Temporal worker waiting for server address=%s attempt=%s/%s",
                settings.temporal_address,
                attempt,
                TEMPORAL_CONNECT_ATTEMPTS,
            )
            await asyncio.sleep(TEMPORAL_CONNECT_RETRY_SECONDS)

    if client is None:
        raise RuntimeError("Temporal worker failed to initialize a client.")

    logger.info(
        "Starting Temporal worker task_queue=%s namespace=%s address=%s",
        settings.temporal_task_queue,
        settings.temporal_namespace,
        settings.temporal_address,
    )
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[ResearchSprintWorkflow],
        activities=[
            create_or_load_research_plan_activity,
            create_approval_request_activity,
            discover_sources_activity,
            discover_competitors_activity,
            wait_for_optional_source_competitor_review_activity,
            ingest_sources_activity,
            embed_evidence_activity,
            run_langgraph_research_activity,
            run_langsmith_eval_activity,
            create_memory_update_proposals_activity,
            persist_memory_update_activity,
            finalize_sprint_activity,
        ],
    )
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
