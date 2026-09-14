from __future__ import annotations

from heapq import heappop, heappush
from math import inf

from fastapi import HTTPException

from app.schemas.graph import GraphPayloadSchema
from app.services.graph_service import GraphService


class JohnsonService:
    @staticmethod
    def _validate_directed_graph(payload: GraphPayloadSchema) -> None:
        if not payload.edges:
            return

        if any(not edge.is_directed for edge in payload.edges):
            raise HTTPException(
                status_code=400,
                detail="El algoritmo de Johnson requiere un grafo dirigido. Convierte la arista a dirigida o crea un grafo dirigido válido.",
            )

    @staticmethod
    def _build_super_source_graph(G):
        super_source = "__johnson_super_source__"
        graph = G.copy()
        for node in list(graph.nodes()):
            graph.add_edge(super_source, node, weight=0.0)
        return graph, super_source

    @staticmethod
    def _bellman_ford(graph, source: str):
        distance = {node: inf for node in graph.nodes()}
        distance[source] = 0.0

        for _ in range(len(graph.nodes()) - 1):
            updated = False
            for u, v, data in graph.edges(data=True):
                weight = float(data.get("weight", 1.0))
                if distance.get(u, inf) != inf and distance[u] + weight < distance.get(v, inf):
                    distance[v] = distance[u] + weight
                    updated = True
            if not updated:
                break

        for u, v, data in graph.edges(data=True):
            weight = float(data.get("weight", 1.0))
            if distance.get(u, inf) != inf and distance[u] + weight < distance.get(v, inf):
                return None

        return distance

    @staticmethod
    def _reconstruct_path(predecessors: dict[str, str | None], source: str, target: str) -> list[str]:
        if source == target:
            return [source]

        if target not in predecessors or predecessors[target] is None:
            return []

        path: list[str] = []
        current = target
        while current is not None and current != source:
            path.append(current)
            current = predecessors[current]

        if current != source:
            return []

        path.append(source)
        path.reverse()
        return path

    @staticmethod
    def calculate_all_pairs_shortest_paths(payload: GraphPayloadSchema):
        JohnsonService._validate_directed_graph(payload)
        graph = GraphService.build_networkx_graph(payload)

        if not graph.nodes():
            return {
                "distances": {},
                "paths": {},
                "has_negative_cycle": False,
            }

        if not isinstance(graph, __import__("networkx").DiGraph):
            raise HTTPException(
                status_code=400,
                detail="El algoritmo de Johnson requiere un grafo dirigido. Usa aristas dirigidas para cada conexión.",
            )

        super_graph, super_source = JohnsonService._build_super_source_graph(graph)
        distances_from_source = JohnsonService._bellman_ford(super_graph, super_source)
        if distances_from_source is None:
            return {
                "has_negative_cycle": True,
                "message": "El grafo contiene un ciclo de peso negativo; no se puede calcular Johnson.",
            }

        potentials = {
            node: distances_from_source.get(node, 0.0) for node in graph.nodes()
        }

        reweighted_graph = graph.copy()
        for u, v, data in graph.edges(data=True):
            weight = float(data.get("weight", 1.0))
            adjusted_weight = weight + potentials.get(u, 0.0) - potentials.get(v, 0.0)
            reweighted_graph[u][v]["weight"] = adjusted_weight

        distances: dict[str, dict[str, float | None]] = {}
        paths: dict[str, dict[str, list[str]]] = {}

        for source in graph.nodes():
            queue: list[tuple[float, str]] = [(0.0, source)]
            dist = {node: inf for node in graph.nodes()}
            predecessors: dict[str, str | None] = {node: None for node in graph.nodes()}
            hop_count = {node: inf for node in graph.nodes()}
            dist[source] = 0.0
            hop_count[source] = 0

            while queue:
                current_distance, node = heappop(queue)
                if current_distance > dist.get(node, inf):
                    continue

                for neighbor, data in reweighted_graph.adj[node].items():
                    edge_weight = float(data.get("weight", 1.0))
                    candidate = current_distance + edge_weight
                    next_hops = hop_count.get(node, inf) + 1
                    if (
                        candidate < dist.get(neighbor, inf)
                        or (
                            abs(candidate - dist.get(neighbor, inf)) < 1e-9
                            and next_hops < hop_count.get(neighbor, inf)
                        )
                    ):
                        dist[neighbor] = candidate
                        predecessors[neighbor] = node
                        hop_count[neighbor] = next_hops
                        heappush(queue, (candidate, neighbor))

            source_distances: dict[str, float | None] = {}
            source_paths: dict[str, list[str]] = {}

            for target in graph.nodes():
                if target == source:
                    source_distances[target] = 0.0
                    source_paths[target] = [source]
                    continue

                if dist.get(target, inf) == inf:
                    source_distances[target] = None
                    source_paths[target] = []
                    continue

                original_distance = dist[target] - potentials.get(source, 0.0) + potentials.get(target, 0.0)
                path = JohnsonService._reconstruct_path(predecessors, source, target)
                source_distances[target] = original_distance
                source_paths[target] = path

            distances[str(source)] = source_distances
            paths[str(source)] = source_paths

        return {
            "distances": distances,
            "paths": paths,
            "has_negative_cycle": False,
        }
