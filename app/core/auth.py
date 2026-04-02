from datetime import datetime, timedelta
from uuid import uuid4
from jose import jwt, JWTError
from app.core.config import settings
from app.schemas.auth import TokenData
from app.db.mongodb import get_db


def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    jti = str(uuid4())
    payload = {"sub": user_id, "role": role, "exp": expire, "jti": jti}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return TokenData(
            user_id=str(payload["sub"]),
            role=str(payload["role"]),
            jti=payload.get("jti"),
        )
    except JWTError:
        raise


async def revoke_token(token: str) -> None:
    """Marca el token como revocado insertándolo en la colección revoked_tokens."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        return  # token inválido, no se puede revocar algo que no existe

    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        return

    expires_at = datetime.utcfromtimestamp(exp)
    await get_db()["revoked_tokens"].insert_one({
        "jti": jti,
        "expires_at": expires_at,
    })


async def is_token_revoked(jti: str) -> bool:
    """Check if a token JTI has been revoked."""
    if not jti:
        return False
    result = await get_db()["revoked_tokens"].find_one({"jti": jti}, {"_id": 1})
    return result is not None