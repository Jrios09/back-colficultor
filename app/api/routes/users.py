from fastapi import APIRouter, Depends
from app.api.deps import require_role, get_current_user
from app.schemas.user import UserRole, UserPublic, UserInDB

router = APIRouter(prefix="/api/users", tags=["users"])

@router.get("/me", response_model=UserPublic)
async def read_me(current: UserInDB = Depends(get_current_user)):
    return UserPublic(**current.dict(by_alias=True, exclude={"password_hash"}))

@router.get("/admin", dependencies=[Depends(require_role(UserRole.ADMIN))])
async def admin_only():
    return {"message": "Solo admin"}