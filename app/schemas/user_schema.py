from pydantic import BaseModel

class UserRegister(BaseModel):
    email: str
    telefono: str
    password: str
    role: str

class UserLogin(BaseModel):
    email: str
    password: str