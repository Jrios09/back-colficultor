from datetime import datetime
from app.db.mongodb import get_user_collection
from app.core.security import hash_password
from app.db.indexes import CASE_INSENSITIVE_COLLATION

DEMO_USERS = [
    {
        "email": "admin@colficultor.com",
        "full_name": "Administrador Demo",
        "role": "admin",
        "password": "Admin123!",
    },
    {
        "email": "caficultor@colficultor.com",
        "full_name": "Caficultor Demo",
        "role": "caficultor",
        "password": "Cafe123!",
    },
    {
        "email": "comprador@colficultor.com",
        "full_name": "Comprador Demo",
        "role": "comprador",
        "password": "Compra123!",
    },
]

async def seed_demo_users() -> None:
    users = get_user_collection()
    now = datetime.utcnow()

    for u in DEMO_USERS:
        existing = await users.find_one(
            {"email": u["email"]},
            collation=CASE_INSENSITIVE_COLLATION,
        )
        if existing:
            continue

        doc = {
            "email": u["email"],
            "full_name": u["full_name"],
            "role": u["role"],
            "is_active": True,
            "password_hash": hash_password(u["password"]),
            "created_at": now,
            "updated_at": now,
        }
        await users.insert_one(doc)
