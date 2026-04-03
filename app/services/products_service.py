from fastapi import HTTPException, status

from app.repositories.products_repository import count_active_products, list_active_products


async def get_public_catalog(
    *,
    q: str | None,
    region: str | None,
    min_precio: float | None,
    max_precio: float | None,
    sort: str,
    page: int,
    limit: int,
) -> dict:
    if min_precio is not None and max_precio is not None and min_precio > max_precio:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="minPrecio no puede ser mayor que maxPrecio",
        )

    items = await list_active_products(
        q=q,
        region=region,
        min_price=min_precio,
        max_price=max_precio,
        sort=sort,
        page=page,
        limit=limit,
    )
    total = await count_active_products(
        q=q,
        region=region,
        min_price=min_precio,
        max_price=max_precio,
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
    }
