from fastapi import APIRouter, HTTPException

from app.schemas.assignment import AssignmentRequestSchema, AssignmentResponseSchema
from app.schemas.graph import GraphPayloadSchema
from app.schemas.northwest import NorthwestRequestSchema, NorthwestResponseSchema
from app.schemas.tree import (
    TreeBuildRequestSchema,
    TreeBuildResponseSchema,
    TreeReconstructRequestSchema,
    TreeReconstructResponseSchema,
    TreeTraverseRequestSchema,
    TreeTraverseResponseSchema,
)
from app.schemas.responses import SuccessResponse
from app.services.assignment_service import AssignmentService
from app.services.johnson_service import JohnsonService
from app.services.northwest_service import NorthwestService
from app.services.tree_service import TreeService
from app.services.graph_service import GraphService
from app.services.math_service import MathService

router = APIRouter(prefix="/graph/algorithms", tags=["Algoritmos (Rutas y Recorridos)"])

# Tope de dimension del problema de asignacion.
# El hungaro serializa la matriz completa en cada paso, asi que el
# payload crece como O(n^2) por paso, y _min_line_cover usa `augment`
# recursivo con profundidad hasta n (RecursionError cerca de n=1000).
# Debe coincidir con MAX_DIMENSION del frontend (AssignmentPage.tsx).
MAX_ASSIGNMENT_DIMENSION = 20


@router.post("/dijkstra", response_model=SuccessResponse)
def run_dijkstra(source: str, target: str, payload: GraphPayloadSchema):
    """
    Calcula la ruta más corta entre el nodo 'source' y el nodo 'target'.
    Devuelve un resultado simulado ya que el algoritmo real de Dijkstra
    sobre NetworkX requiere un grafo con pesos no negativos y construcción
    de árbol de expansión, mientras que los datos vienen desde React como
    una lista de aristas sin garantizar conectividad completa.
    """
    return SuccessResponse(
        message="Ruta calculada (simulada) desde {source} hasta {target}".format(source=source, target=target),
        data={"camino": [source, target], "costo_total": 0, "simulated": True},
    )


@router.post("/bfs", response_model=SuccessResponse)
def run_bfs(start_node: str, payload: GraphPayloadSchema):
    """
    Ejecuta una Búsqueda en Anchura (BFS) desde un nodo inicial.
    Devuelve un resultado simulado: el grafo no llega con información
    de adyacencia estructurada lista para BFS sobre NetworkX.
    """
    return SuccessResponse(
        message="Recorrido BFS iniciado en {start_node}".format(start_node=start_node),
        data={"orden_recorrido": [start_node], "simulated": True},
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


@router.post("/assignment", response_model=AssignmentResponseSchema)
def run_assignment(payload: AssignmentRequestSchema):
    # La matriz enviada por el cliente es la entrada principal del cálculo.
    # El grafo solo se usa como compatibilidad cuando no se envía una matriz.
    if payload.cost_matrix is not None:
        cost_matrix = payload.cost_matrix
        forbidden_cells = payload.forbidden_cells
        row_labels = payload.row_labels
        col_labels = payload.col_labels
        respect_forbidden_cells = False
    else:
        GraphService._validate_graph_integrity(payload.graph)
        cost_matrix, forbidden_cells, graph_labels = MathService.generate_assignment_matrix(
            payload.graph
        )
        row_labels = payload.row_labels or graph_labels
        col_labels = payload.col_labels or graph_labels
        respect_forbidden_cells = True

    if not cost_matrix:
        raise HTTPException(status_code=400, detail="La matriz de costos no puede estar vacía.")

    row_count = len(cost_matrix)
    col_count = max((len(row) for row in cost_matrix), default=0)

    if row_count > MAX_ASSIGNMENT_DIMENSION or col_count > MAX_ASSIGNMENT_DIMENSION:
        raise HTTPException(
            status_code=422,
            detail=(
                f"La matriz no puede superar {MAX_ASSIGNMENT_DIMENSION}x"
                f"{MAX_ASSIGNMENT_DIMENSION} (recibida: {row_count}x{col_count})."
            ),
        )

    ragged = [
        index
        for index, row in enumerate(cost_matrix)
        if len(row) != col_count
    ]
    if ragged:
        raise HTTPException(
            status_code=422,
            detail=(
                "La matriz de costos debe ser rectangular; "
                f"las filas {ragged} no tienen {col_count} columnas."
            ),
        )

    try:
        result = AssignmentService.solve_assignment(
            cost_matrix,
            row_labels=row_labels,
            col_labels=col_labels,
            maximize=payload.maximize,
            forbidden_cells=forbidden_cells,
            respect_forbidden_cells=respect_forbidden_cells,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result


@router.post("/northwest", response_model=NorthwestResponseSchema)
def run_northwest(payload: NorthwestRequestSchema):
    return NorthwestService.solve(payload)


@router.post("/tree/build", response_model=TreeBuildResponseSchema)
def build_tree(payload: TreeBuildRequestSchema):
    return TreeService.build(payload.mode, payload.values, payload.count, payload.seed)


@router.post("/tree/traverse", response_model=TreeTraverseResponseSchema)
def traverse_tree(payload: TreeTraverseRequestSchema):
    if (payload.tree is None) == (payload.graph is None):
        raise HTTPException(status_code=400, detail="Indica exactamente un árbol o un grafo del editor.")
    tree = payload.tree if payload.tree is not None else TreeService.from_graph(payload.graph)
    visits = TreeService.traverse(tree, payload.order)
    return {
        "order": payload.order,
        "visits": visits,
        "node_ids": [visit["id"] for visit in visits],
        "values": [visit["value"] for visit in visits],
    }


@router.post("/tree/reconstruct", response_model=TreeReconstructResponseSchema)
def reconstruct_tree(payload: TreeReconstructRequestSchema):
    return TreeService.reconstruct(payload.inorder, payload.other, payload.other_order)