from pydantic import BaseModel, Field


class AssignmentAssignmentSchema(BaseModel):
    row: str
    col: str
    cost: float


class AssignmentStepSchema(BaseModel):
    step: int
    name: str
    matrix: list[list[float]]
    description: str
    min_uncovered: float | None = None
    selected_zeros: list[list[int]] | None = None


class AssignmentResponseSchema(BaseModel):
    assignments: list[AssignmentAssignmentSchema]
    total_cost: float
    initial_cost_matrix: list[list[float]] = Field(default=[], description="Matriz de costos inicial antes de calcular")
    steps: list[AssignmentStepSchema] = Field(default=[], description="Pasos intermedios del algoritmo húngaro")
    padding_info: dict | None = Field(default=None, description="Metadatos de padding para matrices rectangulares (columnas/filas dummy añadidas)")


class AssignmentRequestSchema(BaseModel):
    cost_matrix: list[list[float]] = Field(..., description="Matriz de costos del problema de asignación")
    row_labels: list[str] | None = Field(default=None, description="Etiquetas de filas; opcional")
    col_labels: list[str] | None = Field(default=None, description="Etiquetas de columnas; opcional")
    maximize: bool = Field(False, description="Indica si el objetivo es maximizar en lugar de minimizar")