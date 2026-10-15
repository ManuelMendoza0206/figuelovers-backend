from __future__ import annotations

import random
from typing import Any

from fastapi import HTTPException

from app.schemas.graph import GraphPayloadSchema
from app.schemas.tree import TreeNodeSchema, TreeSchema

MAX_TREE_NODES = 31
RANDOM_MIN = 1
RANDOM_MAX = 99


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=message)


class TreeService:
    @staticmethod
    def _validate_values(values: list[Any], label: str) -> list[int]:
        if not values:
            raise _bad_request(f"La cadena {label} no puede estar vacía.")
        if any(not isinstance(value, int) or isinstance(value, bool) for value in values):
            raise _bad_request(f"La cadena {label} solo puede contener números enteros.")
        if len(values) > MAX_TREE_NODES:
            raise _bad_request(f"El árbol no puede superar {MAX_TREE_NODES} nodos.")
        duplicates = sorted({value for value in values if values.count(value) > 1})
        if duplicates:
            raise _bad_request(f"La cadena {label} contiene valores repetidos: {duplicates}.")
        return values

    @staticmethod
    def _tree_from_values(values: list[int]) -> TreeSchema:
        if not values:
            return TreeSchema(root_id=None, nodes=[], edges=[])
        if len(values) > MAX_TREE_NODES:
            raise _bad_request(f"El árbol no puede superar {MAX_TREE_NODES} nodos.")
        if len(set(values)) != len(values):
            repeated = sorted({value for value in values if values.count(value) > 1})
            raise _bad_request(f"No se permiten valores repetidos: {repeated}.")

        records: dict[int, dict[str, int | None]] = {}
        root_value = values[0]
        records[root_value] = {"left": None, "right": None}
        for value in values[1:]:
            current = root_value
            while True:
                side = "left" if value < current else "right"
                child = records[current][side]
                if child is None:
                    records[current][side] = value
                    records[value] = {"left": None, "right": None}
                    break
                current = child

        nodes = [
            TreeNodeSchema(
                id=f"tree-{value}",
                value=value,
                left=f"tree-{children['left']}" if children["left"] is not None else None,
                right=f"tree-{children['right']}" if children["right"] is not None else None,
            )
            for value, children in records.items()
        ]
        edges = [
            {"source": node.id, "target": child}
            for node in nodes
            for child in (node.left, node.right)
            if child is not None
        ]
        return TreeSchema(root_id=f"tree-{root_value}", nodes=nodes, edges=edges)

    @staticmethod
    def _validate_tree(tree: TreeSchema) -> dict[str, TreeNodeSchema]:
        by_id = {node.id: node for node in tree.nodes}
        if len(by_id) != len(tree.nodes):
            raise _bad_request("El árbol contiene identificadores de nodo repetidos.")
        if len(tree.nodes) > MAX_TREE_NODES:
            raise _bad_request(f"El árbol no puede superar {MAX_TREE_NODES} nodos.")
        if not tree.nodes:
            if tree.root_id is not None:
                raise _bad_request("Un árbol vacío no puede declarar una raíz.")
            return by_id
        if tree.root_id not in by_id:
            raise _bad_request("La raíz indicada no existe en el árbol.")
        if len({node.value for node in tree.nodes}) != len(tree.nodes):
            raise _bad_request("Los valores de los nodos deben ser únicos.")

        parents: dict[str, int] = {node_id: 0 for node_id in by_id}
        for node in tree.nodes:
            if node.left == node.right and node.left is not None:
                raise _bad_request(f"El nodo {node.id} no puede tener el mismo hijo en ambos lados.")
            for child in (node.left, node.right):
                if child is None:
                    continue
                if child not in by_id:
                    raise _bad_request(f"El hijo {child} del nodo {node.id} no existe.")
                parents[child] += 1
                if parents[child] > 1:
                    raise _bad_request(f"El nodo {child} tiene más de un padre.")
        if parents[tree.root_id] != 0:
            raise _bad_request("La raíz no puede tener padre.")
        if any(count != (0 if node_id == tree.root_id else 1) for node_id, count in parents.items()):
            raise _bad_request("El árbol debe tener una sola raíz y todos los nodos deben pertenecer a ella.")

        visited: set[str] = set()
        stack = [tree.root_id]
        while stack:
            node_id = stack.pop()
            if node_id in visited:
                raise _bad_request("El grafo contiene un ciclo.")
            visited.add(node_id)
            node = by_id[node_id]
            stack.extend(child for child in (node.left, node.right) if child is not None)
        if len(visited) != len(by_id):
            raise _bad_request("El árbol debe ser conexo.")
        return by_id

    @staticmethod
    def _traverse(tree: TreeSchema, order: str) -> list[TreeNodeSchema]:
        by_id = TreeService._validate_tree(tree)
        if tree.root_id is None:
            return []
        output: list[TreeNodeSchema] = []
        if order == "preorder":
            stack = [tree.root_id]
            while stack:
                node = by_id[stack.pop()]
                output.append(node)
                if node.right:
                    stack.append(node.right)
                if node.left:
                    stack.append(node.left)
            return output
        if order == "inorder":
            stack: list[str] = []
            current: str | None = tree.root_id
            while current is not None or stack:
                while current is not None:
                    stack.append(current)
                    current = by_id[current].left
                current = stack.pop()
                node = by_id[current]
                output.append(node)
                current = node.right
            return output
        stack: list[tuple[str, bool]] = [(tree.root_id, False)]
        while stack:
            node_id, visited = stack.pop()
            if visited:
                output.append(by_id[node_id])
                continue
            stack.append((node_id, True))
            node = by_id[node_id]
            if node.right:
                stack.append((node.right, False))
            if node.left:
                stack.append((node.left, False))
        return output

    @staticmethod
    def _is_bst(tree: TreeSchema) -> bool:
        inorder = [node.value for node in TreeService._traverse(tree, "inorder")]
        return all(first < second for first, second in zip(inorder, inorder[1:]))

    @staticmethod
    def _traversals(tree: TreeSchema) -> dict[str, list[int]]:
        return {
            order: [node.value for node in TreeService._traverse(tree, order)]
            for order in ("preorder", "inorder", "postorder")
        }

    @staticmethod
    def build(mode: str, values: list[Any] | None, count: int | None, seed: int | None) -> dict:
        if mode == "values":
            if values is None:
                raise _bad_request("Indica los valores que se insertarán.")
            normalized = TreeService._validate_values(values, "de entrada")
        else:
            if count is None or count < 1 or count > MAX_TREE_NODES:
                raise _bad_request(f"La cantidad aleatoria debe estar entre 1 y {MAX_TREE_NODES}.")
            normalized = random.Random(seed).sample(range(RANDOM_MIN, RANDOM_MAX + 1), count)
        tree = TreeService._tree_from_values(normalized)
        return {"tree": tree, "traversals": TreeService._traversals(tree)}

    @staticmethod
    def from_graph(graph: GraphPayloadSchema) -> TreeSchema:
        nodes = {node.id: node for node in graph.nodes}
        if not nodes:
            raise _bad_request("El grafo del editor no contiene nodos.")
        if len(nodes) != len(graph.nodes):
            raise _bad_request("El grafo contiene identificadores de nodo repetidos.")
        children: dict[str, list[str]] = {node_id: [] for node_id in nodes}
        parent_count = {node_id: 0 for node_id in nodes}
        undirected_edges = []
        for edge in graph.edges:
            if not edge.is_directed:
                raise _bad_request("Todas las aristas del árbol deben ser dirigidas de padre a hijo.")
            if edge.source not in nodes or edge.target not in nodes:
                raise _bad_request(f"La arista {edge.id} apunta a un nodo inexistente.")
            children[edge.source].append(edge.target)
            parent_count[edge.target] += 1
            if len(children[edge.source]) > 2:
                raise _bad_request(f"El nodo {edge.source} tiene más de dos hijos.")
            if parent_count[edge.target] > 1:
                raise _bad_request(f"El nodo {edge.target} tiene más de un padre.")
            undirected_edges.append((edge.source, edge.target))

        roots = [node_id for node_id, count in parent_count.items() if count == 0]
        if len(roots) != 1:
            raise _bad_request("El grafo debe tener exactamente una raíz.")
        if len(undirected_edges) != len(nodes) - 1:
            raise _bad_request("El grafo debe ser conexo y no contener ciclos.")

        state: dict[str, int] = {}
        for start_node in nodes:
            if state.get(start_node) == 2:
                continue
            stack: list[tuple[str, bool]] = [(start_node, False)]
            while stack:
                node_id, leaving = stack.pop()
                if leaving:
                    state[node_id] = 2
                    continue
                if state.get(node_id) == 1:
                    raise _bad_request("El grafo contiene un ciclo.")
                if state.get(node_id) == 2:
                    continue
                state[node_id] = 1
                stack.append((node_id, True))
                for child_id in children[node_id]:
                    if state.get(child_id) == 1:
                        raise _bad_request("El grafo contiene un ciclo.")
                    if state.get(child_id) != 2:
                        stack.append((child_id, False))

        resolved_children: dict[str, tuple[str | None, str | None]] = {}
        for parent_id, child_ids in children.items():
            left: str | None = None
            right: str | None = None
            if len(child_ids) == 2:
                explicit = [nodes[child_id].data.get("treeSide") if nodes[child_id].data else None for child_id in child_ids]
                if set(explicit) == {"left", "right"}:
                    left = child_ids[explicit.index("left")]
                    right = child_ids[explicit.index("right")]
                else:
                    # Without both explicit sides, horizontal positions define left/right.
                    parent_position = nodes[parent_id].position
                    if parent_position is None or any(nodes[child_id].position is None for child_id in child_ids):
                        raise _bad_request(f"Los dos hijos de {parent_id} necesitan treeSide o posiciones para decidir izquierda/derecha.")
                    ordered = sorted(child_ids, key=lambda child_id: nodes[child_id].position.x)
                    left, right = ordered
            elif len(child_ids) == 1:
                child_id = child_ids[0]
                side = nodes[child_id].data.get("treeSide") if nodes[child_id].data else None
                if side not in (None, "left", "right"):
                    raise _bad_request(f"El lado de {child_id} debe ser left o right.")
                if side == "right":
                    right = child_id
                else:
                    left = child_id
            resolved_children[parent_id] = (left, right)

        tree_nodes: list[TreeNodeSchema] = []
        used_values: set[int] = set()
        for node_id, node in nodes.items():
            raw_value = node.data.get("treeValue") if node.data else None
            if raw_value is None:
                raw_value = node.label
            if isinstance(raw_value, bool):
                raise _bad_request(f"El nodo {node_id} debe tener un valor entero.")
            try:
                value = int(raw_value)
            except (TypeError, ValueError):
                raise _bad_request(f"El nodo {node_id} debe tener un valor entero (treeValue o etiqueta numérica).")
            if str(value) != str(raw_value).strip() or value in used_values:
                raise _bad_request("Los valores enteros de los nodos deben ser únicos.")
            used_values.add(value)
            left, right = resolved_children[node_id]
            tree_nodes.append(TreeNodeSchema(id=node_id, value=value, left=left, right=right))
        tree = TreeSchema(
            root_id=roots[0],
            nodes=tree_nodes,
            edges=[{"source": source, "target": target} for source, target in undirected_edges],
        )
        TreeService._validate_tree(tree)
        return tree

    @staticmethod
    def traverse(tree: TreeSchema, order: str) -> list[dict[str, Any]]:
        return [{"id": node.id, "value": node.value} for node in TreeService._traverse(tree, order)]

    @staticmethod
    def reconstruct(inorder: list[Any], other: list[Any], other_order: str) -> dict:
        first = TreeService._validate_values(inorder, "in-order")
        second = TreeService._validate_values(other, other_order)
        if len(first) != len(second):
            raise _bad_request("Los recorridos deben tener la misma cantidad de valores.")
        only_first = sorted(set(first) - set(second))
        only_second = sorted(set(second) - set(first))
        if only_first or only_second:
            raise _bad_request(
                f"Los recorridos contienen valores distintos: solo en in-order: {only_first}; "
                f"solo en {other_order}: {only_second}."
            )
        if len(first) > MAX_TREE_NODES:
            raise _bad_request(f"El árbol no puede superar {MAX_TREE_NODES} nodos.")

        index_by_value = {value: index for index, value in enumerate(first)}
        cursor = 0 if other_order == "preorder" else len(second) - 1

        def build(start: int, end: int) -> int | None:
            nonlocal cursor
            if start > end:
                return None
            value = second[cursor]
            cursor += 1 if other_order == "preorder" else -1
            split = index_by_value.get(value, -1)
            if split < start or split > end:
                raise ValueError("inconsistent")
            left = build(start, split - 1) if other_order == "preorder" else None
            right = build(split + 1, end) if other_order == "preorder" else None
            if other_order == "postorder":
                right = build(split + 1, end)
                left = build(start, split - 1)
            nodes_by_value[value] = {"left": left, "right": right}
            return value

        nodes_by_value: dict[int, dict[str, int | None]] = {}
        try:
            root = build(0, len(first) - 1)
            if cursor != (len(second) if other_order == "preorder" else -1):
                raise ValueError("inconsistent")
        except (IndexError, ValueError):
            raise _bad_request("Los recorridos no son compatibles entre sí.")

        nodes = [
            TreeNodeSchema(
                id=f"tree-{value}",
                value=value,
                left=f"tree-{children['left']}" if children["left"] is not None else None,
                right=f"tree-{children['right']}" if children["right"] is not None else None,
            )
            for value, children in nodes_by_value.items()
        ]
        edges = [
            {"source": node.id, "target": child}
            for node in nodes
            for child in (node.left, node.right)
            if child is not None
        ]
        tree = TreeSchema(root_id=f"tree-{root}" if root is not None else None, nodes=nodes, edges=edges)
        return {"tree": tree, "traversals": TreeService._traversals(tree), "is_bst": TreeService._is_bst(tree)}
