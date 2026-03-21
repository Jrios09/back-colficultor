from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.schemas.user import UserCreate, UserPublic
from app.schemas.auth import Token
from app.schemas.password_recovery import (
    ForgotPasswordRequest,
    GenericMessageResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    ResetPasswordValidateResponse,
)
from app.models.user import create_user, authenticate_user
from app.core.auth import create_access_token
from app.services.password_recovery_service import (
    request_password_reset,
    reset_password_with_token,
    validate_reset_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", response_model=UserPublic)
async def register(user_in: UserCreate):
    return await create_user(user_in)

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )
    token = create_access_token(user_id=user.id, role=user.role.value)
    return Token(access_token=token)


@router.post("/forgot-password", response_model=GenericMessageResponse)
async def forgot_password(payload: ForgotPasswordRequest, request: Request):
    message = await request_password_reset(
        email=payload.email,
        client_ip=request.client.host if request.client else None,
    )
    return GenericMessageResponse(message=message)


@router.get("/reset-password/validate", response_model=ResetPasswordValidateResponse)
async def validate_password_reset_token(
    token: str = Query(..., min_length=20, max_length=512),
):
    await validate_reset_token(token)
    return ResetPasswordValidateResponse(valid=True, message="Token válido")


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(payload: ResetPasswordRequest):
    message = await reset_password_with_token(
        token=payload.token,
        new_password=payload.new_password,
    )
    return ResetPasswordResponse(message=message)
