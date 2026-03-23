from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)

async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    users = db["users"]
    password_resets = db["password_resets"]

    # Email único
    await users.create_index("email", unique=True)
    logger.info("Índice único en users.email creado")

    # Índice compuesto útil para filtros (opcional)
    await users.create_index(
        [("is_active", 1), ("role", 1), ("created_at", -1)]
    )
    logger.info("Índice compuesto en users (is_active, role, created_at)")

    # Índices para recuperación de contraseña
    await password_resets.create_index("token_hash", unique=True)
    await password_resets.create_index("expires_at", expireAfterSeconds=0)
    await password_resets.create_index([("user_id", 1), ("used", 1), ("expires_at", -1)])
    logger.info("Índices en password_resets creados")
