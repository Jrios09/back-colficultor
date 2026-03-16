from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)

async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    users = db["users"]

    # Email único
    await users.create_index("email", unique=True)
    logger.info("Índice único en users.email creado")

    # Índice compuesto útil para filtros (opcional)
    await users.create_index(
        [("is_active", 1), ("role", 1), ("created_at", -1)]
    )
    logger.info("Índice compuesto en users (is_active, role, created_at)")