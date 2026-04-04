from datetime import date

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import require_role
from app.schemas.user import UserInDB, UserRole
from app.services.reports_service import build_orders_csv, build_sales_pdf

router = APIRouter(prefix="/api/reportes", tags=["reportes"])


@router.get("/ordenes.csv")
async def export_orders_csv(
    desde: date = Query(..., description="Fecha inicio YYYY-MM-DD"),
    hasta: date = Query(..., description="Fecha fin YYYY-MM-DD"),
    _: UserInDB = Depends(require_role(UserRole.ADMIN)),
):
    content = await build_orders_csv(desde=desde, hasta=hasta)
    filename = f"ordenes_{desde.isoformat()}_{hasta.isoformat()}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/ventas.pdf")
async def export_sales_pdf(
    desde: date = Query(..., description="Fecha inicio YYYY-MM-DD"),
    hasta: date = Query(..., description="Fecha fin YYYY-MM-DD"),
    _: UserInDB = Depends(require_role(UserRole.ADMIN)),
):
    content = await build_sales_pdf(desde=desde, hasta=hasta)
    filename = f"ventas_{desde.isoformat()}_{hasta.isoformat()}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
