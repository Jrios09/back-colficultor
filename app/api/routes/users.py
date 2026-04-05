from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.api.deps import require_role, get_current_user
from app.schemas.user import (
    PerfilUpdate,
    UserAdminActionResponse,
    UserInDB,
    UserPublic,
    UserRole,
    UserRoleUpdateRequest,
)
from app.models.user import delete_user_permanently, list_users_admin, set_user_role, update_user

router = APIRouter(prefix="/api/users", tags=["users"])

@router.get("/me", response_model=UserPublic)
async def read_me(current: UserInDB = Depends(get_current_user)):
    return UserPublic(**current.dict(by_alias=True, exclude={"password_hash"}))

@router.patch("/me", response_model=UserPublic)
async def update_me(
    updates: PerfilUpdate,
    current: UserInDB = Depends(get_current_user),
):
    """
    Actualiza el perfil del usuario autenticado.
    Solo permite editar: full_name y campos de perfil.
    role, is_active y password_hash están protegidos por el schema.
    """
    updated = await update_user(
        user_id=current.id,
        full_name=updates.full_name,
        perfil_ciudad=updates.perfil_ciudad,
        perfil_departamento=updates.perfil_departamento,
        perfil_direccion=updates.perfil_direccion,
        perfil_telefono=updates.perfil_telefono,
        perfil_preferencias=updates.perfil_preferencias,
    )
    return UserPublic(**updated.dict(by_alias=True, exclude={"password_hash"}))

@router.get("/admin", dependencies=[Depends(require_role(UserRole.ADMIN))])
async def admin_only():
    return {"message": "Solo admin"}


@router.get("", response_model=list[UserPublic])
async def list_users_for_admin(
    role: UserRole | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=200, ge=1, le=500),
    _: UserInDB = Depends(require_role(UserRole.ADMIN)),
):
    return await list_users_admin(role=role, is_active=is_active, search=search, limit=limit)


@router.patch("/{user_id}/role", response_model=UserPublic)
async def update_user_role(
    user_id: str,
    payload: UserRoleUpdateRequest,
    current: UserInDB = Depends(require_role(UserRole.ADMIN)),
):
    if user_id == current.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No puedes cambiar tu propio rol desde este módulo",
        )
    if payload.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No está permitido asignar el rol admin a otros usuarios",
        )

    updated = await set_user_role(user_id=user_id, role=payload.role)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return updated


@router.delete("/{user_id}", response_model=UserAdminActionResponse)
async def delete_user_admin(
    user_id: str,
    current: UserInDB = Depends(require_role(UserRole.ADMIN)),
):
    if user_id == current.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No puedes eliminar tu propio usuario administrador",
        )

    deleted = await delete_user_permanently(user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return {
        "message": "Usuario eliminado permanentemente",
        "user_id": user_id,
    }
