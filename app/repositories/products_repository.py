import re
import unicodedata
from datetime import datetime

from bson import ObjectId

from app.db.mongodb import get_db


SORT_MAPPING: dict[str, tuple[str, int]] = {
    "precio_asc": ("precio", 1),
    "precio_desc": ("precio", -1),
    "recientes": ("created_at", -1),
}

# Mapa de caracteres base → clase regex que incluye sus variantes acentuadas.
# Como usamos $options:"i" no hace falta duplicar mayúsculas.
_ACCENT_CLASSES: dict[str, str] = {
    "a": "[aáàâäã]",
    "á": "[aáàâäã]",
    "à": "[aáàâäã]",
    "â": "[aáàâäã]",
    "ä": "[aáàâäã]",
    "ã": "[aáàâäã]",
    "e": "[eéèêë]",
    "é": "[eéèêë]",
    "è": "[eéèêë]",
    "ê": "[eéèêë]",
    "ë": "[eéèêë]",
    "i": "[iíìîï]",
    "í": "[iíìîï]",
    "ì": "[iíìîï]",
    "î": "[iíìîï]",
    "ï": "[iíìîï]",
    "o": "[oóòôöõ]",
    "ó": "[oóòôöõ]",
    "ò": "[oóòôöõ]",
    "ô": "[oóòôöõ]",
    "ö": "[oóòôöõ]",
    "õ": "[oóòôöõ]",
    "u": "[uúùûü]",
    "ú": "[uúùûü]",
    "ù": "[uúùûü]",
    "û": "[uúùûü]",
    "ü": "[uúùûü]",
    "n": "[nñ]",
    "ñ": "[nñ]",
    "c": "[cç]",
    "ç": "[cç]",
}


def _accent_pattern(text: str) -> str:
    """
    Convierte un texto en un patrón regex que hace match independientemente
    de si los caracteres tienen o no tilde/acento.
    Ejemplo: "cafe" → "[cç][aáàâäã][fF][eéèêë]"
             "café" → mismo resultado
    """
    parts = []
    for ch in text.lower():
        if ch.isspace():
            parts.append(r"\s+")
        elif ch in _ACCENT_CLASSES:
            parts.append(_ACCENT_CLASSES[ch])
        else:
            parts.append(re.escape(ch))
    return "".join(parts)


def _doc_to_public(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    return doc


def _build_catalog_query(
    q: str | None,
    region: str | None,
    min_price: float | None,
    max_price: float | None,
) -> dict:
    # Acumulamos todas las condiciones en una lista para usar $and al final.
    # Esto evita conflictos entre $or de región y $or de búsqueda de texto.
    must: list[dict] = [{"is_active": True}]

    if q:
        tokens = q.strip().split()
        for token in tokens:
            pattern = _accent_pattern(token)
            # Cada palabra debe aparecer en al menos uno de los campos de texto.
            must.append({
                "$or": [
                    {"nombre":      {"$regex": pattern, "$options": "i"}},
                    {"descripcion": {"$regex": pattern, "$options": "i"}},
                    {"region":      {"$regex": pattern, "$options": "i"}},
                ]
            })

    if region:
        normalized_region = region.strip()
        if normalized_region:
            region_pattern = _accent_pattern(normalized_region)
            exact = {"$regex": f"^{region_pattern}$", "$options": "i"}
            # Compatibilidad con datos legacy que usen "origen" en vez de "region".
            must.append({"$or": [{"region": exact}, {"origen": exact}]})

    price_filter: dict = {}
    if min_price is not None:
        price_filter["$gte"] = min_price
    if max_price is not None:
        price_filter["$lte"] = max_price
    if price_filter:
        must.append({"precio": price_filter})

    return {"$and": must} if len(must) > 1 else must[0]


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
