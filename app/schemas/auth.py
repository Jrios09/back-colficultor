from pydantic import BaseModel, EmailStr

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: str
    role: str
    jti: str | None = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str