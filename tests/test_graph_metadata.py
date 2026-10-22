from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
NODE_DATA = {
    "label": "Origen",
    "folio": 1,
    "role": "source",
    "supply": 5,
    "treeValue": 7,
    "treeSide": "left",
    "extra": "x",
}


def test_graph_import_and_validation_preserve_arbitrary_node_data():
    graph = {
        "nodes": [{
            "id": "A",
            "label": "Origen",
            "position": {"x": 10, "y": 20},
            "data": NODE_DATA,
        }],
        "edges": [],
    }
    imported = client.post(
        "/api/v1/graph/import",
        json={"metadata": {"version": "1.0.0"}, "graph": graph},
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["data"]["graph"]["nodes"][0]["data"] == NODE_DATA

    validated = client.post("/api/v1/graph/validate", json=graph)
    assert validated.status_code == 200, validated.text
    assert validated.json()["data"]["nodos"][0]["data"] == NODE_DATA


def test_graph_validation_exposes_assignment_matrix_without_losing_direction():
    graph = {
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [
            {"id": "e1", "source": "a", "target": "b", "weight": 0, "is_directed": True},
        ],
    }

    response = client.post("/api/v1/graph/validate", json=graph)

    assert response.status_code == 200, response.text
    assignment = response.json()["data"]["matriz_costos_asignacion"]
    assert assignment["matrix"] == [[0, 0], [0, 0]]
    assert assignment["forbidden_cells"] == [[True, False], [True, True]]
