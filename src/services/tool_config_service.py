"""ToolConfig service — CRUD for individual tool configurations."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.tool import ToolConfigCreate, ToolConfigUpdate
from src.persistencia.models.tool_config import ToolConfig
from src.persistencia.repositories.tool_repository import ToolRepository
from src.services.base_crud_service import BaseCRUDService


class ToolConfigService(BaseCRUDService[ToolConfig, ToolConfigCreate, ToolConfigUpdate]):
    model_class = ToolConfig
    repo_class = ToolRepository

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
