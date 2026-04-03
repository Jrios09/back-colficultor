from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)

# Collation para búsquedas case-insensitive en español.
# strength=2: ignora diferencias de mayúsculas/minúsculas Y de acentos/diacríticos.
# Así "Admin@colficultor.com" y "admin@colficultor.com" los trata como duplicados.
CASE_INSENSITIVE_COLLATION = {"locale": "es", "strength": 2}


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    users = db["users"]
    password_resets = db["password_resets"]
    revoked_tokens = db["revoked_tokens"]
    productos = db["productos"]

    # ── users ──────────────────────────────────────────────────────────
    # Email único — case-insensitive
    await users.create_index(
        "email",
        unique=True,
        collation=CASE_INSENSITIVE_COLLATION,
    )
    logger.info("Índice único en users.email creado (case-insensitive)")

    # Índice compuesto para filtros (rol, estado, fecha)
    await users.create_index(
        [("is_active", 1), ("role", 1), ("created_at", -1)]
    )
    logger.info("Índice compuesto en users (is_active, role, created_at)")

    # ── password_resets ────────────────────────────────────────────────
    await password_resets.create_index("token_hash", unique=True)
    await password_resets.create_index("expires_at", expireAfterSeconds=0)
    await password_resets.create_index([("user_id", 1), ("used", 1), ("expires_at", -1)])
    logger.info("Índices en password_resets creados")

    # ── revoked_tokens ─────────────────────────────────────────────────
    await revoked_tokens.create_index("jti", unique=True)
    await revoked_tokens.create_index("expires_at", expireAfterSeconds=0)
    logger.info("Índices en revoked_tokens creados")

    # ── productos (HU-03) ───────────────────────────────────────────────
    # Búsqueda por caficultor (casi todas las queries lo usan)
    await productos.create_index("caficultor_id")
    logger.info("Índice en productos.caficultor_id creado")

    # Filtro activo por caficultor
    await productos.create_index([("caficultor_id", 1), ("is_active", 1)])
    logger.info("Índice compuesto en productos (caficultor_id, is_active) creado")

    # Búsqueda por región dentro de un caficultor
    await productos.create_index([("caficultor_id", 1), ("region", 1), ("is_active", 1)])
    logger.info("Índice compuesto en productos (caficultor_id, region, is_active) creado")

    # Ordenamiento por precio
    await productos.create_index([("caficultor_id", 1), ("precio", 1)])
    logger.info("Índice compuesto en productos (caficultor_id, precio) creado")

    # Búsqueda por nombre (parcial o completa)
    await productos.create_index("nombre")
    logger.info("Índice en productos.nombre creado")
