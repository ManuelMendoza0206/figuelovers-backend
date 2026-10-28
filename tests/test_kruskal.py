import copy
import json
from pathlib import Path

import networkx as nx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.graph import GraphPayloadSchema
from app.schemas.kruskal import KruskalRequestSchema
from app.services.kruskal_service import KruskalService


client = TestClient(app)

ENDPOINT = "/api/v1/graph/algorithms/kruskal"


def make_graph(nodes, edges, objective="min"):
    return {
        "graph": {
            "nodes": [{"id": node} for node in nodes],
            "edges": [
                {
                    "id": edge_id,
                    "source": source,
                    "target": target,
                    "weight": weight,
                    "is_directed": directed,
                }
                for edge_id, source, target, weight, directed in edges
            ],
        },
        "objective": objective,
    }


# Grafo no dirigido del enunciado, valores calculados a mano:
#   A-B 1, B-C 2, A-C 3, C-D 4, B-D 5, D-E 6, C-E 7
# Orden por peso: AB(1) BC(2) AC(3) CD(4) BD(5) DE(6) CE(7)
# Aceptan: AB, BC, CD, DE (4 = n-1 aristas); rechazan AC, BD, CE por
# ciclo. Total = 1 + 2 + 4 + 6 = 13.
UNDIRECTED_EXAMPLE = [
    ("eAB", "A", "B", 1.0, False),
    ("eBC", "B", "C", 2.0, False),
    ("eAC", "A", "C", 3.0, False),
    ("eCD", "C", "D", 4.0, False),
    ("eBD", "B", "D", 5.0, False),
    ("eDE", "D", "E", 6.0, False),
    ("eCE", "C", "E", 7.0, False),
]


def test_kruskal_minimum_example_accepts_and_rejects_each_edge():
    payload = make_graph(["A", "B", "C", "D", "E"], UNDIRECTED_EXAMPLE)
    response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 200, response.text
    body = response.json()

    assert [edge["id"] for edge in body["mst_edges"]] == ["eAB", "eBC", "eCD", "eDE"]
    assert body["total_weight"] == 13
    assert body["components"] == 1
    assert body["is_connected"] is True
    assert body["ignored_directions"] is False

    # Todas las aristas se procesan, en orden de peso.
    assert body["sorted_edges"] == ["eAB", "eBC", "eAC", "eCD", "eBD", "eDE", "eCE"]
    assert [step["edge"]["id"] for step in body["steps"]] == body["sorted_edges"]

    decisions = {step["edge"]["id"]: step["decision"] for step in body["steps"]}
    assert decisions == {
        "eAB": "accepted", "eBC": "accepted", "eAC": "rejected",
        "eCD": "accepted", "eBD": "rejected", "eDE": "accepted", "eCE": "rejected",
    }

    rejected_ac = next(step for step in body["steps"] if step["edge"]["id"] == "eAC")
    assert "ciclo" in rejected_ac["reason"]

    # Peso acumulado y componentes coherentes paso a paso.
    assert body["steps"][0]["total_weight_so_far"] == 1
    assert body["steps"][-1]["total_weight_so_far"] == 13
    last_components = body["steps"][-1]["components_snapshot"]
    assert len(last_components) == 1
    assert sorted(last_components[0]) == ["A", "B", "C", "D", "E"]


def test_kruskal_maximum_spanning_tree_on_same_graph():
    # Máximo, calculado a mano: orden descendente CE(7) DE(6) BD(5)
    # CD(4) AC(3) BC(2) AB(1). Aceptan CE, DE, BD y AC (3 se une al
    # componente ya formado); total = 7 + 6 + 5 + 3 = 21.
    payload = make_graph(["A", "B", "C", "D", "E"], UNDIRECTED_EXAMPLE, objective="max")
    response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 200, response.text
    body = response.json()

    assert [edge["id"] for edge in body["mst_edges"]] == ["eCE", "eDE", "eBD", "eAC"]
    assert body["total_weight"] == 21
    assert body["components"] == 1
    assert body["is_connected"] is True
    assert body["sorted_edges"] == ["eCE", "eDE", "eBD", "eCD", "eAC", "eBC", "eAB"]


def test_kruskal_disconnected_graph_returns_forest_with_warning():
    payload = make_graph(["A", "B", "C", "D", "E", "F"], UNDIRECTED_EXAMPLE)
    response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["is_connected"] is False
    assert body["components"] == 2
    assert body["total_weight"] == 13
    assert any("bosque" in warning.lower() for warning in body["warnings"])

    # El nodo aislado F forma su propio componente en el snapshot final.
    final_components = body["steps"][-1]["components_snapshot"]
    assert len(final_components) == 2
    assert ["F"] in final_components


def test_kruskal_ignores_directed_edges_and_warns():
    directed_example = [
        (edge_id, source, target, weight, True)
        for edge_id, source, target, weight, _ in UNDIRECTED_EXAMPLE
    ]
    payload = make_graph(["A", "B", "C", "D", "E"], directed_example)
    response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["ignored_directions"] is True
    assert any("dirección" in warning.lower() for warning in body["warnings"])
    # Mismo resultado que la versión no dirigida.
    assert [edge["id"] for edge in body["mst_edges"]] == ["eAB", "eBC", "eCD", "eDE"]
    assert body["total_weight"] == 13


def test_kruskal_accepts_negative_and_zero_weights():
    # Nota: el esquema compartido EdgeSchema todavía rechaza un peso
    # negativo en una arista NO dirigida (422, validación previa a este
    # servicio y fuera de alcance), así que el caso negativo viaja en
    # una arista dirigida: para Kruskal la dirección se ignora, así que
    # es la forma de alimentarle un peso negativo. El cero va en una no
    # dirigida para cubrir ambos caminos.
    payload = make_graph(
        ["A", "B", "C"],
        [
            ("eAB", "A", "B", -2.0, True),
            ("eBC", "B", "C", 0.0, False),
            ("eAC", "A", "C", 5.0, False),
        ],
    )
    response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert [edge["id"] for edge in body["mst_edges"]] == ["eAB", "eBC"]
    assert body["total_weight"] == -2


def test_kruskal_weight_ties_are_deterministic_by_original_order():
    # Triángulo con las tres aristas de peso 1: el desempate es el orden
    # original en payload.edges => se aceptan eAB y eBC, y eAC se
    # rechaza por ciclo.
    payload = make_graph(
        ["A", "B", "C"],
        [
            ("eAB", "A", "B", 1.0, False),
            ("eBC", "B", "C", 1.0, False),
            ("eAC", "A", "C", 1.0, False),
        ],
    )
    response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["sorted_edges"] == ["eAB", "eBC", "eAC"]
    assert [edge["id"] for edge in body["mst_edges"]] == ["eAB", "eBC"]
    assert body["total_weight"] == 2

    # Reproducible: dos corridas idénticas producen la misma respuesta.
    second = client.post(ENDPOINT, json=payload)
    assert second.json() == body


def test_kruskal_rejects_self_loop_and_parallel_edges():
    # Paralelas A-B (2 y 5): la primera (menor peso) une y la segunda
    # forma ciclo. Bucle A-A: se rechaza con motivo "bucle".
    payload = make_graph(
        ["A", "B"],
        [
            ("e1", "A", "B", 2.0, False),
            ("e2", "A", "B", 5.0, False),
            ("eLoop", "A", "A", 3.0, False),
        ],
    )
    response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 200, response.text
    body = response.json()

    assert [edge["id"] for edge in body["mst_edges"]] == ["e1"]
    assert body["total_weight"] == 2
    assert body["components"] == 1

    decisions = {step["edge"]["id"]: step for step in body["steps"]}
    assert decisions["eLoop"]["decision"] == "rejected"
    assert "bucle" in decisions["eLoop"]["reason"]
    assert decisions["e2"]["decision"] == "rejected"
    assert "ciclo" in decisions["e2"]["reason"]


def test_kruskal_single_node_and_edgeless_graphs():
    only_node = client.post(ENDPOINT, json=make_graph(["A"], []))
    assert only_node.status_code == 200, only_node.text
    body = only_node.json()
    assert body["mst_edges"] == []
    assert body["total_weight"] == 0
    assert body["components"] == 1
    assert body["is_connected"] is True
    assert body["steps"] == []

    two_nodes = client.post(ENDPOINT, json=make_graph(["A", "B"], []))
    assert two_nodes.status_code == 200, two_nodes.text
    body_two = two_nodes.json()
    assert body_two["components"] == 2
    assert body_two["is_connected"] is False
    assert any("bosque" in warning.lower() for warning in body_two["warnings"])


def test_kruskal_rejects_edge_referencing_missing_node():
    payload = {
        "graph": {
            "nodes": [{"id": "A"}],
            "edges": [{"id": "e1", "source": "A", "target": "Z", "weight": 1.0, "is_directed": False}],
        },
        "objective": "min",
    }
    response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 400
    assert "origen inválido" in response.json()["message"].lower() or "destino inválido" in response.json()["message"].lower()


def test_kruskal_total_matches_networkx_on_random_graphs():
    # Solo en el TEST: networkx como referencia externa. El servicio no
    # usa NetworkX. Con pesos aleatorios enteros puede haber empates, y
    # entonces existen varios MST de igual costo: se comparan TOTALES,
    # no arista por arista.
    for seed in range(5):
        reference = nx.gnp_random_graph(8, 0.45, seed=seed)
        reference.add_nodes_from(range(8))
        for u, v in reference.edges():
            reference[u][v]["weight"] = ((u * 7 + v * 13 + seed) % 20) + 1
        expected = nx.minimum_spanning_tree(reference, weight="weight")
        expected_total = expected.size(weight="weight")
        component_count = nx.number_connected_components(reference)

        edges = [
            (f"e{u}-{v}", f"n{u}", f"n{v}", float(reference[u][v]["weight"]), False)
            for u, v in reference.edges()
        ]
        payload = make_graph([f"n{index}" for index in range(8)], edges)
        response = client.post(ENDPOINT, json=payload)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total_weight"] == expected_total, f"seed={seed}"
        # Un bosque de expansión tiene n - c aristas.
        assert len(body["mst_edges"]) == 8 - component_count, f"seed={seed}"
        assert body["components"] == component_count, f"seed={seed}"
        assert body["is_connected"] is (component_count == 1), f"seed={seed}"


def test_kruskal_rejects_graphs_over_the_limits():
    many_nodes = client.post(
        ENDPOINT, json=make_graph([f"n{index}" for index in range(101)], [])
    )
    assert many_nodes.status_code == 400
    assert "100" in many_nodes.json()["message"]

    many_edges = client.post(
        ENDPOINT,
        json=make_graph(
            ["A", "B"],
            [(f"e{index}", "A", "B", 1.0, False) for index in range(501)],
        ),
    )
    assert many_edges.status_code == 400
    assert "500" in many_edges.json()["message"]


def _load_real_constellation() -> GraphPayloadSchema:
    path = (
        Path(__file__).resolve().parents[2]
        / "figuelovers-frontend"
        / "public"
        / "constellations"
        / "osa-mayor.json"
    )
    if not path.exists():
        pytest.skip("No se encontró la plantilla real de Osa Mayor")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return GraphPayloadSchema.model_validate(raw["graph"])


def test_kruskal_runs_on_real_constellation_without_mutating_the_payload():
    payload = _load_real_constellation()
    snapshot = copy.deepcopy(payload.model_dump())

    result = KruskalService.calculate_spanning_tree(KruskalRequestSchema(graph=payload))

    # Osa Mayor: 7 estrellas, 7 aristas no dirigidas de peso 1, con un
    # ciclo (el cuadrilátero dubhe-merak-phecda-megrez): el MST tiene
    # 6 aristas (n-1) de peso total 6, conexo.
    assert result.is_connected is True
    assert result.components == 1
    assert len(result.mst_edges) == 6
    assert result.total_weight == 6
    assert result.ignored_directions is False

    # La arista del ciclo se rechaza por "formaría un ciclo".
    rejected = [step for step in result.steps if step.decision == "rejected"]
    assert len(rejected) == 1
    assert "ciclo" in rejected[0].reason

    # El servicio solo LEE el payload: la constelación no se modifica.
    assert payload.model_dump() == snapshot
