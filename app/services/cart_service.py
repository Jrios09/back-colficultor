from fastapi import HTTPException, status

from app.repositories.cart_repository import get_or_create_cart, save_cart_items
from app.repositories.products_repository import get_active_products_by_ids


def _normalize_cart_item(item: dict) -> dict:
    return {
        "productId": item["productId"],
        "cantidad": int(item["cantidad"]),
        "precioSnapshot": float(item.get("precioSnapshot", 0)),
    }


async def get_cart_for_user(user_id: str) -> dict:
    cart = await get_or_create_cart(user_id)
    raw_items = [_normalize_cart_item(item) for item in cart.get("items", [])]

    product_map = await get_active_products_by_ids([item["productId"] for item in raw_items])

    response_items = []
    total = 0.0
    for item in raw_items:
        product = product_map.get(item["productId"])
        nombre = product["nombre"] if product else "Producto no disponible"
        precio = float(item["precioSnapshot"])
        subtotal = precio * item["cantidad"]
        total += subtotal

        response_items.append(
            {
                "productId": item["productId"],
                "nombre": nombre,
                "cantidad": item["cantidad"],
                "precioSnapshot": precio,
                "subtotal": subtotal,
            }
        )

    return {
        "userId": user_id,
        "items": response_items,
        "total": total,
        "updatedAt": cart["updatedAt"],
    }


async def add_item_to_cart(user_id: str, product_id: str, cantidad: int) -> dict:
    product_map = await get_active_products_by_ids([product_id])
    product = product_map.get(product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado o inactivo")

    cart = await get_or_create_cart(user_id)
    items = [_normalize_cart_item(item) for item in cart.get("items", [])]

    found = False
    for item in items:
        if item["productId"] == product_id:
            item["cantidad"] += cantidad
            item["precioSnapshot"] = float(product["precio"])
            found = True
            break

    if not found:
        items.append(
            {
                "productId": product_id,
                "cantidad": cantidad,
                "precioSnapshot": float(product["precio"]),
            }
        )

    await save_cart_items(user_id, items)
    return await get_cart_for_user(user_id)


async def update_cart_item_quantity(user_id: str, product_id: str, cantidad: int) -> dict:
    cart = await get_or_create_cart(user_id)
    items = [_normalize_cart_item(item) for item in cart.get("items", [])]

    if not any(item["productId"] == product_id for item in items):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El producto no está en el carrito")

    product_map = await get_active_products_by_ids([product_id])
    product = product_map.get(product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado o inactivo")

    for item in items:
        if item["productId"] == product_id:
            item["cantidad"] = cantidad
            item["precioSnapshot"] = float(product["precio"])
            break

    await save_cart_items(user_id, items)
    return await get_cart_for_user(user_id)


async def remove_item_from_cart(user_id: str, product_id: str) -> dict:
    cart = await get_or_create_cart(user_id)
    items = [_normalize_cart_item(item) for item in cart.get("items", [])]

    filtered = [item for item in items if item["productId"] != product_id]
    if len(filtered) == len(items):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El producto no está en el carrito")

    await save_cart_items(user_id, filtered)
    return await get_cart_for_user(user_id)
