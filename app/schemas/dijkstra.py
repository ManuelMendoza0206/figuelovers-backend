from pydantic import BaseModel, ConfigDict, Field

from app.schemas.graph import GraphPayloadSchema


class DijkstraRequestSchema(BaseModel):
    """Entrada del camino mínimo con un origen único.

    A diferencia de Johnson, el grafo puede mezclar aristas dirigidas y
    no dirigidas: cada arista se respeta segun su flag `is_directed`.
    """

    graph: GraphPayloadSchema = Field(
        ..., description="Grafo del editor (puede mezclar dirigidas y no dirigidas)"
    )
    source: str = Field(..., description="ID del nodo origen (obligatorio)")
    target: str | None = Field(
        None,
        description=(
            "ID del nodo destino opcional. Solo sirve para resaltar un camino "
            "concreto: las distancias se calculan siempre a TODOS los nodos."
        ),
    )


class DijkstraRelaxationSchema(BaseModel):
    """Un intento de mejora de distancia saliendo del nodo fijado del paso.

    `from`/`to` llegan serializados con esas claves via alias (son
    palabras reservadas en Python).
    """

    model_config = ConfigDict(populate_by_name=True)

    from_node: str = Field(..., alias="from")
    to_node: str = Field(..., alias="to")
    edge_id: str = Field(..., description="Arista usada en el intento")
    old_distance: float | None = Field(
        ..., description="Distancia conocida antes del intento; null = infinito"
    )
    new_distance: float = Field(..., description="Distancia propuesta por esta arista")
    improved: bool = Field(..., description="True solo si la mejora fue estricta")


class DijkstraStepSchema(BaseModel):
    """Paso de la traza: el nodo que se fija definitivamente."""

    step: int
    node: str = Field(..., description="Nodo cuya distancia queda definitiva")
    distance: float = Field(..., description="Distancia definitiva del nodo")
    relaxations: list[DijkstraRelaxationSchema] = Field(
        default_factory=list,
        description="Intentos de mejora realizados desde el nodo fijado",
    )
    distances_snapshot: dict[str, float | None] = Field(
        ..., description="Mejor distancia conocida de cada nodo tras este paso (null = infinito)"
    )
    visited_snapshot: list[str] = Field(
        ..., description="Nodos fijados hasta este paso, en orden"
    )


class DijkstraTargetPathSchema(BaseModel):
    """Camino final hacia el destino opcional."""

    nodes: list[str] = Field(..., description="Nodos del camino origen → destino")
    edges: list[str] = Field(..., description="IDs de las aristas del camino, en orden")
    total_distance: float | None = Field(
        ..., description="Distancia total del camino; null si el destino es inalcanzable"
    )


class DijkstraResponseSchema(BaseModel):
    """Resultado completo de Dijkstra desde un unico origen."""

    source: str
    target: str | None
    distances: dict[str, float | None] = Field(
        ..., description="Distancia minima desde el origen a cada nodo; null = inalcanzable"
    )
    predecessors: dict[str, str | None] = Field(
        ..., description="Predecesor en el camino minimo; null si aun no tiene"
    )
    paths: dict[str, list[str]] = Field(
        ..., description="Camino minimo origen → cada nodo; lista vacia si es inalcanzable"
    )
    order_visited: list[str] = Field(
        ..., description="Orden en que los nodos quedaron definitivos"
    )
    steps: list[DijkstraStepSchema] = Field(
        ..., description="Traza completa: un paso por cada nodo fijado"
    )
    target_path: DijkstraTargetPathSchema | None = Field(
        None, description="Camino al destino solo si se envio un target"
    )
    warnings: list[str] = Field(default_factory=list)
