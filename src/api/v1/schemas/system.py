from pydantic import BaseModel


class SystemStats(BaseModel):
    active_users: int
    total_conversations: int
    status: str = "healthy"
