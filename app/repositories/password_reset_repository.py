from datetime import datetime
from bson import ObjectId

from app.db.mongodb import get_password_reset_collection


async def create_password_reset_token(
    user_id: str,
    token_hash: str,
    expires_at: datetime,
) -> str:
    resets = get_password_reset_collection()
    now = datetime.utcnow()
    doc = {
        "user_id": ObjectId(user_id),
        "token_hash": token_hash,
        "expires_at": expires_at,
        "used": False,
        "created_at": now,
        "used_at": None,
    }
    result = await resets.insert_one(doc)
    return str(result.inserted_id)


async def get_valid_password_reset_by_token_hash(token_hash: str):
    resets = get_password_reset_collection()
    now = datetime.utcnow()
    return await resets.find_one(
        {
            "token_hash": token_hash,
            "used": False,
            "expires_at": {"$gt": now},
        }
    )


async def mark_password_reset_token_used(token_id: str, used_at: datetime | None = None) -> None:
    resets = get_password_reset_collection()
    effective_used_at = used_at or datetime.utcnow()
    await resets.update_one(
        {"_id": ObjectId(token_id)},
        {
            "$set": {
                "used": True,
                "used_at": effective_used_at,
            }
        },
    )


async def invalidate_active_tokens_for_user(user_id: str) -> None:
    resets = get_password_reset_collection()
    now = datetime.utcnow()
    await resets.update_many(
        {
            "user_id": ObjectId(user_id),
            "used": False,
            "expires_at": {"$gt": now},
        },
        {
            "$set": {
                "used": True,
                "used_at": now,
            }
        },
    )
