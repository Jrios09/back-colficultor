from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException, status

from app.db.mongodb import get_db


def _doc_to_product(doc: dict) -> dict:
    """Convierte _id de ObjectId a string en el documento."""
    doc["_id"] = str(doc["_id"])
    return doc


async def create_producto(caficultor_id: str, producto_in: dict) -> dict:
    """
    Inserta un producto nuevo en la colección 'productos'.
    producto_in ya viene validado por el schema de Pydantic.
    """
    db = get_db()
    now = datetime.utcnow()
    doc = {
        **producto_in,
        "caficultor_id": caficultor_id,
        "is_active": True,
        "urls_imagenes": [],
        "imagenes": [],
        "created_at": now,
        "updated_at": now,
    }
    result = await db["productos"].insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


async def get_productos_by_caficultor(
    caficultor_id: str,
    include_inactive: bool = False,
) -> list[dict]:
    """
    Lista todos los productos de un caficultor.
    Por defecto solo trae activos. include_inactive=True para el dueño.
    """
    db = get_db()
    query: dict = {"caficultor_id": caficultor_id}
    if not include_inactive:
        query["is_active"] = True
    cursor = db["productos"].find(query).sort("created_at", -1)
    docs = await cursor.to_list(length=None)
    return [_doc_to_product(d) for d in docs]


async def get_all_active_productos() -> list[dict]:
    """
    Lista todos los productos activos (para compradores).
    """
    db = get_db()
    cursor = db["productos"].find({"is_active": True}).sort("created_at", -1)
    docs = await cursor.to_list(length=None)
    return [_doc_to_product(d) for d in docs]


async def get_all_productos(*, include_inactive: bool = True) -> list[dict]:
    """
    Lista todos los productos para administración.
    include_inactive=True incluye activos e inactivos.
    """
    db = get_db()
    query: dict = {}
    if not include_inactive:
        query["is_active"] = True
    cursor = db["productos"].find(query).sort("created_at", -1)
    docs = await cursor.to_list(length=None)
    return [_doc_to_product(d) for d in docs]


async def get_producto_by_id(producto_id: str) -> dict | None:
    """Busca un producto por su ObjectId. Retorna None si no existe."""
    db = get_db()
    try:
        doc = await db["productos"].find_one({"_id": ObjectId(producto_id)})
    except Exception:
        return None
    if not doc:
        return None
    return _doc_to_product(doc)


async def update_producto(
    producto_id: str,
    caficultor_id: str,
    updates: dict,
) -> dict:
    """
    Actualiza campos de un producto verificando que el caficultor sea el dueño.
    Lanza 404 si el producto no existe O no le pertenece.
    """
    db = get_db()
    updates["updated_at"] = datetime.utcnow()

    result = await db["productos"].find_one_and_update(
        {"_id": ObjectId(producto_id), "caficultor_id": caficultor_id},
        {"$set": updates},
        return_document=True,
    )
    if not result:
        # Distinguimos "no existe" de "no le pertenece"
        exists = await db["productos"].find_one({"_id": ObjectId(producto_id)})
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Producto no encontrado",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para editar este producto",
        )
    return _doc_to_product(result)


async def soft_delete_producto(producto_id: str, caficultor_id: str) -> None:
    """
    Desactiva un producto (soft-delete). Verifica pertenencia.
    Lanza 404/403 con los mismos criterios que update_producto.
    """
    await update_producto(producto_id, caficultor_id, {"is_active": False})


async def soft_delete_producto_admin(producto_id: str) -> None:
    """
    Desactiva un producto (soft-delete) sin verificar dueño.
    Útil para rol admin.
    """
    db = get_db()
    result = await db["productos"].update_one(
        {"_id": ObjectId(producto_id)},
        {"$set": {"is_active": False, "updated_at": datetime.utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )


def _extract_urls(imagenes: list[dict]) -> list[str]:
    urls: list[str] = []
    for image in imagenes:
        secure_url = image.get("secure_url")
        url = image.get("url")
        if isinstance(secure_url, str) and secure_url:
            urls.append(secure_url)
        elif isinstance(url, str) and url:
            urls.append(url)
    return urls


async def append_producto_imagenes(producto_id: str, nuevas_imagenes: list[dict]) -> dict:
    db = get_db()
    doc = await db["productos"].find_one({"_id": ObjectId(producto_id)})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )

    actuales = doc.get("imagenes", [])
    merged = [*actuales, *nuevas_imagenes]
    urls = _extract_urls(merged)

    updated = await db["productos"].find_one_and_update(
        {"_id": ObjectId(producto_id)},
        {
            "$set": {
                "imagenes": merged,
                "urls_imagenes": urls,
                "updated_at": datetime.utcnow(),
            }
        },
        return_document=True,
    )
    return _doc_to_product(updated)


async def remove_producto_imagen_por_id(producto_id: str, image_id: str) -> tuple[dict, dict]:
    db = get_db()
    doc = await db["productos"].find_one({"_id": ObjectId(producto_id)})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )

    imagenes = doc.get("imagenes", [])
    removed = None
    remaining: list[dict] = []
    for image in imagenes:
        if image.get("asset_id") == image_id or image.get("public_id") == image_id:
            if removed is None:
                removed = image
                continue
        remaining.append(image)

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Imagen no encontrada en el producto",
        )

    updated = await db["productos"].find_one_and_update(
        {"_id": ObjectId(producto_id)},
        {
            "$set": {
                "imagenes": remaining,
                "urls_imagenes": _extract_urls(remaining),
                "updated_at": datetime.utcnow(),
            }
        },
        return_document=True,
    )
    return _doc_to_product(updated), removed


async def clear_producto_imagenes(producto_id: str) -> None:
    db = get_db()
    await db["productos"].update_one(
        {"_id": ObjectId(producto_id)},
        {
            "$set": {
                "imagenes": [],
                "urls_imagenes": [],
                "updated_at": datetime.utcnow(),
            }
        },
    )
