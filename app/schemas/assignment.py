from typing import Any

from pydantic import BaseModel, Field


class AssignmentRequestSchema(BaseModel):
    cost_matrix: list[list[float]] = Field(..., description="Matriz de costos del problema de asignación")
    row_labels: list[str] | None = Field(default=None, description="Etiquetas de filas; opcional")
    col_labels: list[str] | None = Field(default=None, description="Etiquetas de columnas; opcional")
    maximize: bool = Field(False, description="Indica si el objetivo es maximizar en lugar de minimizar")


class AssignmentAssignmentSchema(BaseModel):
    row: str
    col: str
    cost: float


class AssignmentResponseSchema(BaseModel):
    assignments: list[AssignmentAssignmentSchema]
    total_cost: float
