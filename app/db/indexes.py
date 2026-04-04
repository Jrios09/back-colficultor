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
    carritos = db["carritos"]
    ordenes = db["ordenes"]

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

    # Índices para catálogo público (HU-04)
    await productos.create_index("is_active")
    await productos.create_index("precio")
    await productos.create_index("region")
    await productos.create_index("origen")
    await productos.create_index([("is_active", 1), ("region", 1), ("precio", 1)])
    await productos.create_index([("is_active", 1), ("origen", 1), ("precio", 1)])
    logger.info("Índices de catálogo público en productos creados")

    # ── carritos (HU-05) ───────────────────────────────────────────────
    # Un único carrito por usuario
    await carritos.create_index("userId", unique=True)
    await carritos.create_index("updatedAt")
    logger.info("Índices en carritos creados")

    # ── ordenes (HU-05) ────────────────────────────────────────────────
    await ordenes.create_index("userId")
    await ordenes.create_index("estado")
    await ordenes.create_index("createdAt")
    logger.info("Índices en ordenes creados")

    # ── oauth_states (Google OAuth CSRF) ───────────────────────────────
    # Cada state es de un solo uso; expira a los 10 minutos automáticamente
    oauth_states = db["oauth_states"]
    await oauth_states.create_index("state", unique=True)
    await oauth_states.create_index("expires_at", expireAfterSeconds=0)
    logger.info("Índices en oauth_states creados")

    # ── google_pending (registro pendiente de rol) ─────────────────────
    # Token temporal que guarda info del usuario Google hasta que seleccione rol
    # Expira a los 15 minutos automáticamente
    google_pending = db["google_pending"]
    await google_pending.create_index("temp_token_hash", unique=True)
    await google_pending.create_index("expires_at", expireAfterSeconds=0)
    logger.info("Índices en google_pending creados")
