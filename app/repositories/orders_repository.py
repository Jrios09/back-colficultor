from app.db.mongodb import get_db


async def create_order(order_doc: dict) -> dict:
    db = get_db()
    result = await db["ordenes"].insert_one(order_doc)
    order_doc["_id"] = str(result.inserted_id)
    return order_doc
