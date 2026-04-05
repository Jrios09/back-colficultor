from datetime import datetime

from app.db.mongodb import get_db


def _serialize_id(doc: dict | None) -> dict | None:
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    return doc


async def list_orders_between(*, desde_dt: datetime, hasta_dt: datetime) -> list[dict]:
    db = get_db()
    cursor = db["ordenes"].find(
        {
            "createdAt": {
                "$gte": desde_dt,
                "$lte": hasta_dt,
            }
        }
    ).sort("createdAt", 1)
    docs = await cursor.to_list(length=None)
    return [_serialize_id(doc) for doc in docs]


async def list_transactions_by_order_ids(order_ids: list[str]) -> dict[str, dict]:
    if not order_ids:
        return {}

    db = get_db()
    cursor = db["transacciones"].find(
        {"orderId": {"$in": order_ids}}
    ).sort("updatedAt", -1)
    docs = await cursor.to_list(length=None)

    latest_by_order: dict[str, dict] = {}
    for doc in docs:
        oid = str(doc.get("orderId", ""))
        if not oid:
            continue
        if oid not in latest_by_order:
            latest_by_order[oid] = _serialize_id(doc)
    return latest_by_order
