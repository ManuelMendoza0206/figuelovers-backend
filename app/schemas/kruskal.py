from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.graph import GraphPayloadSchema


class KruskalRequestSchema(BaseModel):
    """Entrada del árbol de expansión (MST) de Kruskal.

    El grafo se trata SIEMPRE como no dirigido: la dirección de cada
    arista se ignora (y se avisa cuando hay aristas dirigidas).
    """

    graph: GraphPayloadSchema = Field(..., description="Grafo del editor")
    objective: Literal["min", "max"] = Field(
        "min",
        description=(
            "'min' busca el árbol de expansión MÍNIMA; 'max' el MÁXIMO "
            "(mismo algoritmo ordenando las aristas de mayor a menor)."
        ),
    )


class KruskalEdgeSchema(BaseModel):
    """Arista simple con su peso ya resuelto (vacío = 1)."""

    id: str
    source: str
    target: str
    weight: float


class KruskalStepSchema(BaseModel):
    """Paso de la traza: una arista evaluada y su decisión."""

    step: int
    edge: KruskalEdgeSchema
    decision: Literal["accepted", "rejected"]
    reason: str = Field(
        ..., description='"une componentes distintos" / "formaría un ciclo" / "bucle"'
    )
    components_snapshot: list[list[str]] = Field(
        ..., description="Componentes (listas de ids de nodo) tras aplicar el paso"
    )
    total_weight_so_far: float = Field(
        ..., description="Peso acumulado de las aristas aceptadas hasta el paso"
    )


class KruskalResponseSchema(BaseModel):
    """Resultado de Kruskal: un árbol (o un bosque si el grafo es desconexo)."""

    mst_edges: list[KruskalEdgeSchema] = Field(
        ..., description="Aristas aceptadas, en el orden en que se aceptaron"
    )
    total_weight: float = Field(..., description="Suma de los pesos aceptados")
    components: int = Field(..., description="Cantidad de componentes conexas al terminar")
    is_connected: bool = Field(..., description="True si el grafo es conexo (un solo árbol)")
    sorted_edges: list[str] = Field(
        ..., description="IDs de todas las aristas en el orden en que se procesaron"
    )
    steps: list[KruskalStepSchema] = Field(
        ..., description="Traza completa: TODAS las aristas, aceptadas y rechazadas"
    )
    ignored_directions: bool = Field(
        ..., description="True si el grafo tenía aristas dirigidas (se ignoró la dirección)"
    )
    warnings: list[str] = Field(default_factory=list)
