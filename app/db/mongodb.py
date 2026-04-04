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

def get_oauth_states_collection():
    """Estados OAuth temporales para protección CSRF."""
    return get_db()["oauth_states"]

def get_google_pending_collection():
    """Registros pendientes de Google (usuario nuevo sin rol asignado aún)."""
    return get_db()["google_pending"]


async def setup_collection_validators(db: AsyncIOMotorDatabase) -> None:
    """Aplica validators de esquema a las colecciones para prevenir documentos malformados."""
    import logging
    logger = logging.getLogger(__name__)
    existing_collections = await db.list_collection_names()

    try:
        await db.command({
            "collMod": "users",
            "validator": {
                "$jsonSchema": {
                    "bsonType": "object",
                    # password_hash ya no es requerido: los usuarios de Google no lo tienen
                    "required": [
                        "email",
                        "role",
                        "is_active",
                        "created_at",
                        "updated_at",
                    ],
                    "properties": {
                        "email":         {"bsonType": "string"},
                        # null para usuarios Google, string para usuarios locales
                        "password_hash": {"bsonType": ["string", "null"]},
                        "role":          {"enum": ["caficultor", "comprador", "admin"]},
                        "is_active":     {"bsonType": "bool"},
                        "full_name":     {"bsonType": ["string", "null"]},
                        # "local" | "google"
                        "provider":      {"bsonType": ["string", "null"]},
                        # Identificador único de Google (sub)
                        "google_sub":    {"bsonType": ["string", "null"]},
                        "perfil": {
                            "bsonType": ["object", "null"],
                            "properties": {
                                "ciudad":       {"bsonType": ["string", "null"]},
                                "departamento": {"bsonType": ["string", "null"]},
                                "direccion":    {"bsonType": ["string", "null"]},
                                "telefono":     {"bsonType": ["string", "null"]},
                                "preferencias": {"bsonType": ["string", "null"]},
                                "foto":         {"bsonType": ["string", "null"]},
                            }
                        },
                        "created_at":    {"bsonType": "date"},
                        "updated_at":    {"bsonType": "date"},
                    },
                }
            },
            "validationLevel": "moderate",
            "validationAction": "error",
        })
        logger.info("Validator para colección 'users' aplicado")
    except Exception as ex:
        logger.warning("No se pudo aplicar validator en 'users' (puede ya existir): %s", ex)

    # ── productos (HU-03) ─────────────────────────────────────────────
    try:
        await db.command({
            "collMod": "productos",
            "validator": {
                "$jsonSchema": {
                    "bsonType": "object",
                    "required": [
                        "caficultor_id",
                        "nombre",
                        "descripcion",
                        "precio",
                        "stock",
                        "region",
                        "is_active",
                        "created_at",
                        "updated_at",
                    ],
                    "properties": {
                        "caficultor_id": {"bsonType": "string"},
                        "nombre":        {"bsonType": "string", "minLength": 1, "maxLength": 200},
                        "descripcion":   {"bsonType": "string", "maxLength": 2000},
                        "precio":        {"bsonType": "number", "minimum": 0.01},
                        "stock":        {"bsonType": "int", "minimum": 0},
                        "region":       {"bsonType": "string", "maxLength": 100},
                        "is_active":    {"bsonType": "bool"},
                        "created_at":    {"bsonType": "date"},
                        "updated_at":    {"bsonType": "date"},
                    },
                }
            },
            "validationLevel": "moderate",
            "validationAction": "error",
        })
        logger.info("Validator para colección 'productos' aplicado")
    except Exception as ex:
        logger.warning("No se pudo aplicar validator en 'productos' (puede ya existir): %s", ex)

    # ── carritos (HU-05) ──────────────────────────────────────────────
    carritos_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["userId", "items", "updatedAt"],
            "properties": {
                "userId": {"bsonType": "string"},
                "items": {
                    "bsonType": "array",
                    "items": {
                        "bsonType": "object",
                        "required": ["productId", "cantidad"],
                        "properties": {
                            "productId": {"bsonType": "string"},
                            "cantidad": {"bsonType": "int", "minimum": 1},
                            "precioSnapshot": {"bsonType": ["number", "null"]},
                        },
                    },
                },
                "createdAt": {"bsonType": ["date", "null"]},
                "updatedAt": {"bsonType": "date"},
            },
        }
    }
    try:
        if "carritos" in existing_collections:
            await db.command({
                "collMod": "carritos",
                "validator": carritos_validator,
                "validationLevel": "moderate",
                "validationAction": "error",
            })
        else:
            await db.create_collection(
                "carritos",
                validator=carritos_validator,
                validationLevel="moderate",
                validationAction="error",
            )
        logger.info("Validator para colección 'carritos' aplicado")
    except Exception as ex:
        logger.warning("No se pudo aplicar validator en 'carritos' (puede ya existir): %s", ex)

    # ── ordenes (HU-05) ───────────────────────────────────────────────
    ordenes_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "userId",
                "items",
                "total",
                "estado",
                "createdAt",
                "updatedAt",
            ],
            "properties": {
                "userId": {"bsonType": "string"},
                "items": {
                    "bsonType": "array",
                    "items": {
                        "bsonType": "object",
                        "required": ["productId", "nombreSnapshot", "precioSnapshot", "cantidad"],
                        "properties": {
                            "productId": {"bsonType": "string"},
                            "nombreSnapshot": {"bsonType": "string"},
                            "precioSnapshot": {"bsonType": "number", "minimum": 0.01},
                            "cantidad": {"bsonType": "int", "minimum": 1},
                            "subtotal": {"bsonType": ["number", "null"]},
                        },
                    },
                },
                "total": {"bsonType": "number", "minimum": 0},
                "estado": {"bsonType": "string"},
                "createdAt": {"bsonType": "date"},
                "updatedAt": {"bsonType": "date"},
            },
        }
    }
    try:
        if "ordenes" in existing_collections:
            await db.command({
                "collMod": "ordenes",
                "validator": ordenes_validator,
                "validationLevel": "moderate",
                "validationAction": "error",
            })
        else:
            await db.create_collection(
                "ordenes",
                validator=ordenes_validator,
                validationLevel="moderate",
                validationAction="error",
            )
        logger.info("Validator para colección 'ordenes' aplicado")
    except Exception as ex:
        logger.warning("No se pudo aplicar validator en 'ordenes' (puede ya existir): %s", ex)
