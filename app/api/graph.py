from fastapi import APIRouter
from app.schemas.graph import GraphPayloadSchema, GraphFileSchema
from app.schemas.responses import SuccessResponse
from app.services.graph_service import GraphService
from app.services.math_service import MathService

router = APIRouter(prefix="/graph", tags=["Procesamiento de Grafos"])


@router.post("/validate", response_model=SuccessResponse)
def validate_and_process_graph(payload: GraphPayloadSchema):
    """
    Recibe el grafo desde React, lo valida lógicamente y genera
    su Matriz y Lista de Adyacencia en tiempo real.
    """
    # 1. Validar integridad y construir en NetworkX
    G = GraphService.build_networkx_graph(payload)

    # 2. Usar los servicios matemáticos para obtener los datos puros
    matrix_response = MathService.generate_adjacency_matrix(G)
    adjacency_list = MathService.generate_adjacency_list(G)

    # 3. Retornar todo estructurado
    return SuccessResponse(
        message="Grafo validado y procesado exitosamente.",
        data={
            "estadisticas": {
                "total_nodos": G.number_of_nodes(),
                "total_aristas": G.number_of_edges(),
                "es_dirigido": matrix_response.is_directed
            },
            "nodos": [
                {"id": node_id, "data": attributes.get("data")}
                for node_id, attributes in G.nodes(data=True)
            ],
            "matriz_adyacencia": matrix_response.model_dump(),
            "lista_adyacencia": adjacency_list
        }
    )


@router.post("/import", response_model=SuccessResponse)
def import_graph_file(file: GraphFileSchema):
    """
    Recibe un archivo de grafo (formato GraphFileSchema, con metadata + graph)
    proveniente de un JSON importado por el usuario, valida que su estructura
    sea lógicamente consistente (aristas con nodos existentes, etc.) y lo
    retorna listo para que el Frontend lo cargue en la pizarra.

    No construye el grafo en NetworkX aquí: solo se valida integridad,
    ya que el objetivo es restaurar el estado tal cual en React.
    """
    # 1. Validar integridad del grafo importado
    validated_payload = GraphService.validate_import(file.graph)

    # 2. Retornar el grafo validado junto con su metadata original
    return SuccessResponse(
        message="Archivo de grafo importado y validado exitosamente.",
        data={
            "metadata": file.metadata.model_dump(),
            "graph": validated_payload.model_dump()
        }
    )