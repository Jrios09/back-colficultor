from datetime import datetime, timedelta
from jose import jwt, JWTError
from app.core.config import settings
from app.schemas.auth import TokenData

def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": user_id, "role": role, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return TokenData(user_id=str(payload["sub"]), role=str(payload["role"]))
    except JWTError:
        raise