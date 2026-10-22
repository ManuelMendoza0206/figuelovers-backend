from pydantic import BaseModel, Field, model_validator

from app.schemas.graph import GraphPayloadSchema


class AssignmentAssignmentSchema(BaseModel):
    row: str
    col: str
    cost: float


class AssignmentStepSchema(BaseModel):
    step: int
    name: str
    matrix: list[list[float | None]]
    description: str
    min_uncovered: float | None = None
    selected_zeros: list[list[int]] | None = None


class AssignmentResponseSchema(BaseModel):
    assignments: list[AssignmentAssignmentSchema]
    total_cost: float
    status: str = Field("optimal", description="Estado: optimal o infeasible")
    message: str | None = None
    initial_cost_matrix: list[list[float | None]] = Field(
        default_factory=list,
        description="Matriz de costos inicial antes de calcular",
    )
    steps: list[AssignmentStepSchema] = Field(
        default_factory=list,
        description="Pasos intermedios del algoritmo húngaro",
    )
    padding_info: dict | None = Field(default=None, description="Metadatos de padding para matrices rectangulares (columnas/filas dummy añadidas)")


class AssignmentRequestSchema(BaseModel):
    cost_matrix: list[list[float]] | None = Field(None, description="Matriz de costos del problema de asignación")
    row_labels: list[str] | None = Field(default=None, description="Etiquetas de filas; opcional")
    col_labels: list[str] | None = Field(default=None, description="Etiquetas de columnas; opcional")
    maximize: bool = Field(False, description="Indica si el objetivo es maximizar en lugar de minimizar")
    forbidden_cells: list[list[bool]] | None = Field(
        default=None,
        description="Máscara opcional: true indica una conexión prohibida.",
    )
    graph: GraphPayloadSchema | None = Field(
        default=None,
        description="Grafo dirigido que se convierte en matriz de costos sin inventar conexiones.",
    )

    @model_validator(mode="after")
    def validate_source(self):
        if (self.cost_matrix is None) == (self.graph is None):
            raise ValueError("Indica exactamente cost_matrix o graph.")
        if self.graph is not None and self.forbidden_cells is not None:
            raise ValueError("forbidden_cells no se combina con graph.")
        return self