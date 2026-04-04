from datetime import datetime

from bson import ObjectId
from pymongo import ReturnDocument

from app.db.mongodb import get_db


def _serialize_id(doc: dict | None) -> dict | None:
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    return doc


def _parse_order_id(order_id: str) -> ObjectId | None:
    try:
        return ObjectId(order_id)
    except Exception:
        return None


async def get_order_by_id(order_id: str) -> dict | None:
    oid = _parse_order_id(order_id)
    if oid is None:
        return None
    db = get_db()
    doc = await db["ordenes"].find_one({"_id": oid})
    return _serialize_id(doc)


async def create_transaction(transaction_doc: dict) -> dict:
    db = get_db()
    result = await db["transacciones"].insert_one(transaction_doc)
    transaction_doc["_id"] = str(result.inserted_id)
    return transaction_doc


async def get_transaction_by_provider_ref(provider_ref: str) -> dict | None:
    db = get_db()
    doc = await db["transacciones"].find_one({"providerRef": provider_ref})
    return _serialize_id(doc)


async def update_transaction_status(
    provider_ref: str,
    status: str,
    raw: dict | None = None,
) -> dict | None:
    db = get_db()
    update_doc: dict = {
        "$set": {
            "status": status,
            "updatedAt": datetime.utcnow(),
        }
    }
    if raw is not None:
        update_doc["$set"]["raw"] = raw

    updated = await db["transacciones"].find_one_and_update(
        {"providerRef": provider_ref},
        update_doc,
        return_document=ReturnDocument.AFTER,
    )
    return _serialize_id(updated)


async def set_order_status_with_history(
    order_id: str,
    new_status: str,
    changed_by_user_id: str | None,
    reason: str | None = None,
) -> dict | None:
    oid = _parse_order_id(order_id)
    if oid is None:
        return None
    db = get_db()
    current = await db["ordenes"].find_one({"_id": oid})
    if not current:
        return None

    from_status = current.get("estado")
    if from_status == new_status:
        current["_id"] = str(current["_id"])
        return current

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
