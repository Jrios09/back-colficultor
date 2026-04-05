from bson import ObjectId
from datetime import datetime
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.db.mongodb import get_db


class ReviewAlreadyExistsError(Exception):
    pass


def _serialize_id(doc: dict | None) -> dict | None:
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    return doc


async def create_review(review_doc: dict) -> dict:
    db = get_db()
    try:
        result = await db["resenas"].insert_one(review_doc)
    except DuplicateKeyError as ex:
        raise ReviewAlreadyExistsError("Ya existe una reseña para este producto y usuario") from ex

    review_doc["_id"] = str(result.inserted_id)
    return review_doc


async def list_reviews_by_product(product_id: str) -> list[dict]:
    db = get_db()
    cursor = db["resenas"].find({"productId": product_id}).sort("createdAt", -1)
    docs = await cursor.to_list(length=None)
    return [_serialize_id(doc) for doc in docs]


async def list_reviews_by_user(user_id: str) -> list[dict]:
    db = get_db()
    cursor = db["resenas"].find({"userId": user_id}).sort("createdAt", -1)
    docs = await cursor.to_list(length=None)
    return [_serialize_id(doc) for doc in docs]


async def product_exists(product_id: str) -> bool:
    if not ObjectId.is_valid(product_id):
        return False

    db = get_db()
    doc = await db["productos"].find_one({"_id": ObjectId(product_id)}, {"_id": 1})
    return doc is not None


async def get_review_by_id(review_id: str) -> dict | None:
    if not ObjectId.is_valid(review_id):
        return None
    db = get_db()
    doc = await db["resenas"].find_one({"_id": ObjectId(review_id)})
    return _serialize_id(doc)


async def get_product_owner_id(product_id: str) -> str | None:
    if not ObjectId.is_valid(product_id):
        return None
    db = get_db()
    product = await db["productos"].find_one({"_id": ObjectId(product_id)}, {"caficultor_id": 1})
    if not product:
        return None
    owner_id = product.get("caficultor_id")
    return str(owner_id) if owner_id else None


async def set_review_reply(review_id: str, reply_text: str) -> dict | None:
    if not ObjectId.is_valid(review_id):
        return None
    db = get_db()
    updated = await db["resenas"].find_one_and_update(
        {"_id": ObjectId(review_id)},
        {
            "$set": {
                "respuesta_caficultor": reply_text,
                "updatedAt": datetime.utcnow(),
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    return _serialize_id(updated)
