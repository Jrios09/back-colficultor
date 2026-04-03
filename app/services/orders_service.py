from datetime import datetime

from fastapi import HTTPException, status

from app.repositories.cart_repository import clear_cart, get_or_create_cart
from app.repositories.orders_repository import create_order
from app.repositories.products_repository import (
    decrement_stock_if_available,
    get_active_products_by_ids,
    increment_stock,
)


async def create_order_from_cart(user_id: str) -> dict:
    cart = await get_or_create_cart(user_id)
    cart_items = cart.get("items", [])

    if not cart_items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El carrito está vacío",
        )

    product_ids = [item["productId"] for item in cart_items]
    products_map = await get_active_products_by_ids(product_ids)

    missing_products = [pid for pid in product_ids if pid not in products_map]
    if missing_products:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto no encontrado o inactivo: {missing_products[0]}",
        )

    for item in cart_items:
        product = products_map[item["productId"]]
        if int(product["stock"]) < int(item["cantidad"]):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stock insuficiente para '{product['nombre']}'. Disponible: {product['stock']}",
            )

    decremented: list[tuple[str, int]] = []
    try:
        for item in cart_items:
            ok = await decrement_stock_if_available(item["productId"], int(item["cantidad"]))
            if not ok:
                product = products_map[item["productId"]]
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Stock insuficiente para '{product['nombre']}'. Intenta nuevamente.",
                )
            decremented.append((item["productId"], int(item["cantidad"])))
    except Exception:
        for product_id, cantidad in decremented:
            await increment_stock(product_id, cantidad)
        raise

    order_items = []
    total = 0.0
    for item in cart_items:
        product = products_map[item["productId"]]
        precio = float(product["precio"])
        cantidad = int(item["cantidad"])
        subtotal = precio * cantidad
        total += subtotal

        order_items.append(
            {
                "productId": item["productId"],
                "nombreSnapshot": product["nombre"],
                "precioSnapshot": precio,
                "cantidad": cantidad,
                "subtotal": subtotal,
            }
        )

    now = datetime.utcnow()
    order_doc = {
        "userId": user_id,
        "items": order_items,
        "total": total,
        "estado": "PENDIENTE_PAGO",
        "createdAt": now,
        "updatedAt": now,
    }

    order = await create_order(order_doc)
    await clear_cart(user_id)
    return order
