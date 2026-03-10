from fastapi import APIRouter
from app.controllers import auth_controller
from app.schemas.user_schema import UserRegister, UserLogin

router = APIRouter()

@router.post("/register")
def register(user: UserRegister):
    return auth_controller.register(user)

@router.post("/login")
def login(user: UserLogin):
    return auth_controller.login(user)

@router.post("/logout")
def logout():
    return auth_controller.logout()