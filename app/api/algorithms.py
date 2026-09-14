from fastapi import APIRouter, HTTPException

from app.schemas.assignment import AssignmentRequestSchema
from app.schemas.graph import GraphPayloadSchema
from app.schemas.responses import SuccessResponse
from app.services.assignment_service import AssignmentService
from app.services.johnson_service import JohnsonService

router = APIRouter(prefix="/graph/algorithms", tags=["Algoritmos (Rutas y Recorridos)"])


@router.post("/dijkstra")
def run_dijkstra(source: str, target: str, payload: GraphPayloadSchema):
    """
    Calcula la ruta más corta entre el nodo 'source' y el nodo 'target'.
    """
    return SuccessResponse(
        message=f"Ruta calculada (simulada) desde {source} hasta {target}",
        data={"camino": [source, target], "costo_total": 0},
    )


@router.post("/bfs")
def run_bfs(start_node: str, payload: GraphPayloadSchema):
    """
    Ejecuta una Búsqueda en Anchura (BFS) desde un nodo inicial.
    """
    return SuccessResponse(
        message=f"Recorrido BFS iniciado en {start_node}",
        data={"orden_recorrido": [start_node]},
    )


@router.post("/johnson")
def run_johnson(payload: GraphPayloadSchema):
    result = JohnsonService.calculate_all_pairs_shortest_paths(payload)
    if result.get("has_negative_cycle"):
        return {
            "has_negative_cycle": True,
            "message": result["message"],
        }

    return {
        "distances": result["distances"],
        "paths": result["paths"],
        "has_negative_cycle": False,
    }


@router.post("/assignment")
def run_assignment(payload: AssignmentRequestSchema):
    if not payload.cost_matrix:
        raise HTTPException(status_code=400, detail="La matriz de costos no puede estar vacía.")

    result = AssignmentService.solve_assignment(
        payload.cost_matrix,
        row_labels=payload.row_labels,
        col_labels=payload.col_labels,
        maximize=payload.maximize,
    )
    return result