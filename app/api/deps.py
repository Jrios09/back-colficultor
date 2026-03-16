from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.auth import decode_token
from app.models.user import get_user_by_id
from app.schemas.user import UserInDB, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    data = decode_token(token)
    user = await get_user_by_id(data.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario no válido")
    return user

def require_role(*allowed: UserRole):
    async def wrapper(current: UserInDB = Depends(get_current_user)):
        if current.role not in [r.value for r in allowed]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes",
            )
        return current
    return wrapper