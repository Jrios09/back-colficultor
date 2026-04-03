from datetime import datetime

from app.db.mongodb import get_db


async def get_cart_by_user(user_id: str) -> dict | None:
    db = get_db()
    return await db["carritos"].find_one({"userId": user_id})


async def create_empty_cart(user_id: str) -> dict:
    db = get_db()
    now = datetime.utcnow()
    doc = {
        "userId": user_id,
        "items": [],
        "createdAt": now,
        "updatedAt": now,
    }
    await db["carritos"].insert_one(doc)
    return doc


async def get_or_create_cart(user_id: str) -> dict:
    cart = await get_cart_by_user(user_id)
    if cart:
        return cart
    return await create_empty_cart(user_id)


async def save_cart_items(user_id: str, items: list[dict]) -> dict:
    db = get_db()
    now = datetime.utcnow()
    await db["carritos"].update_one(
        {"userId": user_id},
        {
            "$set": {
                "items": items,
                "updatedAt": now,
            },
            "$setOnInsert": {
                "createdAt": now,
            },
        },
        upsert=True,
    )
    return await get_or_create_cart(user_id)


async def clear_cart(user_id: str) -> dict:
    return await save_cart_items(user_id, [])
