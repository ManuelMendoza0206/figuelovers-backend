from __future__ import annotations

from heapq import heappop, heappush
from math import inf

from fastapi import HTTPException

from app.schemas.dijkstra import (
    DijkstraRelaxationSchema,
    DijkstraResponseSchema,
    DijkstraStepSchema,
    DijkstraTargetPathSchema,
    DijkstraRequestSchema,
)
from app.services.graph_service import GraphService

# Tope de nodos para Dijkstra.
#
# El limite NO viene del costo del algoritmo (Dijkstra con heap es
# O(E log V), trivial para miles de nodos), sino de la TRAZA: se
# serializa un paso por cada nodo fijado, cada paso incluye sus
# relajaciones y un snapshot de distancias, asi que el payload crece
# como O(V^2) por respuesta. 100 nodos -> ~100 snapshots de 100
# entradas, comparable al espiritu del tope de 20x20 de Asignacion.
# Debe coincidir con MAX_DIJKSTRA_NODES del frontend (dijkstraInput.ts).
MAX_DIJKSTRA_NODES = 100


class DijkstraService:
    """Camino mínimo con origen único, sin librerías de grafos.

    Implementación propia con heapq: la traza (pasos, relajaciones,
    orden de fijado) es la FUENTE REAL del resultado, no una
    reconstrucción posterior. NetworkX no participa a proposito.
    """

    # ================================================================
    # VALIDACIONES
    # ================================================================
    @staticmethod
    def _validate(payload: DijkstraRequestSchema) -> None:
        # Integridad del payload (aristas apuntando a nodos inexistentes):
        # misma validacion que el resto de los servicios de grafos.
        GraphService.validate_import(payload.graph)

        node_ids = [node.id for node in payload.graph.nodes]

        if not node_ids:
            raise HTTPException(
                status_code=400,
                detail="El grafo no tiene nodos: añade al menos un nodo antes de calcular Dijkstra.",
            )

        if len(node_ids) > MAX_DIJKSTRA_NODES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"El grafo tiene {len(node_ids)} nodos; Dijkstra admite hasta "
                    f"{MAX_DIJKSTRA_NODES} nodos para poder serializar la traza paso a paso."
                ),
            )

        if payload.source not in node_ids:
            raise HTTPException(
                status_code=400,
                detail=f"El nodo origen '{payload.source}' no existe en el grafo.",
            )

        if payload.target is not None and payload.target not in node_ids:
            raise HTTPException(
                status_code=400,
                detail=f"El nodo destino '{payload.target}' no existe en el grafo.",
            )

        negative: list[str] = []
        for edge in payload.graph.edges:
            weight = DijkstraService._resolve_weight(edge.weight)
            if weight != weight or weight in (inf, -inf):
                raise HTTPException(
                    status_code=400,
                    detail=f"La arista '{edge.id}' tiene un peso no finito ({edge.weight}).",
                )
            if weight < 0:
                negative.append(f"{edge.id} ({edge.source}→{edge.target}, peso {weight})")

        if negative:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Dijkstra no admite pesos negativos; afecta a: "
                    + ", ".join(negative)
                    + ". Usa Johnson, que sí soporta pesos negativos en grafos dirigidos."
                ),
            )

    @staticmethod
    def _resolve_weight(weight: float | None) -> float:
        # Convención compartida con GraphService: un peso vacío cuenta como 1.
        return 1.0 if weight is None else float(weight)

    # ================================================================
    # ESTRUCTURA
    # ================================================================
    @staticmethod
    def _build_adjacency(payload: DijkstraRequestSchema):
        """Adyacencia dirigida por lista, construida a mano desde el payload.

        NO se usa NetworkX: nx.DiGraph/nx.Graph colapsan las aristas
        paralelas (quedaría solo la última) y no deja registrar los
        self-loops como "ignorados". Acá se conservan todas; los
        self-loops se descartan porque no pueden mejorar ninguna
        distancia.
        """

        adjacency: dict[str, list[tuple[str, float, str]]] = {
            node.id: [] for node in payload.graph.nodes
        }

        self_loops = 0
        weightless: list[str] = []

        for edge in payload.graph.edges:
            if edge.weight is None:
                weightless.append(edge.id)

            if edge.source == edge.target:
                self_loops += 1
                continue

            weight = DijkstraService._resolve_weight(edge.weight)
            adjacency[edge.source].append((edge.target, weight, edge.id))

            # No dirigida => se recorre en ambos sentidos. Dirigida, solo
            # source→target. (A diferencia de Johnson, no se exige que
            # todas sean dirigidas.)
            if not edge.is_directed:
                adjacency[edge.target].append((edge.source, weight, edge.id))

        return adjacency, self_loops, weightless

    # ================================================================
    # ALGORITMO
    # ================================================================
    @staticmethod
    def _reconstruct_path(
        predecessors: dict[str, str | None],
        predecessor_edges: dict[str, str | None],
        source: str,
        target: str,
    ) -> tuple[list[str], list[str]]:
        if source == target:
            return [source], []

        if target not in predecessors or predecessors[target] is None:
            return [], []

        nodes: list[str] = []
        edges: list[str] = []
        current = target
        while current is not None and current != source:
            nodes.append(current)
            edge_id = predecessor_edges.get(current)
            if edge_id is not None:
                edges.append(edge_id)
            current = predecessors[current]

        if current != source:
            return [], []

        nodes.append(source)
        nodes.reverse()
        edges.reverse()
        return nodes, edges

    @staticmethod
    def calculate_shortest_paths(payload: DijkstraRequestSchema) -> DijkstraResponseSchema:
        DijkstraService._validate(payload)

        node_order: dict[str, int] = {
            node.id: index for index, node in enumerate(payload.graph.nodes)
        }
        adjacency, self_loops, weightless = DijkstraService._build_adjacency(payload)

        warnings: list[str] = []
        if self_loops:
            warnings.append(
                f"Se ignoraron {self_loops} bucle(s) (arista de un nodo a sí mismo): "
                "no pueden mejorar ninguna distancia."
            )
        if weightless:
            warnings.append(
                "Las aristas sin peso (" + ", ".join(weightless) + ") se trataron con peso 1."
            )

        distances: dict[str, float | None] = {node: None for node in node_order}
        predecessors: dict[str, str | None] = {node: None for node in node_order}
        predecessor_edges: dict[str, str | None] = {node: None for node in node_order}

        source = payload.source
        distances[source] = 0.0

        # Desempate determinista: a igual distancia gana el nodo de menor
        # índice en payload.nodes (por eso el heap guarda la posición y no
        # el id). Y la relajación solo reemplaza predecesor si la mejora es
        # ESTRICTA: a igual distancia no se cambia nada. Ambas reglas hacen
        # que el resultado sea reproducible byte a byte.
        queue: list[tuple[float, int, str]] = [(0.0, node_order[source], source)]
        fixed: set[str] = set()
        order_visited: list[str] = []
        steps: list[DijkstraStepSchema] = []

        while queue:
            current_distance, _, node = heappop(queue)

            if node in fixed:
                continue  # entrada vieja del heap: ya estaba fijado
            fixed.add(node)
            order_visited.append(node)

            relaxations: list[DijkstraRelaxationSchema] = []

            # Vecinos en orden de aparición en payload.edges: otra capa de
            # determinismo cuando dos aristas llevan al mismo vecino.
            for neighbor, weight, edge_id in adjacency[node]:
                old_distance = distances[neighbor]
                candidate = current_distance + weight
                improved = old_distance is None or candidate < old_distance

                relaxations.append(
                    DijkstraRelaxationSchema(
                        **{
                            "from": node,
                            "to": neighbor,
                        },
                        edge_id=edge_id,
                        old_distance=old_distance,
                        new_distance=candidate,
                        improved=improved,
                    )
                )

                if improved:
                    distances[neighbor] = candidate
                    predecessors[neighbor] = node
                    predecessor_edges[neighbor] = edge_id
                    heappush(queue, (candidate, node_order[neighbor], neighbor))

            steps.append(
                DijkstraStepSchema(
                    step=len(steps) + 1,
                    node=node,
                    distance=float(current_distance),
                    relaxations=relaxations,
                    distances_snapshot=dict(distances),
                    visited_snapshot=list(order_visited),
                )
            )

        paths: dict[str, list[str]] = {}
        for target in node_order:
            nodes_path, _ = DijkstraService._reconstruct_path(
                predecessors, predecessor_edges, source, target
            )
            paths[target] = nodes_path

        target_path: DijkstraTargetPathSchema | None = None
        if payload.target is not None:
            nodes_path, edge_ids = DijkstraService._reconstruct_path(
                predecessors, predecessor_edges, source, payload.target
            )
            total = distances[payload.target]
            target_path = DijkstraTargetPathSchema(
                nodes=nodes_path,
                edges=edge_ids,
                total_distance=float(total) if total is not None else None,
            )
            if total is None:
                warnings.append(
                    f"No hay camino desde '{source}' hasta '{payload.target}': el destino es inalcanzable."
                )

        return DijkstraResponseSchema(
            source=source,
            target=payload.target,
            distances=distances,
            predecessors=predecessors,
            paths=paths,
            order_visited=order_visited,
            steps=steps,
            target_path=target_path,
            warnings=warnings,
        )
