import re
from datetime import datetime

from bson import ObjectId

from app.db.mongodb import get_db


SORT_MAPPING: dict[str, tuple[str, int]] = {
    "precio_asc": ("precio", 1),
    "precio_desc": ("precio", -1),
    "recientes": ("created_at", -1),
}


def _doc_to_public(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    return doc


def _build_catalog_query(
    q: str | None,
    region: str | None,
    min_price: float | None,
    max_price: float | None,
) -> dict:
    query: dict = {"is_active": True}

    if q:
        normalized_q = q.strip()
        if normalized_q:
            safe_q = re.escape(normalized_q)
            query["nombre"] = {"$regex": safe_q, "$options": "i"}

    if region:
        normalized_region = region.strip()
        if normalized_region:
            exact_region = {"$regex": f"^{re.escape(normalized_region)}$", "$options": "i"}
            # Compatibilidad con datos legacy que usen "origen" en vez de "region".
            query["$or"] = [
                {"region": exact_region},
                {"origen": exact_region},
            ]

    price_filter: dict = {}
    if min_price is not None:
        price_filter["$gte"] = min_price
    if max_price is not None:
        price_filter["$lte"] = max_price
    if price_filter:
        query["precio"] = price_filter

    return query


async def count_active_products(
    q: str | None,
    region: str | None,
    min_price: float | None,
    max_price: float | None,
) -> int:
    db = get_db()
    query = _build_catalog_query(q=q, region=region, min_price=min_price, max_price=max_price)
    return await db["productos"].count_documents(query)


async def list_active_products(
    *,
    q: str | None,
    region: str | None,
    min_price: float | None,
    max_price: float | None,
    sort: str,
    page: int,
    limit: int,
) -> list[dict]:
    db = get_db()
    query = _build_catalog_query(q=q, region=region, min_price=min_price, max_price=max_price)
    sort_field, sort_direction = SORT_MAPPING.get(sort, SORT_MAPPING["recientes"])

    skip = (page - 1) * limit
    cursor = (
        db["productos"]
        .find(query)
        .sort(sort_field, sort_direction)
        .skip(skip)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return [_doc_to_public(d) for d in docs]


async def get_active_products_by_ids(product_ids: list[str]) -> dict[str, dict]:
    if not product_ids:
        return {}

    object_ids = []
    for pid in product_ids:
        try:
            object_ids.append(ObjectId(pid))
        except Exception:
            continue

    if not object_ids:
        return {}

    db = get_db()
    cursor = db["productos"].find({"_id": {"$in": object_ids}, "is_active": True})
    docs = await cursor.to_list(length=None)
    mapped = {}
    for doc in docs:
        public = _doc_to_public(doc)
        mapped[public["_id"]] = public
    return mapped


async def decrement_stock_if_available(product_id: str, cantidad: int) -> bool:
    db = get_db()
    try:
        oid = ObjectId(product_id)
    except Exception:
        return False

    result = await db["productos"].update_one(
        {
            "_id": oid,
            "is_active": True,
            "stock": {"$gte": cantidad},
        },
        {
            "$inc": {"stock": -cantidad},
            "$set": {"updated_at": datetime.utcnow()},
        },
    )
    return result.modified_count == 1


async def increment_stock(product_id: str, cantidad: int) -> None:
    db = get_db()
    try:
        oid = ObjectId(product_id)
    except Exception:
        return

    await db["productos"].update_one(
        {"_id": oid},
        {
            "$inc": {"stock": cantidad},
            "$set": {"updated_at": datetime.utcnow()},
        },
    )
