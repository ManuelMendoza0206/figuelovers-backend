import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.graph import GraphPayloadSchema, NodeSchema, EdgeSchema


client = TestClient(app)


def test_johnson_all_pairs_shortest_paths_without_negative_cycle():
    payload = GraphPayloadSchema(
        nodes=[
            NodeSchema(id="A"),
            NodeSchema(id="B"),
            NodeSchema(id="C"),
            NodeSchema(id="D"),
        ],
        edges=[
            EdgeSchema(id="e1", source="A", target="B", weight=1.0, is_directed=True),
            EdgeSchema(id="e2", source="A", target="C", weight=4.0, is_directed=True),
            EdgeSchema(id="e3", source="B", target="C", weight=2.0, is_directed=True),
            EdgeSchema(id="e4", source="B", target="D", weight=5.0, is_directed=True),
            EdgeSchema(id="e5", source="C", target="D", weight=1.0, is_directed=True),
            EdgeSchema(id="e6", source="D", target="A", weight=2.0, is_directed=True),
        ],
    )

    response = client.post("/api/v1/graph/algorithms/johnson", json=payload.model_dump())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["has_negative_cycle"] is False
    assert body["distances"]["A"]["B"] == 1
    assert body["distances"]["A"]["C"] == 3
    assert body["distances"]["A"]["D"] == 4
    assert body["paths"]["A"]["D"] in (["A", "C", "D"], ["A", "B", "C", "D"])


def test_johnson_detects_negative_cycle():
    payload = GraphPayloadSchema(
        nodes=[NodeSchema(id="A"), NodeSchema(id="B"), NodeSchema(id="C")],
        edges=[
            EdgeSchema(id="e1", source="A", target="B", weight=1.0, is_directed=True),
            EdgeSchema(id="e2", source="B", target="C", weight=-3.0, is_directed=True),
            EdgeSchema(id="e3", source="C", target="A", weight=1.0, is_directed=True),
        ],
    )

    response = client.post("/api/v1/graph/algorithms/johnson", json=payload.model_dump())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["has_negative_cycle"] is True
    assert "ciclo" in body["message"].lower()


def test_assignment_minimizes_costs_classic_case():
    payload = {
        "cost_matrix": [[4, 2, 8], [4, 3, 7], [3, 1, 6]],
        "row_labels": ["Trabajador 1", "Trabajador 2", "Trabajador 3"],
        "col_labels": ["Tarea A", "Tarea B", "Tarea C"],
        "maximize": False,
    }

    response = client.post("/api/v1/graph/algorithms/assignment", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_cost"] == 12
    assert len(body["assignments"]) == 3
    assert {item["row"] for item in body["assignments"]} == set(payload["row_labels"])
    assert {item["col"] for item in body["assignments"]} == set(payload["col_labels"])


def test_assignment_supports_maximize_and_rectangular_matrix():
    payload = {
        "cost_matrix": [[10, 1, 8], [3, 9, 2], [7, 4, 6]],
        "row_labels": ["R1", "R2", "R3"],
        "col_labels": ["C1", "C2", "C3"],
        "maximize": True,
    }

    response = client.post("/api/v1/graph/algorithms/assignment", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_cost"] == 25
    assert len(body["assignments"]) == 3

    rect_payload = {
        "cost_matrix": [[5, 9], [3, 7], [8, 2]],
        "row_labels": ["W1", "W2", "W3"],
        "col_labels": ["T1", "T2"],
        "maximize": False,
    }

    rect_response = client.post("/api/v1/graph/algorithms/assignment", json=rect_payload)
    assert rect_response.status_code == 200, rect_response.text
    rect_body = rect_response.json()
    assert len(rect_body["assignments"]) == 2
    assert {item["row"] for item in rect_body["assignments"]} <= set(rect_payload["row_labels"])
    assert {item["col"] for item in rect_body["assignments"]} <= set(rect_payload["col_labels"])


def test_johnson_rejects_undirected_graph():
    payload = GraphPayloadSchema(
        nodes=[NodeSchema(id="A"), NodeSchema(id="B")],
        edges=[EdgeSchema(id="e1", source="A", target="B", weight=5.0, is_directed=False)],
    )

    response = client.post("/api/v1/graph/algorithms/johnson", json=payload.model_dump())
    assert response.status_code == 400
    assert "dirigido" in response.json()["message"].lower()
