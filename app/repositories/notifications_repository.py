from datetime import datetime

from bson import ObjectId
from pymongo import ReturnDocument

from app.db.mongodb import get_notifications_collection


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


async def create_notification(notification_doc: dict) -> dict:
    notifications = get_notifications_collection()
    result = await notifications.insert_one(notification_doc)
    notification_doc["_id"] = str(result.inserted_id)
    return notification_doc


async def list_notifications_for_user(user_id: str, *, limit: int = 50) -> list[dict]:
    notifications = get_notifications_collection()
    cursor = (
        notifications
        .find({"userId": user_id})
        .sort("createdAt", -1)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return [_serialize_id(doc) for doc in docs]


async def count_unread_notifications_for_user(user_id: str) -> int:
    notifications = get_notifications_collection()
    return await notifications.count_documents({"userId": user_id, "isRead": False})


async def mark_notification_as_read_for_user(notification_id: str, user_id: str) -> dict | None:
    oid = _parse_object_id(notification_id)
    if oid is None:
        return None

    notifications = get_notifications_collection()
    now = datetime.utcnow()
    updated = await notifications.find_one_and_update(
        {"_id": oid, "userId": user_id},
        {"$set": {"isRead": True, "readAt": now, "updatedAt": now}},
        return_document=ReturnDocument.AFTER,
    )
    return _serialize_id(updated)


async def mark_all_notifications_as_read_for_user(user_id: str) -> int:
    notifications = get_notifications_collection()
    now = datetime.utcnow()
    result = await notifications.update_many(
        {"userId": user_id, "isRead": False},
        {"$set": {"isRead": True, "readAt": now, "updatedAt": now}},
    )
    return int(result.modified_count)
