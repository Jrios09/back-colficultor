from datetime import datetime
from app.db.mongodb import get_user_collection
from app.core.security import hash_password

async def create_default_admin() -> None:
    users = get_user_collection()

    email = "admin@colficultor.com"

    existing = await users.find_one({"email": email})
    if existing:
        return  # ya existe

    now = datetime.utcnow()
    doc = {
        "email": email,
        "full_name": "Administrador",
        "role": "admin",
        "is_active": True,
        "password_hash": hash_password("Admin123!"),  # cámbialo luego
        "created_at": now,
        "updated_at": now,
    }

    await users.insert_one(doc)