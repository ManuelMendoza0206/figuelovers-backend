import networkx as nx
from fastapi import HTTPException
from app.schemas.graph import GraphPayloadSchema


class GraphService:
    @staticmethod
    def _validate_graph_integrity(payload: GraphPayloadSchema) -> None:
        """
        Valida que el grafo enviado por el Frontend sea lógicamente consistente.
        """
        valid_node_ids = {node.id for node in payload.nodes}
        for edge in payload.edges:
            if edge.source not in valid_node_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"Inconsistencia: La arista {edge.id} tiene un origen inválido ({edge.source})."
                )
            if edge.target not in valid_node_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"Inconsistencia: La arista {edge.id} tiene un destino inválido ({edge.target})."
                )

    @staticmethod
    def build_networkx_graph(payload: GraphPayloadSchema) -> nx.Graph | nx.DiGraph:
        """
        Convierte el payload de React a un objeto de NetworkX.
        Detecta automáticamente si el grafo es dirigido o no.
        """
        # Ejecutar validación de integridad primero
        GraphService._validate_graph_integrity(payload)

        # Determinar si el grafo debe ser dirigido (DiGraph) o no (Graph)
        # Si al menos UNA arista es dirigida, tratamos todo el grafo como dirigido.
        is_directed_graph = any(edge.is_directed for edge in payload.edges)

        G = nx.DiGraph() if is_directed_graph else nx.Graph()

        # Insertar nodos
        for node in payload.nodes:
            # Guardamos los atributos extra (como label o position) dentro del nodo en NetworkX
            G.add_node(
                node.id,
                label=node.label,
                position=node.position.model_dump() if node.position else None
            )

        # Insertar aristas
        for edge in payload.edges:
            # En NetworkX, los pesos por defecto suelen llamarse 'weight'
            G.add_edge(
                edge.source,
                edge.target,
                weight=edge.weight if edge.weight is not None else 1.0,
                id=edge.id
            )

        return G

    @staticmethod
    def validate_import(payload: GraphPayloadSchema) -> GraphPayloadSchema:
        """
        Valida un grafo proveniente de un archivo JSON importado (sin construir
        el objeto de NetworkX, ya que para importar solo nos interesa confirmar
        que la estructura sea consistente antes de cargarla a la pizarra).

        Retorna el mismo payload si es válido, o lanza HTTPException 400 si
        encuentra alguna inconsistencia (aristas apuntando a nodos inexistentes, etc.).
        """
        GraphService._validate_graph_integrity(payload)
        return payload