from motor.motor_asyncio import AsyncIOMotorClient
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
