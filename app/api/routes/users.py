from fastapi import APIRouter, Depends
from app.api.deps import require_role, get_current_user
from app.schemas.user import UserRole, UserPublic, UserInDB, PerfilUpdate
from app.models.user import update_user

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