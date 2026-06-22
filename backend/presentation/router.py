"""Aggregator that includes all v1 business-layer routers."""

from fastapi import APIRouter

from backend.presentation.routers import (
    admin,
    auth,
    chat,
    conversations,
    dashboard,
    data_analyst,
    db_collector,
    db_connector,
    documents,
    domain_config,
    events,
    integrations,
    knowledge,
    metrics,
    models,
    prompts,
    reactive_config,
    reactive_credentials,
    reactive_tools,
    system,
    tools,
    users,
    webhooks,
)

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(users.router)
router.include_router(conversations.router)
router.include_router(chat.router)
router.include_router(data_analyst.router)
router.include_router(events.router)
router.include_router(dashboard.router)
router.include_router(knowledge.router)
router.include_router(documents.router)
router.include_router(models.router)
router.include_router(tools.router)
router.include_router(prompts.router)
router.include_router(reactive_config.router)
router.include_router(reactive_tools.router)
router.include_router(reactive_credentials.router)
router.include_router(system.router)
router.include_router(admin.router)
router.include_router(db_collector.router)
router.include_router(domain_config.router)
router.include_router(metrics.router)
router.include_router(webhooks.router)
router.include_router(db_connector.router)
router.include_router(integrations.router)
