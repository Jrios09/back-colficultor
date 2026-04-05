from datetime import datetime
from fastapi import HTTPException
from bson import ObjectId

from app.db.mongodb import get_user_collection
from app.core.security import hash_password, verify_password
from app.schemas.user import UserCreate, UserInDB, UserPublic, UserRole
from app.db.indexes import CASE_INSENSITIVE_COLLATION

def _doc_to_in_db(doc) -> UserInDB:
    doc["_id"] = str(doc["_id"])
    # Aplanar el objeto perfil embebido si existe en MongoDB
    if "perfil" in doc and isinstance(doc["perfil"], dict):
        perfil = doc.pop("perfil")
        for key, value in perfil.items():
            doc[f"perfil_{key}"] = value
            
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
    # Los usuarios de Google no tienen contraseña local
    if not user.password_hash:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def get_user_by_google_sub(google_sub: str) -> UserInDB | None:
    """Busca un usuario por su identificador único de Google (sub)."""
    users = get_user_collection()
    doc = await users.find_one({"google_sub": google_sub})
    if not doc:
        return None
    return _doc_to_in_db(doc)


async def create_google_user(
    email: str,
    full_name: str,
    google_sub: str,
    role: UserRole,
    picture: str | None = None,
) -> UserPublic:
    """Crea un usuario nuevo registrado mediante Google OAuth.
    No genera password_hash — el usuario solo puede acceder vía Google.
    """
    users = get_user_collection()

    # Doble verificación: el email no debe existir (race condition)
    if await users.find_one({"email": email}, collation=CASE_INSENSITIVE_COLLATION):
        raise HTTPException(status_code=400, detail="Email ya registrado")

    now = datetime.utcnow()
    doc = {
        "email": email,
        "full_name": full_name,
        "role": role.value,
        "is_active": True,
        "password_hash": None,
        "provider": "google",
        "google_sub": google_sub,
        "created_at": now,
        "updated_at": now,
    }
    if picture:
        doc["perfil"] = {"foto": picture}

    result = await users.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return UserPublic(**doc)


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


async def update_user(
    user_id: str,
    full_name: str | None = None,
    perfil_ciudad: str | None = None,
    perfil_departamento: str | None = None,
    perfil_direccion: str | None = None,
    perfil_telefono: str | None = None,
    perfil_preferencias: str | None = None,
) -> UserInDB | None:
    """
    Actualiza campos editables del perfil de un usuario.
    Retorna el documento actualizado o None si el usuario no existe.
    Nunca modifica role, is_active o password_hash.
    """
    users = get_user_collection()
    updates: dict = {"updated_at": datetime.utcnow()}

    if full_name is not None:
        updates["full_name"] = full_name

    # Campos del perfil embebido (parcial — solo los no-nulos se actualizan)
    perfil_fields = {
        "perfil.ciudad": perfil_ciudad,
        "perfil.departamento": perfil_departamento,
        "perfil.direccion": perfil_direccion,
        "perfil.telefono": perfil_telefono,
        "perfil.preferencias": perfil_preferencias,
    }
    for field, value in perfil_fields.items():
        if value is not None:
            updates[field] = value

    result = await users.find_one_and_update(
        {"_id": ObjectId(user_id)},
        {"$set": updates},
        return_document=True,
    )
    if not result:
        return None
    return _doc_to_in_db(result)


async def list_active_user_ids_by_role(role: UserRole | str) -> list[str]:
    users = get_user_collection()
    role_value = role.value if isinstance(role, UserRole) else str(role)
    cursor = users.find(
        {"role": role_value, "is_active": True},
        {"_id": 1},
    )
    docs = await cursor.to_list(length=None)
    return [str(doc["_id"]) for doc in docs]


def _to_public(user_in_db: UserInDB) -> UserPublic:
    return UserPublic(**user_in_db.dict(by_alias=True, exclude={"password_hash"}))


async def list_users_admin(
    *,
    role: UserRole | str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    limit: int = 200,
) -> list[UserPublic]:
    users = get_user_collection()
    query: dict = {}
    if role is not None:
        query["role"] = role.value if isinstance(role, UserRole) else str(role)
    if is_active is not None:
        query["is_active"] = bool(is_active)
    if search:
        term = str(search).strip()
        if term:
            query["$or"] = [
                {"email": {"$regex": term, "$options": "i"}},
                {"full_name": {"$regex": term, "$options": "i"}},
            ]

    cursor = users.find(query).sort("created_at", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    result: list[UserPublic] = []
    for doc in docs:
        in_db = _doc_to_in_db(doc)
        result.append(_to_public(in_db))
    return result


async def set_user_role(*, user_id: str, role: UserRole) -> UserPublic | None:
    if not ObjectId.is_valid(user_id):
        return None
    users = get_user_collection()
    updated = await users.find_one_and_update(
        {"_id": ObjectId(user_id)},
        {"$set": {"role": role.value, "updated_at": datetime.utcnow()}},
        return_document=True,
    )
    if not updated:
        return None
    return _to_public(_doc_to_in_db(updated))


async def delete_user_permanently(*, user_id: str) -> bool:
    if not ObjectId.is_valid(user_id):
        return False
    users = get_user_collection()
    result = await users.delete_one({"_id": ObjectId(user_id)})
    return result.deleted_count == 1
