from bson import ObjectId
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
