from typing import Literal

from pydantic import BaseModel, Field


class NorthwestRequestSchema(BaseModel):
    costs: list[list[float | None]] = Field(
        ..., description="Matriz de costos; null representa una ruta bloqueada"
    )
    supply: list[float] = Field(..., description="Oferta disponible en cada origen")
    demand: list[float] = Field(..., description="Demanda requerida en cada destino")
    row_labels: list[str] = Field(default_factory=list)
    col_labels: list[str] = Field(default_factory=list)


class NorthwestDummySchema(BaseModel):
    type: Literal["origin", "destination"]
    index: int
    quantity: float


class NorthwestBasicCellSchema(BaseModel):
    cell: tuple[int, int]
    quantity: float


class NorthwestBlockedUseSchema(BaseModel):
    cell: tuple[int, int]
    origin: str
    destination: str
    quantity: float


class NorthwestStepSchema(BaseModel):
    step: int
    cell: tuple[int, int]
    quantity: float
    supply_remaining: list[float]
    demand_remaining: list[float]
    closed: Literal["row", "column", "both"]
    degenerate: bool
    note: str
    allocation: list[list[float]]


class NorthwestResponseSchema(BaseModel):
    allocation: list[list[float]]
    basic_cells: list[NorthwestBasicCellSchema]
    total_cost: float | None
    steps: list[NorthwestStepSchema]
    was_balanced: bool
    dummy: NorthwestDummySchema | None
    uses_blocked_routes: bool
    blocked_used: list[NorthwestBlockedUseSchema]
    warnings: list[str]
