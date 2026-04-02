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
