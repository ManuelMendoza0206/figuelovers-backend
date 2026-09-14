from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.api.router import api_router
from app.schemas.responses import ErrorResponse

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def handle_cors_preflight(request: Request, call_next):
    if request.method == "OPTIONS":
        origin = request.headers.get("origin") or "*"
        response = Response(status_code=200)
        response.headers["Access-Control-Allow-Origin"] = origin if origin != "*" else "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = request.headers.get("access-control-request-headers", "*")
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response
    return await call_next(request)

app.include_router(api_router, prefix=settings.API_V1_STR)

# ==========================================
# MANEJADORES GLOBALES DE ERRORES
# ==========================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Captura errores de Pydantic (ej: enviar un string donde iba un int).
    """
    # Formateamos el error para que sea legible para el Frontend
    errores_legibles = [{"campo": err["loc"][-1], "mensaje": err["msg"]} for err in exc.errors()]
    
    error_response = ErrorResponse(
        message="Datos inválidos enviados desde el Frontend",
        details=errores_legibles
    )
    return JSONResponse(status_code=422, content=error_response.model_dump())


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Captura excepciones HTTP manuales (ej: los `raise HTTPException` de nuestros servicios).
    """
    error_response = ErrorResponse(
        message=str(exc.detail),
        details={"status_code": exc.status_code}
    )
    return JSONResponse(status_code=exc.status_code, content=error_response.model_dump())


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Captura CUALQUIER otro error interno (ej: División por cero, fallos en NetworkX).
    Evita que el servidor se caiga y el frontend se quede esperando.
    """
    error_response = ErrorResponse(
        message="Error interno del servidor",
        details=str(exc) # Nota: En producción real, no se envían los detalles crudos por seguridad
    )
    return JSONResponse(status_code=500, content=error_response.model_dump())

# ==========================================

@app.get("/", tags=["Raíz"])
def root():
    return {
        "status": "online",
        "message": f"Bienvenido a {settings.PROJECT_NAME}. Revisa /docs para la documentación."
    }