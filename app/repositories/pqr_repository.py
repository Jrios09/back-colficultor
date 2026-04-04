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


async def create_ticket(ticket_doc: dict) -> dict:
    db = get_db()
    result = await db["pqr_tickets"].insert_one(ticket_doc)
    ticket_doc["_id"] = str(result.inserted_id)
    return ticket_doc


async def list_tickets_by_user(user_id: str) -> list[dict]:
    db = get_db()
    cursor = db["pqr_tickets"].find({"userId": user_id}).sort("createdAt", -1)
    docs = await cursor.to_list(length=None)
    return [_serialize_id(doc) for doc in docs]


async def list_all_tickets() -> list[dict]:
    db = get_db()
    cursor = db["pqr_tickets"].find({}).sort("createdAt", -1)
    docs = await cursor.to_list(length=None)
    return [_serialize_id(doc) for doc in docs]


async def get_ticket_by_id(ticket_id: str) -> dict | None:
    oid = _parse_object_id(ticket_id)
    if oid is None:
        return None
    db = get_db()
    doc = await db["pqr_tickets"].find_one({"_id": oid})
    return _serialize_id(doc)


async def update_ticket_estado(*, ticket_id: str, estado: str) -> dict | None:
    oid = _parse_object_id(ticket_id)
    if oid is None:
        return None

    db = get_db()
    updated = await db["pqr_tickets"].find_one_and_update(
        {"_id": oid},
        {"$set": {"estado": estado, "updatedAt": datetime.utcnow()}},
        return_document=ReturnDocument.AFTER,
    )
    return _serialize_id(updated)


async def update_ticket_respuesta(*, ticket_id: str, respuesta: str) -> dict | None:
    oid = _parse_object_id(ticket_id)
    if oid is None:
        return None

    db = get_db()
    updated = await db["pqr_tickets"].find_one_and_update(
        {"_id": oid},
        {"$set": {"respuesta": respuesta, "updatedAt": datetime.utcnow()}},
        return_document=ReturnDocument.AFTER,
    )
    return _serialize_id(updated)
