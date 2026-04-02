from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

client: AsyncIOMotorClient | None = None

def get_client() -> AsyncIOMotorClient:
    global client
    if client is None:
        client = AsyncIOMotorClient(settings.MONGODB_URI)
    return client

def get_db():
    return get_client()[settings.DB_NAME]

def get_user_collection():
    return get_db()["users"]

def get_password_reset_collection():
    return get_db()["password_resets"]


async def setup_collection_validators(db: AsyncIOMotorDatabase) -> None:
    """Aplica validators de esquema a las colecciones para prevenir documentos malformados."""
    import logging
    logger = logging.getLogger(__name__)

    try:
        await db.command({
            "collMod": "users",
            "validator": {
                "$jsonSchema": {
                    "bsonType": "object",
                    "required": [
                        "email",
                        "password_hash",
                        "role",
                        "is_active",
                        "created_at",
                        "updated_at",
                    ],
                    "properties": {
                        "email":           {"bsonType": "string"},
                        "password_hash":   {"bsonType": "string"},
                        "role":            {"enum": ["caficultor", "comprador", "admin"]},
                        "is_active":      {"bsonType": "bool"},
                        "full_name":      {"bsonType": ["string", "null"]},
                        "created_at":     {"bsonType": "date"},
                        "updated_at":     {"bsonType": "date"},
                    },
                }
            },
            "validationLevel": "moderate",
            "validationAction": "error",
        })
        logger.info("Validator para colección 'users' aplicado")
    except Exception as ex:
        logger.warning("No se pudo aplicar validator en 'users' (puede ya existir): %s", ex)
