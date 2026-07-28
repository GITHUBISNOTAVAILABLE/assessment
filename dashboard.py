from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, Optional
from decimal import Decimal, ROUND_HALF_UP
from app.services.cache import get_revenue_summary
from app.core.auth import authenticate_request as get_current_user

router = APIRouter()

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    current_user = Depends(get_current_user)
) -> Dict[str, Any]:

    # BUGFIX (tenant isolation): never fall back to a shared default tenant.
    # The old code used getattr(..., "default_tenant"), which silently lumped
    # any user with an unresolved tenant into one shared scope.
    tenant_id = getattr(current_user, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No tenant associated with this user")

    # Optional month/year enables timezone-correct monthly reporting
    # (see services/reservations.calculate_monthly_revenue).
    if (month is None) != (year is None):
        raise HTTPException(status_code=422, detail="Provide both month and year, or neither")

    revenue_data = await get_revenue_summary(property_id, tenant_id, month, year)

    # BUGFIX (precision): money must never pass through binary floats.
    # The old code did float(revenue_data['total']), which cannot represent
    # decimal cents exactly and produced the "off by a few cents" totals
    # finance reported. Keep the value as Decimal, round half-up to cents
    # for display, and serialize as strings.
    total_exact = Decimal(str(revenue_data['total']))
    total_display = total_exact.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    response = {
        "property_id": revenue_data['property_id'],
        "total_revenue": str(total_display),
        "total_revenue_exact": str(total_exact),
        "currency": revenue_data['currency'],
        "reservations_count": revenue_data['count']
    }
    if month and year:
        response["period"] = f"{year}-{month:02d}"
    return response
