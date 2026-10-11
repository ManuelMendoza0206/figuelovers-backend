import networkx as nx
from app.schemas.responses import AdjacencyMatrixResponse

class MathService:
    @staticmethod
    def generate_adjacency_matrix(G: nx.Graph | nx.DiGraph) -> AdjacencyMatrixResponse:
        """
        Convierte un grafo de NetworkX en una Matriz de Adyacencia estructurada
        para ser consumida por React.
        """
        nodes_list = list(G.nodes())
        
        try:
            matrix_array = nx.to_numpy_array(G, nodelist=nodes_list, weight='weight')
        except Exception as e:
             raise ValueError(f"Error interno al calcular matriz: {str(e)}")

        matrix_list = matrix_array.tolist()
        is_directed = isinstance(G, nx.DiGraph)
        return AdjacencyMatrixResponse(
            nodes=nodes_list,
            matrix=matrix_list,
            is_directed=is_directed
        )
        
    @staticmethod
    def generate_adjacency_list(G: nx.Graph | nx.DiGraph) -> dict[str, list[dict]]:
        """
        Convierte el grafo en una Lista de Adyacencia (muy útil para depuración).
        Retorna: {'A': [{'target': 'B', 'weight': 5}], 'B': []}
        """
        adj_list = {}
        for node in G.nodes():
            connections = []
            for neighbor in G.neighbors(node):
                edge_data = G.get_edge_data(node, neighbor)
                weight = edge_data.get('weight', 1.0)
                connections.append({"target": neighbor, "weight": weight})
            adj_list[str(node)] = connections
            
        return adj_list