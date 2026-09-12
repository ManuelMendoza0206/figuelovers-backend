from fastapi import APIRouter
from app.schemas.graph import GraphPayloadSchema
from app.schemas.responses import SuccessResponse
# Aquí luego importaremos el AlgorithmService que crearemos después

router = APIRouter(prefix="/graph/algorithms", tags=["Algoritmos (Rutas y Recorridos)"])

@router.post("/dijkstra")
def run_dijkstra(source: str, target: str, payload: GraphPayloadSchema):
    """
    Calcula la ruta más corta entre el nodo 'source' y el nodo 'target'.
    """
    # TODO: Implementar la lógica de Dijkstra usando NetworkX en el futuro
    return SuccessResponse(
        message=f"Ruta calculada (simulada) desde {source} hasta {target}",
        data={"camino": [source, target], "costo_total": 0}
    )

@router.post("/bfs")
def run_bfs(start_node: str, payload: GraphPayloadSchema):
    """
    Ejecuta una Búsqueda en Anchura (BFS) desde un nodo inicial.
    """
    # TODO: Implementar lógica BFS en el futuro
    return SuccessResponse(
        message=f"Recorrido BFS iniciado en {start_node}",
        data={"orden_recorrido": [start_node]}
    )