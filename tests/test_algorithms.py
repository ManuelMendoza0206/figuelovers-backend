import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.graph import GraphPayloadSchema, NodeSchema, EdgeSchema
from app.services.assignment_service import AssignmentService
from app.services.math_service import MathService


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


def test_assignment_accepts_a_perfect_graph_assignment():
    graph = {
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [
            {"id": "e1", "source": "a", "target": "b", "weight": 4, "is_directed": True},
            {"id": "e2", "source": "b", "target": "a", "weight": 2, "is_directed": True},
        ],
    }

    response = client.post(
        "/api/v1/graph/algorithms/assignment",
        json={"graph": graph},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "optimal"
    assert {(item["row"], item["col"]) for item in body["assignments"]} == {
        ("a", "b"),
        ("b", "a"),
    }
    assert body["total_cost"] == 6


def test_assignment_reports_infeasible_graph_without_perfect_matching():
    graph = {
        "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        "edges": [
            {"id": "e1", "source": "a", "target": "b", "weight": 1, "is_directed": True},
            {"id": "e2", "source": "b", "target": "c", "weight": 1, "is_directed": True},
        ],
    }

    response = client.post(
        "/api/v1/graph/algorithms/assignment",
        json={"graph": graph},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "infeasible"
    assert body["assignments"] == []
    assert "perfecta" in body["message"].lower()


def test_assignment_preserves_a_legitimate_zero_cost_edge():
    graph = {
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [
            {"id": "e1", "source": "a", "target": "b", "weight": 0, "is_directed": True},
            {"id": "e2", "source": "b", "target": "a", "weight": 3, "is_directed": True},
        ],
    }

    matrix, forbidden, labels = MathService.generate_assignment_matrix(
        GraphPayloadSchema.model_validate(graph)
    )

    assert labels == ["a", "b"]
    assert matrix == [[0, 0], [3, 0]]
    assert forbidden == [[True, False], [False, True]]
    result = AssignmentService.solve_assignment(
        matrix,
        forbidden_cells=forbidden,
        respect_forbidden_cells=True,
    )
    assert result["status"] == "optimal"
    assert result["total_cost"] == 3
    assert {item["cost"] for item in result["assignments"]} == {0, 3}


def test_directed_edge_is_not_treated_as_bidirectional():
    graph = GraphPayloadSchema(
        nodes=[NodeSchema(id="a"), NodeSchema(id="b")],
        edges=[
            EdgeSchema(
                id="e1",
                source="a",
                target="b",
                weight=7,
                is_directed=True,
            )
        ],
    )

    matrix, forbidden, _ = MathService.generate_assignment_matrix(graph)

    assert matrix[0][1] == 7
    assert forbidden[0][1] is False
    assert forbidden[1][0] is True


def test_forbidden_cells_are_never_selected_even_when_their_cost_is_zero():
    result = AssignmentService.solve_assignment(
        [[None, 5], [2, None]],
    )

    assert result["status"] == "optimal"
    assert {(item["row"], item["col"]) for item in result["assignments"]} == {
        ("0", "1"),
        ("1", "0"),
    }
    assert result["total_cost"] == 7


def test_editing_a_prohibited_cell_with_numeric_cost_enables_it():
    response = client.post(
        "/api/v1/graph/algorithms/assignment",
        json={
            "cost_matrix": [["03", None], [2, 4]],
            "forbidden_cells": [[True, True], [False, False]],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "optimal"
    assert body["initial_cost_matrix"] == [[3.0, None], [2.0, 4.0]]
    assert body["total_cost"] == 7
    assert {(item["row"], item["col"]) for item in body["assignments"]} == {
        ("0", "0"),
        ("1", "1"),
    }


def test_empty_and_special_values_remain_prohibited():
    response = client.post(
        "/api/v1/graph/algorithms/assignment",
        json={
            "cost_matrix": [["", "prohibited"], [None, "  "]],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "infeasible"
    assert body["assignments"] == []


def test_invalid_numeric_cost_returns_validation_error():
    response = client.post(
        "/api/v1/graph/algorithms/assignment",
        json={"cost_matrix": [["not-a-number"]]},
    )

    assert response.status_code == 422
    assert "número válido" in response.json()["message"]


def test_assignment_recalculates_steps_and_result_from_each_received_matrix():
    first = client.post(
        "/api/v1/graph/algorithms/assignment",
        json={
            "cost_matrix": [[None, "03"], [2, 4]],
            "row_labels": ["R1", "R2"],
            "col_labels": ["C1", "C2"],
        },
    )
    second = client.post(
        "/api/v1/graph/algorithms/assignment",
        json={
            "cost_matrix": [[1, None], [None, 1]],
            "row_labels": ["R1", "R2"],
            "col_labels": ["C1", "C2"],
        },
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    first_body = first.json()
    second_body = second.json()
    assert first_body["status"] == "optimal"
    assert second_body["status"] == "optimal"
    assert first_body["total_cost"] == 5
    assert second_body["total_cost"] == 2
    assert first_body["initial_cost_matrix"] != second_body["initial_cost_matrix"]
    assert first_body["steps"] != second_body["steps"]
    assert first_body["steps"][0]["matrix"] == [[None, 0.0], [0.0, 2.0]]
    assert second_body["steps"][0]["matrix"] == [[0.0, None], [None, 0.0]]


def test_assignment_example_with_four_directed_nodes_is_infeasible():
    graph = {
        "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}],
        "edges": [
            {"id": "e1", "source": "b", "target": "a", "weight": 1, "is_directed": True},
            {"id": "e2", "source": "b", "target": "d", "weight": 1, "is_directed": True},
            {"id": "e3", "source": "c", "target": "a", "weight": 1, "is_directed": True},
            {"id": "e4", "source": "d", "target": "c", "weight": 1, "is_directed": True},
        ],
    }

    response = client.post(
        "/api/v1/graph/algorithms/assignment",
        json={"graph": graph},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "infeasible"
    assert body["total_cost"] == 0
    assert body["assignments"] == []


def test_assignment_uses_the_updated_graph_instead_of_stale_matrix_data():
    graph = {
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [
            {"id": "e1", "source": "a", "target": "b", "weight": 2, "is_directed": True},
            {"id": "e2", "source": "b", "target": "a", "weight": 3, "is_directed": True},
        ],
    }

    first = client.post(
        "/api/v1/graph/algorithms/assignment",
        json={"graph": graph},
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "optimal"
    assert first.json()["total_cost"] == 5

    graph["edges"][1]["weight"] = 9
    second = client.post(
        "/api/v1/graph/algorithms/assignment",
        json={"graph": graph},
    )
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "optimal"
    assert second.json()["total_cost"] == 11


@pytest.mark.parametrize("maximize", [False, True])
def test_assignment_steps_preserve_forbidden_cells_as_null(maximize):
    payload = {
        "cost_matrix": [[None, 9], [2, None]],
        "maximize": maximize,
    }

    response = client.post("/api/v1/graph/algorithms/assignment", json=payload)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "optimal"
    assert body["initial_cost_matrix"] == [[None, 9], [2, None]]
    assert body["steps"]
    for step in body["steps"]:
        assert step["matrix"][0][0] is None
        assert step["matrix"][1][1] is None
        assert step["matrix"][0][1] is not None
        assert step["matrix"][1][0] is not None
