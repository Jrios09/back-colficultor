from datetime import datetime

from bson import ObjectId
from pymongo import ReturnDocument

from app.db.mongodb import get_db


def _serialize_id(doc: dict | None) -> dict | None:
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    return doc


def _parse_object_id(raw_id: str) -> ObjectId | None:
    try:
        return ObjectId(raw_id)
    except Exception:
        return None


async def create_order(order_doc: dict) -> dict:
    db = get_db()
    result = await db["ordenes"].insert_one(order_doc)
    order_doc["_id"] = str(result.inserted_id)
    return order_doc


async def list_orders_by_user(user_id: str) -> list[dict]:
    db = get_db()
    cursor = db["ordenes"].find(
        {
            "userId": user_id,
            "$or": [
                {"deletedByBuyer": {"$exists": False}},
                {"deletedByBuyer": False},
            ],
        }
    ).sort("createdAt", -1)
    docs = await cursor.to_list(length=None)
    return [_serialize_id(doc) for doc in docs]


async def get_order_by_id(order_id: str) -> dict | None:
    oid = _parse_object_id(order_id)
    if oid is None:
        return None
    db = get_db()
    doc = await db["ordenes"].find_one({"_id": oid})
    return _serialize_id(doc)


async def list_orders_by_caficultor(caficultor_id: str) -> list[dict]:
    db = get_db()
    cursor = db["ordenes"].find({"caficultorIds": caficultor_id}).sort("createdAt", -1)
    docs = await cursor.to_list(length=None)
    return [_serialize_id(doc) for doc in docs]


async def get_product_ids_of_caficultor(product_ids: set[str], caficultor_id: str) -> set[str]:
    """Dado un conjunto de product_ids, devuelve solo los que pertenecen al caficultor."""
    if not product_ids:
        return set()
    db = get_db()
    oids = [ObjectId(pid) for pid in product_ids if ObjectId.is_valid(pid)]
    if not oids:
        return set()
    cursor = db["productos"].find(
        {"_id": {"$in": oids}, "caficultor_id": caficultor_id},
        {"_id": 1},
    )
    docs = await cursor.to_list(length=None)
    return {str(doc["_id"]) for doc in docs}


async def order_has_caficultor(order: dict, caficultor_id: str) -> bool:
    cached_ids = order.get("caficultorIds", [])
    if caficultor_id in cached_ids:
        return True

    product_ids = [item.get("productId") for item in order.get("items", []) if item.get("productId")]
    object_ids: list[ObjectId] = []
    for pid in product_ids:
        oid = _parse_object_id(pid)
        if oid is not None:
            object_ids.append(oid)

    if not object_ids:
        return False

    db = get_db()
    count = await db["productos"].count_documents(
        {
            "_id": {"$in": object_ids},
            "caficultor_id": caficultor_id,
        },
        limit=1,
    )
    return count > 0


async def user_has_paid_order_for_product(*, user_id: str, product_id: str) -> bool:
    db = get_db()
    count = await db["ordenes"].count_documents(
        {
            "userId": user_id,
            "estado": "PAGADA",
            "items": {"$elemMatch": {"productId": product_id}},
        },
        limit=1,
    )
    return count > 0


async def update_order_status_with_history(
    *,
    order_id: str,
    new_status: str,
    changed_by_user_id: str | None,
    reason: str | None = None,
) -> dict | None:
    oid = _parse_object_id(order_id)
    if oid is None:
        return None
    db = get_db()
    current = await db["ordenes"].find_one({"_id": oid})
    if not current:
        return None

    from_status = current.get("estado")
    if from_status == new_status:
        return _serialize_id(current)

    now = datetime.utcnow()
    history_item = {
        "fromStatus": from_status,
        "toStatus": new_status,
        "changedByUserId": changed_by_user_id,
        "reason": reason,
        "createdAt": now,
    }

    updated = await db["ordenes"].find_one_and_update(
        {"_id": oid},
        {
            "$set": {
                "estado": new_status,
                "updatedAt": now,
            },
            "$push": {
                "statusHistory": history_item,
            },
        },
        return_document=ReturnDocument.AFTER,
    )
    return _serialize_id(updated)


async def soft_delete_pending_order_by_buyer(
    *,
    order_id: str,
    buyer_id: str,
) -> dict | None:
    oid = _parse_object_id(order_id)
    if oid is None:
        return None

    db = get_db()
    current = await db["ordenes"].find_one(
        {
            "_id": oid,
            "userId": buyer_id,
        }
    )
    if not current:
        return None

    now = datetime.utcnow()
    from_status = current.get("estado")
    history_item = {
        "fromStatus": from_status,
        "toStatus": "CANCELADA",
        "changedByUserId": buyer_id,
        "reason": "buyer_deleted_pending_order",
        "createdAt": now,
    }

    updated = await db["ordenes"].find_one_and_update(
        {"_id": oid, "userId": buyer_id},
        {
            "$set": {
                "estado": "CANCELADA",
                "deletedByBuyer": True,
                "updatedAt": now,
            },
            "$push": {
                "statusHistory": history_item,
            },
        },
        return_document=ReturnDocument.AFTER,
    )
    return _serialize_id(updated)
