from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRegister(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=4)

    @model_validator(mode="before")
    @classmethod
    def derive_username(cls, data: dict) -> dict:
        if isinstance(data, dict):
            if not data.get("username") and data.get("name"):
                data["username"] = data["name"]
            if not data.get("username"):
                raise ValueError("username or name is required")
        return data


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
