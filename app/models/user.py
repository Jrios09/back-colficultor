from datetime import datetime
from fastapi import HTTPException
from bson import ObjectId

from app.db.mongodb import get_user_collection
from app.core.security import hash_password, verify_password
from app.schemas.user import UserCreate, UserInDB, UserPublic
from app.db.indexes import CASE_INSENSITIVE_COLLATION

def _doc_to_in_db(doc) -> UserInDB:
    doc["_id"] = str(doc["_id"])
    return UserInDB(**doc)

async def create_user(user_in: UserCreate) -> UserPublic:
    users = get_user_collection()

    if await users.find_one({"email": user_in.email}):
        raise HTTPException(status_code=400, detail="Email ya registrado")

    now = datetime.utcnow()
    doc = {
        "email": user_in.email,
        "full_name": user_in.full_name,
        "role": user_in.role.value,
        "is_active": True,
        "password_hash": hash_password(user_in.password),
        "created_at": now,
        "updated_at": now,
    }

    result = await users.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return UserPublic(**doc)

async def get_user_by_email(email: str) -> UserInDB | None:
    users = get_user_collection()
    doc = await users.find_one(
        {"email": email},
        collation=CASE_INSENSITIVE_COLLATION,
    )
    if not doc:
        return None
    return _doc_to_in_db(doc)

async def get_user_by_id(user_id: str) -> UserInDB | None:
    users = get_user_collection()
    doc = await users.find_one({"_id": ObjectId(user_id)})
    if not doc:
        return None
    return _doc_to_in_db(doc)

async def authenticate_user(email: str, password: str) -> UserInDB | None:
    user = await get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def set_user_password(user_id: str, plain_password: str) -> bool:
    users = get_user_collection()
    result = await users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "password_hash": hash_password(plain_password),
                "updated_at": datetime.utcnow(),
            }
        },
    )
    return result.matched_count == 1


async def update_user(user_id: str, full_name: str | None = None) -> UserInDB | None:
    """Actualiza campos editables de un usuario. Retorna el documento actualizado."""
    users = get_user_collection()
    updates: dict = {"updated_at": datetime.utcnow()}
    if full_name is not None:
        updates["full_name"] = full_name

    result = await users.find_one_and_update(
        {"_id": ObjectId(user_id)},
        {"$set": updates},
        return_document=True,
    )
    if not result:
        return None
    return _doc_to_in_db(result)
