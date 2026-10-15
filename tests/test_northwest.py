import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
URL = "/api/v1/graph/algorithms/northwest"


def solve(costs, supply, demand, **extra):
    return client.post(
        URL,
        json={
            "costs": costs,
            "supply": supply,
            "demand": demand,
            **extra,
        },
    )


def test_northwest_classic_balanced_problem_total_cost():
    response = solve(
        [[2, 3, 1, 4], [3, 2, 5, 1], [4, 3, 2, 6]],
        [20, 30, 25],
        [10, 25, 20, 20],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["was_balanced"] is True
    assert body["allocation"] == [[10, 10, 0, 0], [0, 15, 15, 0], [0, 0, 5, 20]]
    assert sum(
        body["allocation"][row][col] * [[2, 3, 1, 4], [3, 2, 5, 1], [4, 3, 2, 6]][row][col]
        for row in range(3)
        for col in range(4)
    ) == 285


@pytest.mark.parametrize(
    ("supply", "demand", "dummy_type", "quantity"),
    [
        ([8, 2], [4, 3], "destination", 3),
        ([2, 3], [4, 5], "origin", 4),
    ],
)
def test_northwest_balances_both_directions(supply, demand, dummy_type, quantity):
    response = solve([[1, 2], [3, 4]], supply, demand)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["was_balanced"] is False
    assert body["dummy"]["type"] == dummy_type
    assert body["dummy"]["quantity"] == quantity


def test_northwest_records_degenerate_basic_cells_to_m_plus_n_minus_one():
    response = solve([[1, 2], [3, 4]], [5, 5], [5, 5])

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["basic_cells"]) == 3
    assert any(cell["quantity"] == 0 for cell in body["basic_cells"])
    assert any(step["degenerate"] for step in body["steps"])


def test_northwest_marks_blocked_route_as_infeasible_not_zero_cost():
    response = solve([[None]], [5], [5], row_labels=["A"], col_labels=["B"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["uses_blocked_routes"] is True
    assert body["blocked_used"][0]["cell"] == [0, 0]
    assert body["total_cost"] is None
    assert body["allocation"] == [[5]]


@pytest.mark.parametrize(
    ("costs", "supply", "demand"),
    [
        ([], [], []),
        ([[1], [1, 2]], [1, 1], [1]),
        ([[1, 2]], [1], [1]),
        ([[-1]], [1], [1]),
        ([[1]], [-1], [1]),
        ([[1]], [1], [-1]),
        ([[1]], [0], [1]),
        ([[1]], [1], [0]),
    ],
)
def test_northwest_rejects_invalid_inputs(costs, supply, demand):
    response = solve(costs, supply, demand)
    assert response.status_code == 400
    assert response.json()["message"]


def test_northwest_rejects_dimensions_over_twenty():
    response = solve([[1] for _ in range(21)], [1] * 21, [21])
    assert response.status_code == 400
    assert "20x20" in response.json()["message"]


def test_northwest_accepts_twenty_by_twenty():
    response = solve(
        [[0] * 20 for _ in range(20)],
        [1] * 20,
        [1] * 20,
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["allocation"]) == 20
    assert len(response.json()["allocation"][0]) == 20
