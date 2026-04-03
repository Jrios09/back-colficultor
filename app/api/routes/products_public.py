from fastapi import APIRouter, Query

from app.schemas.catalog import CatalogListResponse, CatalogSort
from app.services.products_service import get_public_catalog

router = APIRouter(prefix="/api/productos", tags=["catalogo"])


@router.get("", response_model=CatalogListResponse)
async def list_catalog(
    q: str | None = Query(default=None, min_length=1, max_length=100),
    origen: str | None = Query(default=None, max_length=100),
    region: str | None = Query(default=None, max_length=100),
    min_precio: float | None = Query(default=None, alias="minPrecio", ge=0),
    max_precio: float | None = Query(default=None, alias="maxPrecio", ge=0),
    sort: CatalogSort = Query(default=CatalogSort.RECIENTES),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=12, ge=1, le=100),
):
    target_region = region or origen
    return await get_public_catalog(
        q=q,
        region=target_region,
        min_precio=min_precio,
        max_precio=max_precio,
        sort=sort.value,
        page=page,
        limit=limit,
    )
