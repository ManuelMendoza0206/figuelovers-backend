from typing import Any
from pydantic import BaseModel, Field, root_validator, ConfigDict

class Position(BaseModel):
    """Posición espacial en el lienzo de React."""
    x: float
    y: float


class NodeSchema(BaseModel):
    """Representación de un vértice en el grafo."""
    id: str = Field(..., description="Identificador único del nodo (ej: 'node-1', 'A')")
    label: str | None = Field(None, description="Etiqueta visible para el usuario")
    position: Position | None = Field(None, description="Posición en el Canvas del Frontend")
    data: dict[str, Any] | None = Field(default_factory=dict, description="Atributos genéricos adicionales")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "A",
                "label": "Ciudad 1",
                "position": {"x": 100, "y": 250},
                "data": {"color": "blue"}
            }
        }
    )

class EdgeSchema(BaseModel):
    """Representación de una conexión entre dos nodos."""
    id: str = Field(..., description="Identificador único de la arista")
    source: str = Field(..., description="ID del nodo de origen")
    target: str = Field(..., description="ID del nodo destino")
    weight: float | None = Field(1.0, description="Peso, costo o distancia de la arista. Valores negativos solo permitidos para aristas dirigidas (usar con Johnson).")
    is_directed: bool = Field(False, description="¿Es una arista dirigida (flecha)?")
    label: str | None = Field(None, description="Etiqueta visual del peso (opcional)")

    @root_validator(skip_on_failure=True)
    def check_negative_weight(cls, values):
        weight = values.get("weight")
        is_directed = values.get("is_directed")
        if weight is not None and weight < 0 and not is_directed:
            raise ValueError("Negative weights are only allowed for directed edges (use Johnson algorithm)")
        return values

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "e1-2",
                "source": "A",
                "target": "B",
                "weight": 15.5,
                "is_directed": True
            }
        }
    )

class GraphPayloadSchema(BaseModel):
    """Estructura completa que envía el Frontend a FastAPI."""
    nodes: list[NodeSchema] = Field(..., description="Lista de todos los vértices")
    edges: list[EdgeSchema] = Field(..., description="Lista de todas las conexiones")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nodes": [
                    {"id": "A", "label": "A"},
                    {"id": "B", "label": "B"}
                ],
                "edges": [
                    {"id": "eA-B", "source": "A", "target": "B", "weight": 5.0, "is_directed": False}
                ]
            }
        }
    )

class GraphFileMetadata(BaseModel):
    """Metadata descriptiva del archivo exportado."""
    version: str = Field("1.0.0", description="Versión del formato de archivo, para futuras migraciones")
    name: str | None = Field(None, description="Nombre opcional del proyecto/grafo dado por el usuario")
    created_at: str | None = Field(None, description="Fecha ISO de creación/exportación, generada en el Frontend")


class GraphFileSchema(BaseModel):
    """
    Formato completo de archivo .json que se exporta desde el Frontend
    y se vuelve a importar para restaurar el grafo en la pizarra.
    """
    metadata: GraphFileMetadata = Field(default_factory=GraphFileMetadata)
    graph: GraphPayloadSchema = Field(..., description="Nodos y aristas del grafo guardado")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "metadata": {"version": "1.0.0", "name": "Mi Grafo", "created_at": "2026-08-30T12:00:00Z"},
                "graph": {
                    "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
                    "edges": [{"id": "eA-B", "source": "A", "target": "B", "weight": 5.0, "is_directed": False}]
                }
            }
        }
    )