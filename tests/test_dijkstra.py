import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.dijkstra import DijkstraRequestSchema
from app.schemas.graph import GraphPayloadSchema, NodeSchema, EdgeSchema
from app.services.dijkstra_service import DijkstraService


client = TestClient(app)

ENDPOINT = "/api/v1/graph/algorithms/dijkstra"


def make_graph(nodes, edges, source="A", target=None):
    return {
        "graph": {
            "nodes": [{"id": node} for node in nodes],
            "edges": [
                {
                    "id": edge_id,
                    "source": source_node,
                    "target": target_node,
                    "weight": weight,
                    "is_directed": is_directed,
                }
                for edge_id, source_node, target_node, weight, is_directed in edges
            ],
        },
        "source": source,
        "target": target,
    }


# Grafo dirigido del enunciado, valores calculados a mano:
#   A→B 4, A→C 1, C→B 2, B→D 1, C→D 5, D→E 3, origen A
# Distancias: A=0, C=1, B=3, D=4, E=7 (vía A,C,B,D,E)
DIRECTED_EXAMPLE = [
    ("eAB", "A", "B", 4.0, True),
    ("eAC", "A", "C", 1.0, True),
    ("eCB", "C", "B", 2.0, True),
    ("eBD", "B", "D", 1.0, True),
    ("eCD", "C", "D", 5.0, True),
    ("eDE", "D", "E", 3.0, True),
]


def test_dijkstra_directed_example_distances_path_and_visit_order():
    payload = make_graph(["A", "B", "C", "D", "E"], DIRECTED_EXAMPLE, source="A", target="E")

    response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 200, response.text
    body = response.json()

    # Distancias calculadas a mano.
    assert body["distances"] == {"A": 0, "B": 3, "C": 1, "D": 4, "E": 7}
    # Camino a E: A,C,B,D,E con aristas eAC,eCB,eBD,eDE.
    assert body["paths"]["E"] == ["A", "C", "B", "D", "E"]
    assert body["target_path"]["nodes"] == ["A", "C", "B", "D", "E"]
    assert body["target_path"]["edges"] == ["eAC", "eCB", "eBD", "eDE"]
    assert body["target_path"]["total_distance"] == 7
    # Orden de fijado definitivo.
    assert body["order_visited"] == ["A", "C", "B", "D", "E"]
    # Predecesores coherentes con el camino.
    assert body["predecessors"]["E"] == "D"
    assert body["predecessors"]["A"] is None

    # Un paso por nodo fijado, con la distancia correcta.
    assert [step["node"] for step in body["steps"]] == ["A", "C", "B", "D", "E"]
    assert [step["distance"] for step in body["steps"]] == [0, 1, 3, 4, 7]
    assert [step["step"] for step in body["steps"]] == [1, 2, 3, 4, 5]

    # Relajaciones del primer paso (desde A): B y C mejoran desde infinito.
    first_relaxations = body["steps"][0]["relaxations"]
    assert first_relaxations == [
        {"from": "A", "to": "B", "edge_id": "eAB", "old_distance": None, "new_distance": 4, "improved": True},
        {"from": "A", "to": "C", "edge_id": "eAC", "old_distance": None, "new_distance": 1, "improved": True},
    ]

    # El snapshot del último paso es el resultado final.
    assert body["steps"][-1]["distances_snapshot"] == body["distances"]
    assert body["steps"][-1]["visited_snapshot"] == ["A", "C", "B", "D", "E"]


def test_dijkstra_mixed_graph_undirected_traverse_both_ways():
    # A-B no dirigida (2), B→C dirigida (3). La dirigida no se puede
    # recorrer de C a B; la no dirigida sí de B a A.
    payload = make_graph(
        ["A", "B", "C"],
        [
            ("eAB", "A", "B", 2.0, False),
            ("eBC", "B", "C", 3.0, True),
        ],
        source="A",
    )
    response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["distances"] == {"A": 0, "B": 2, "C": 5}
    assert body["paths"]["C"] == ["A", "B", "C"]

    # Desde C no se puede retroceder por la arista dirigida B→C ni
    # cruzar A-B al revés (B es inalcanzable desde C).
    payload_back = make_graph(
        ["A", "B", "C"],
        [
            ("eAB", "A", "B", 2.0, False),
            ("eBC", "B", "C", 3.0, True),
        ],
        source="C",
    )
    response_back = client.post(ENDPOINT, json=payload_back)
    assert response_back.status_code == 200, response_back.text
    body_back = response_back.json()
    assert body_back["distances"] == {"A": None, "B": None, "C": 0}
    assert body_back["paths"]["A"] == []


def test_dijkstra_unreachable_node_is_null_with_empty_path():
    payload = make_graph(
        ["A", "B", "C"],
        [("eAB", "A", "B", 1.0, True)],
        source="A",
    )
    response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["distances"]["C"] is None
    assert body["paths"]["C"] == []
    assert body["predecessors"]["C"] is None


def test_dijkstra_negative_weight_returns_400_mentioning_johnson():
    # Nota: una arista NO dirigida con peso negativo la rechaza antes el
    # esquema (422); el rechazo de Dijkstra aplica a las dirigidas.
    payload = make_graph(
        ["A", "B", "C"],
        [
            ("eAB", "A", "B", 4.0, True),
            ("eBC", "B", "C", -2.0, True),
        ],
        source="A",
    )
    response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 400, response.text
    message = response.json()["message"]
    assert "negativos" in message.lower()
    assert "johnson" in message.lower()
    assert "eBC" in message


def test_dijkstra_unknown_source_or_target_returns_400():
    base = make_graph(["A", "B"], [("eAB", "A", "B", 1.0, True)], source="A")

    response = client.post(ENDPOINT, json={**base, "source": "Z"})
    assert response.status_code == 400
    assert "origen" in response.json()["message"].lower()

    response_target = client.post(ENDPOINT, json={**base, "target": "Z"})
    assert response_target.status_code == 400
    assert "destino" in response_target.json()["message"].lower()


def test_dijkstra_equal_distances_are_deterministic():
    # A→B 1, A→C 1, B→D 1, C→D 1: D queda a distancia 2 por dos rutas.
    # Criterio documentado: a igual distancia gana el nodo de menor índice
    # en payload.nodes y la relajación solo cambia el predecesor si la
    # mejora es estricta => el predecesor de D es B.
    payload = make_graph(
        ["A", "B", "C", "D"],
        [
            ("eAB", "A", "B", 1.0, True),
            ("eAC", "A", "C", 1.0, True),
            ("eBD", "B", "D", 1.0, True),
            ("eCD", "C", "D", 1.0, True),
        ],
        source="A",
    )
    response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["distances"]["D"] == 2
    assert body["predecessors"]["D"] == "B"
    assert body["paths"]["D"] == ["A", "B", "D"]

    # Al fijar C, la arista C→D propone 2 pero no mejora (no estricto).
    step_c = next(step for step in body["steps"] if step["node"] == "C")
    relaxation_to_d = next(r for r in step_c["relaxations"] if r["to"] == "D")
    assert relaxation_to_d["improved"] is False
    assert relaxation_to_d["new_distance"] == 2

    # Reproducible: dos corridas idénticas producen la misma respuesta.
    second = client.post(ENDPOINT, json=payload)
    assert second.json() == body


def test_dijkstra_source_equals_target():
    payload = make_graph(["A", "B"], [("eAB", "A", "B", 1.0, True)], source="A", target="A")
    response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["distances"]["A"] == 0
    assert body["paths"]["A"] == ["A"]
    assert body["target_path"] == {"nodes": ["A"], "edges": [], "total_distance": 0}


def test_dijkstra_parallel_edges_and_self_loop():
    # Aristas paralelas A→B (5 y 2): gana la menor de forma natural.
    # Self-loop A→A: se ignora y se avisa.
    payload = make_graph(
        ["A", "B"],
        [
            ("e1", "A", "B", 5.0, True),
            ("e2", "A", "B", 2.0, True),
            ("eLoop", "A", "A", 1.0, True),
        ],
        source="A",
        target="B",
    )
    response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["distances"]["B"] == 2
    assert body["target_path"]["edges"] == ["e2"]
    assert body["target_path"]["total_distance"] == 2
    assert any("bucle" in warning.lower() for warning in body["warnings"])

    # En el paso de A, ambas paralelas se intentan y ambas mejoran.
    step_a = body["steps"][0]
    to_b = [r for r in step_a["relaxations"] if r["to"] == "B"]
    assert [r["new_distance"] for r in to_b] == [5, 2]
    assert all(r["improved"] for r in to_b)


def test_dijkstra_treats_explicit_null_weight_as_one():
    payload = make_graph(["A", "B"], [("eAB", "A", "B", None, True)], source="A")
    response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["distances"]["B"] == 1
    assert any("peso 1" in warning for warning in body["warnings"])


def test_dijkstra_distances_match_johnson_on_directed_non_negative_graph():
    # Prueba cruzada: en un grafo dirigido con pesos >= 0, las
    # distancias de Dijkstra desde cada origen deben coincidir con la
    # fila de ese origen en la matriz de Johnson.
    nodes = ["A", "B", "C", "D", "E"]
    edges = DIRECTED_EXAMPLE + [
        ("eEA", "E", "A", 2.0, True),
        ("eDA", "D", "A", 9.0, True),
        ("eBE", "B", "E", 6.0, True),
    ]

    johnson_response = client.post(
        "/api/v1/graph/algorithms/johnson",
        json={"nodes": [{"id": node} for node in nodes], "edges": [
            {"id": edge_id, "source": src, "target": dst, "weight": weight, "is_directed": directed}
            for edge_id, src, dst, weight, directed in edges
        ]},
    )
    assert johnson_response.status_code == 200, johnson_response.text
    johnson = johnson_response.json()
    assert johnson["has_negative_cycle"] is False

    for origin in nodes:
        response = client.post(ENDPOINT, json=make_graph(nodes, edges, source=origin))
        assert response.status_code == 200, response.text
        dijkstra = response.json()
        for node in nodes:
            assert dijkstra["distances"][node] == johnson["distances"][origin][node], (
                f"distancia {origin}->{node}"
            )


def test_dijkstra_rejects_graphs_over_the_node_limit():
    nodes = [f"n{index}" for index in range(101)]
    payload = make_graph(nodes, [], source="n0")
    response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 400
    assert "100" in response.json()["message"]


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


def test_dijkstra_runs_on_real_constellation_without_mutating_the_payload():
    payload = _load_real_constellation()
    snapshot = copy.deepcopy(payload.model_dump())

    request = DijkstraRequestSchema(graph=payload, source="dubhe", target="alkaid")
    result = DijkstraService.calculate_shortest_paths(request)

    # Osa Mayor: 7 estrellas, aristas no dirigidas de peso 1. El
    # cuadrilátero dubhe-merak-phecda-megrez acorta el camino: se llega
    # a megrez en 1 salto y de ahí la cadena megrez-alioth-mizar-alkaid
    # (3 más) => distancia 4.
    assert result.distances["alkaid"] == 4
    assert result.paths["alkaid"] == [
        "dubhe", "megrez", "alioth", "mizar", "alkaid",
    ]

    # El servicio solo LEE el payload: la constelación no se modifica.
    assert payload.model_dump() == snapshot
