from fastapi import APIRouter
from app.schemas.responses import SuccessResponse

router = APIRouter(prefix="/health", tags=["Salud del Sistema"])

@router.get("", response_model=SuccessResponse)
def health_check():
    """
    Verifica que la API está en línea y lista para recibir peticiones.
    """
    return SuccessResponse(
        message="El motor de grafos está en línea y funcionando.",
        data={"status": "OK"}
    )