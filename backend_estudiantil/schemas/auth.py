
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Token(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type, usually 'bearer'")
    role: str = Field(default="user", description="User role (admin/user)")
    expires_in: float | None = Field(default=None, description="Expiration in seconds")

    model_config = ConfigDict(from_attributes=True)

class TokenPayload(BaseModel):
    sub: str = Field(..., description="Subject (user id)")
    exp: int = Field(..., description="Expiration timestamp (unix epoch)")
    role: str = Field(default="user", description="User role (admin/user)")

class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email for login")
    password: str = Field(..., min_length=1, description="Plain password")
