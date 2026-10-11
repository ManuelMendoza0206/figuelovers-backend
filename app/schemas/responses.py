from typing import Any
from pydantic import BaseModel, Field


# ==========================================
# ESQUEMAS DE RESPUESTA GENÉRICA
# ==========================================
class SuccessResponse(BaseModel):
    """Respuesta estándar para operaciones exitosas."""
    status: str = "success"
    message: str
    data: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Respuesta estándar para manejo de errores."""
    status: str = "error"
    message: str
    details: Any | None = None


# ==========================================
# ESQUEMAS DE RESPUESTAS MATEMÁTICAS
# ==========================================
class AdjacencyMatrixResponse(BaseModel):
    """Estructura para retornar la matriz matemática."""
    nodes: list[str] = Field(..., description="Lista ordenada de IDs de nodos para interpretar la matriz")
    matrix: list[list[float]] = Field(..., description="Matriz bidimensional (N x N) con los pesos")
    is_directed: bool = Field(..., description="Indica si la matriz representa un grafo dirigido")

    model_config = {"json_schema_extra": {"example": {
        "nodes": ["A", "B", "C"],
        "matrix": [
            [0.0, 5.0, 0.0],
            [5.0, 0.0, 10.0],
            [0.0, 10.0, 0.0]
        ],
        "is_directed": False
    }}}