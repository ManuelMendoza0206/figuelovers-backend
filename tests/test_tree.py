import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
BASE = "/api/v1/graph/algorithms/tree"


def test_build_bst_has_expected_three_traversals():
    response = client.post(f"{BASE}/build", json={
        "mode": "values",
        "values": [8, 3, 10, 1, 6, 14, 4, 7, 13],
    })

    assert response.status_code == 200, response.text
    assert response.json()["traversals"] == {
        "preorder": [8, 3, 1, 6, 4, 7, 10, 14, 13],
        "inorder": [1, 3, 4, 6, 7, 8, 10, 13, 14],
        "postorder": [1, 4, 7, 6, 3, 13, 14, 10, 8],
    }


def test_random_tree_is_seeded_unique_and_in_range():
    payload = {"mode": "random", "count": 12, "seed": 42}
    first = client.post(f"{BASE}/build", json=payload)
    second = client.post(f"{BASE}/build", json=payload)

    assert first.status_code == 200, first.text
    values = first.json()["traversals"]["preorder"]
    assert values == second.json()["traversals"]["preorder"]
    assert len(values) == len(set(values)) == 12
    assert all(1 <= value <= 99 for value in values)


def test_duplicate_build_value_is_rejected():
    response = client.post(f"{BASE}/build", json={"mode": "values", "values": [4, 2, 4]})
    assert response.status_code == 400
    assert "repetidos" in response.json()["message"].lower()


@pytest.mark.parametrize(
    ("order", "other", "expected"),
    [
        ("preorder", [1, 2, 4, 5, 3, 6, 7], [1, 2, 4, 5, 3, 6, 7]),
        ("postorder", [4, 5, 2, 6, 7, 3, 1], [1, 2, 4, 5, 3, 6, 7]),
    ],
)
def test_reconstructs_inorder_with_preorder_or_postorder(order, other, expected):
    response = client.post(f"{BASE}/reconstruct", json={
        "inorder": [4, 2, 5, 1, 6, 3, 7],
        "other": other,
        "other_order": order,
    })

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["traversals"]["inorder"] == [4, 2, 5, 1, 6, 3, 7]
    assert body["traversals"][order] == other
    assert body["traversals"]["preorder"] == expected
    assert body["is_bst"] is False


def test_reconstruction_lists_each_value_that_does_not_match_exactly():
    response = client.post(f"{BASE}/reconstruct", json={
        "inorder": [4, 2, 5, 1, 3],
        "other": [4, 5, 2, 9, 1],
        "other_order": "postorder",
    })

    assert response.status_code == 400
    assert response.json()["message"] == (
        "Los recorridos contienen valores distintos: solo en in-order: [3]; "
        "solo en postorder: [9]."
    )


@pytest.mark.parametrize(
    ("inorder", "other", "order", "expected_message"),
    [
        ([], [], "preorder", "La cadena in-order no puede estar vacía."),
        ([1, 2], [1], "preorder", "Los recorridos deben tener la misma cantidad de valores."),
        ([1, 1], [1, 1], "preorder", "La cadena in-order contiene valores repetidos: [1]."),
        (["x"], [1], "preorder", "La cadena in-order solo puede contener números enteros."),
        ([1, 2, 3], [2, 3, 1], "preorder", "Los recorridos no son compatibles entre sí."),
    ],
)
def test_reconstruction_rejects_invalid_traversals_with_exact_messages(inorder, other, order, expected_message):
    response = client.post(f"{BASE}/reconstruct", json={
        "inorder": inorder,
        "other": other,
        "other_order": order,
    })
    assert response.status_code == 400
    assert response.json()["message"] == expected_message


def test_editor_tree_rejects_undirected_cycles_multiple_parents_three_children_and_disconnected():
    def post(nodes, edges):
        return client.post(f"{BASE}/traverse", json={
            "graph": {"nodes": nodes, "edges": edges},
            "order": "preorder",
        })

    nodes = [{"id": str(value), "label": str(value), "data": {"treeValue": value}} for value in range(1, 6)]
    assert post(nodes[:2], [{"id": "e", "source": "1", "target": "2", "is_directed": False}]).status_code == 400
    assert post(nodes[:3], [
        {"id": "a", "source": "1", "target": "2", "is_directed": True},
        {"id": "b", "source": "2", "target": "1", "is_directed": True},
        {"id": "c", "source": "1", "target": "3", "is_directed": True},
    ]).status_code == 400
    assert post(nodes[:4], [
        {"id": "a", "source": "1", "target": "3", "is_directed": True},
        {"id": "b", "source": "2", "target": "3", "is_directed": True},
    ]).status_code == 400
    assert post(nodes[:4], [
        {"id": "a", "source": "1", "target": "2", "is_directed": True},
        {"id": "b", "source": "1", "target": "3", "is_directed": True},
        {"id": "c", "source": "1", "target": "4", "is_directed": True},
    ]).status_code == 400
    assert post(nodes, [
        {"id": "a", "source": "1", "target": "2", "is_directed": True},
        {"id": "b", "source": "1", "target": "3", "is_directed": True},
        {"id": "c", "source": "4", "target": "5", "is_directed": True},
    ]).status_code == 400
