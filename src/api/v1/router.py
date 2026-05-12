"""Aggregator that includes all v1 business-layer routers."""

from fastapi import APIRouter

from src.api.v1.routers import (
    admin,
    auth,
    chat,
    conversations,
    db_collector,
    documents,
    events,
    knowledge,
    models,
    prompts,
    reactive_config,
    reactive_credentials,
    reactive_documents,
    reactive_knowledge,
    reactive_tools,
    system,
    tools,
    users,
)

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(users.router)
router.include_router(conversations.router)
router.include_router(chat.router)
router.include_router(events.router)
router.include_router(knowledge.router)
router.include_router(documents.router)
router.include_router(models.router)
router.include_router(tools.router)
router.include_router(prompts.router)
router.include_router(reactive_config.router)
router.include_router(reactive_knowledge.router)
router.include_router(reactive_documents.router)
router.include_router(reactive_tools.router)
router.include_router(reactive_credentials.router)
router.include_router(system.router)
router.include_router(admin.router)
router.include_router(db_collector.router)
