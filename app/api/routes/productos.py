from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, require_role
from app.schemas.user import UserInDB, UserRole
from app.schemas.producto import (
    ProductoCreate,
    ProductoUpdate,
    ProductoPublic,
)
from app.models.producto import (
    create_producto,
    get_productos_by_caficultor,
    get_all_active_productos,
    get_producto_by_id,
    update_producto,
    soft_delete_producto,
    soft_delete_producto_admin,
)
from app.services.product_images_service import delete_all_product_images_for_product

router = APIRouter(prefix="/api/productos", tags=["productos"])


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def crear_producto(
    producto_in: ProductoCreate,
    current: UserInDB = Depends(require_role(UserRole.CAFICULTOR)),
):
    """
    Crea un producto nuevo.
    Solo caficultores pueden crear productos.
    """
    producto = await create_producto(
        caficultor_id=current.id,
        producto_in=producto_in.model_dump(),
    )
    return producto


@router.get("/mis", response_model=list[dict])
async def listar_mis_productos(
    current: UserInDB = Depends(get_current_user),
):
    """
    Lista los productos del usuario autenticado.
    - Caficultor: ve todos sus productos (activos e inactivos).
    - Comprador: ve todos los productos activos del catálogo.
    """
    if current.role == UserRole.CAFICULTOR:
        return await get_productos_by_caficultor(current.id, include_inactive=True)

    # Comprador ve el catálogo completo de productos activos
    return await get_all_active_productos()


@router.put("/{producto_id}", response_model=dict)
async def editar_producto(
    producto_id: str,
    producto_in: ProductoUpdate,
    current: UserInDB = Depends(require_role(UserRole.CAFICULTOR)),
):
    """
    Actualiza un producto existente.
    Validaciones:
    - Solo el caficultor dueño puede editar su propio producto.
    - Lanzará 404 si no existe o 403 si no le pertenece.
    """
    producto = await get_producto_by_id(producto_id)
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    if producto["caficultor_id"] != current.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para editar este producto")

    updates = {k: v for k, v in producto_in.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se envió ningún campo para actualizar",
        )

    updated = await update_producto(producto_id, current.id, updates)
    return updated


@router.delete("/{producto_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_producto(
    producto_id: str,
    current: UserInDB = Depends(require_role(UserRole.CAFICULTOR, UserRole.ADMIN)),
):
    """
    Desactiva un producto (soft-delete).
    Solo el caficultor dueño puede desactivar su propio producto.
    """
    producto = await get_producto_by_id(producto_id)
    if not producto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    is_admin = current.role == UserRole.ADMIN
    if not is_admin and producto["caficultor_id"] != current.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para eliminar este producto")

    await delete_all_product_images_for_product(producto)
    if is_admin:
        await soft_delete_producto_admin(producto_id)
    else:
        await soft_delete_producto(producto_id, current.id)
    return None
