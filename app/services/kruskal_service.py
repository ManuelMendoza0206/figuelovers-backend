from __future__ import annotations

from fastapi import HTTPException

from app.schemas.graph import GraphPayloadSchema
from app.schemas.kruskal import (
    KruskalEdgeSchema,
    KruskalRequestSchema,
    KruskalResponseSchema,
    KruskalStepSchema,
)
from app.services.graph_service import GraphService

# Topes de tamaño, documentados igual que MAX_ASSIGNMENT_DIMENSION.
#
# Kruskal ordena todas las aristas y registra UN paso por arista (con su
# snapshot de componentes, que es una lista de listas de nodos), asi que
# el costo dominante es O(E) pasos con snapshots de O(V). 100 nodos y
# 500 aristas dejan la traza en un orden de magnitud manejable para el
# navegador. Deben coincidir con los topes del frontend (kruskalInput.ts).
MAX_KRUSKAL_NODES = 100
MAX_KRUSKAL_EDGES = 500


class _UnionFind:
    """Disjoint-set forest con compresión de caminos y unión por rango.

    Implementado a mano (sin NetworkX ni otras librerías) porque la
    estructura ES el algoritmo: cada `union` decide si una arista se
    acepta o forma ciclo.
    """

    def __init__(self, nodes: list[str]) -> None:
        self.parent: dict[str, str] = {node: node for node in nodes}
        self.rank: dict[str, int] = {node: 0 for node in nodes}

    def find(self, node: str) -> str:
        # Compresión de caminos iterativa: sin riesgo de RecursionError.
        root = node
        while self.parent[root] != root:
            root = self.parent[root]

        while self.parent[node] != root:
            self.parent[node], node = root, self.parent[node]

        return root

    def union(self, first: str, second: str) -> bool:
        """Une los conjuntos. Devuelve False si ya estaban unidos."""
        root_first = self.find(first)
        root_second = self.find(second)

        if root_first == root_second:
            return False

        # Unión por rango: el árbol más chico cuelga del más alto.
        if self.rank[root_first] < self.rank[root_second]:
            root_first, root_second = root_second, root_first
        self.parent[root_second] = root_first
        if self.rank[root_first] == self.rank[root_second]:
            self.rank[root_first] += 1
        return True

    def components(self, node_order: list[str]) -> list[list[str]]:
        """Componentes actuales, en orden determinista.

        Los miembros de cada componente siguen el orden de payload.nodes
        y los componentes se ordenan por su primer miembro: dos corridas
        idénticas producen snapshots idénticos.
        """
        groups: dict[str, list[str]] = {}
        for node in node_order:
            groups.setdefault(self.find(node), []).append(node)
        return list(groups.values())


class KruskalService:
    """Árbol de expansión (mínima o máxima) con union-find propio."""

    # ================================================================
    # VALIDACIONES
    # ================================================================
    @staticmethod
    def _validate(payload: KruskalRequestSchema) -> None:
        # Integridad: aristas que referencian nodos inexistentes -> 400.
        GraphService.validate_import(payload.graph)

        node_count = len(payload.graph.nodes)
        edge_count = len(payload.graph.edges)

        if node_count == 0:
            raise HTTPException(
                status_code=400,
                detail="El grafo no tiene nodos: añade al menos un nodo antes de calcular Kruskal.",
            )

        if node_count > MAX_KRUSKAL_NODES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"El grafo tiene {node_count} nodos; Kruskal admite hasta "
                    f"{MAX_KRUSKAL_NODES} nodos para serializar la traza."
                ),
            )

        if edge_count > MAX_KRUSKAL_EDGES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"El grafo tiene {edge_count} aristas; Kruskal admite hasta "
                    f"{MAX_KRUSKAL_EDGES} aristas (un paso por arista en la traza)."
                ),
            )

        for edge in payload.graph.edges:
            weight = KruskalService._resolve_weight(edge.weight)
            if weight != weight or weight in (float("inf"), float("-inf")):
                raise HTTPException(
                    status_code=400,
                    detail=f"La arista '{edge.id}' tiene un peso no finito ({edge.weight}).",
                )

    @staticmethod
    def _resolve_weight(weight: float | None) -> float:
        # Misma convención que el resto del backend: peso vacío = 1.
        # A diferencia de Dijkstra, acá SÍ se admiten pesos negativos y cero.
        return 1.0 if weight is None else float(weight)

    # ================================================================
    # ALGORITMO
    # ================================================================
    @staticmethod
    def _edge_schema(edge) -> KruskalEdgeSchema:
        return KruskalEdgeSchema(
            id=edge.id,
            source=edge.source,
            target=edge.target,
            weight=KruskalService._resolve_weight(edge.weight),
        )

    @staticmethod
    def calculate_spanning_tree(payload: KruskalRequestSchema) -> KruskalResponseSchema:
        """Kruskal sobre el grafo tratado como NO DIRIGIDO.

        Reglas (documentadas también en la ayuda de la UI):
        - Se ordenan las aristas por peso (ascendente para 'min',
          descendente para 'max'); a igual peso manda el ORDEN ORIGINAL
          de la arista en payload.edges (ordenación estable => desempate
          determinista).
        - Se acepta una arista si une dos componentes distintos; se
          rechaza si forma un ciclo o si es un bucle.
        - Se procesan TODAS las aristas, incluso después de tener n-c
          aceptadas, para que la traza muestre el motivo de cada
          rechazo (decisión documentada; la UI lo refleja).
        - Grafo desconexo => BOSQUE de expansión (un árbol por
          componente), no es un error.
        """
        KruskalService._validate(payload)

        node_order = [node.id for node in payload.graph.nodes]
        edges = payload.graph.edges

        ignored_directions = any(edge.is_directed for edge in edges)

        # Orden determinista: peso y, a igual peso, posición original.
        # `sorted` es estable, pero el índice se iguala explícitamente
        # para que 'max' no dependa del orden de partida.
        indexed = list(enumerate(edges))
        if payload.objective == "max":
            indexed.sort(key=lambda item: (-KruskalService._resolve_weight(item[1].weight), item[0]))
        else:
            indexed.sort(key=lambda item: (KruskalService._resolve_weight(item[1].weight), item[0]))

        union_find = _UnionFind(node_order)

        steps: list[KruskalStepSchema] = []
        mst_edges: list[KruskalEdgeSchema] = []
        total_weight = 0.0

        for _, edge in indexed:
            edge_schema = KruskalService._edge_schema(edge)

            if edge.source == edge.target:
                decision = "rejected"
                reason = "bucle: la arista sale y vuelve al mismo nodo."
            elif union_find.union(edge.source, edge.target):
                decision = "accepted"
                reason = "une dos componentes distintos."
                mst_edges.append(edge_schema)
                total_weight += edge_schema.weight
            else:
                decision = "rejected"
                reason = "formaría un ciclo: sus extremos ya están en el mismo componente."

            steps.append(
                KruskalStepSchema(
                    step=len(steps) + 1,
                    edge=edge_schema,
                    decision=decision,
                    reason=reason,
                    components_snapshot=union_find.components(node_order),
                    total_weight_so_far=total_weight,
                )
            )

        components = union_find.components(node_order)
        component_count = len(components)
        is_connected = component_count == 1

        warnings: list[str] = []
        if ignored_directions:
            warnings.append(
                "Kruskal ignora la dirección de las aristas: el grafo se trató como no dirigido."
            )
        if not is_connected:
            warnings.append(
                f"El grafo es desconexo: el resultado es un bosque de expansión con "
                f"{component_count} componentes (un árbol por componente), no un único árbol."
            )

        return KruskalResponseSchema(
            mst_edges=mst_edges,
            total_weight=total_weight,
            components=component_count,
            is_connected=is_connected,
            sorted_edges=[edge.id for _, edge in indexed],
            steps=steps,
            ignored_directions=ignored_directions,
            warnings=warnings,
        )
