"""Tests de `_min_line_cover` y del matching bipartito.

Cubre la reescritura iterativa de Kuhn: el objetivo es que se comporte
exactamente igual que la version recursiva que reemplazo, que era la que
reventaba con RecursionError cerca de n=1000.
"""

import random

import pytest

from app.services.assignment_service import AssignmentService as A


def _matching_recursivo(zero_matrix):
    """La version original, mantenida como oraculo en los tests."""
    n = len(zero_matrix)
    match_col = [-1] * n

    def augment(r, visited):
        for c in range(n):
            if zero_matrix[r][c] and not visited[c]:
                visited[c] = True
                if match_col[c] == -1 or augment(match_col[c], visited):
                    match_col[c] = r
                    return True
        return False

    for r in range(n):
        augment(r, [False] * n)

    match_row = [-1] * n
    for c in range(n):
        if match_col[c] != -1:
            match_row[match_col[c]] = c
    return match_col, match_row


def _es_matching_valido(zero_matrix, match_col):
    n = len(zero_matrix)
    filas_usadas = set()
    for c in range(n):
        r = match_col[c]
        if r == -1:
            continue
        if not zero_matrix[r][c]:
            return False, "empareja una celda que no es cero"
        if r in filas_usadas:
            return False, f"la fila {r} queda asignada a dos columnas"
        filas_usadas.add(r)
    return True, ""


def test_matching_es_valido_en_matriz_dispersa():
    z = [[r == c for c in range(5)] for r in range(5)]
    match_col, _ = A._max_bipartite_matching(z)
    ok, motivo = _es_matching_valido(z, match_col)
    assert ok, motivo
    assert sum(1 for v in match_col if v != -1) == 5


def test_matching_sin_ceros_devuelve_vacio():
    z = [[False] * 4 for _ in range(4)]
    match_col, match_row = A._max_bipartite_matching(z)
    assert all(v == -1 for v in match_col)
    assert all(v == -1 for v in match_row)


def test_matching_ignora_las_diagonales_de_un_sin_cero():
    # Solo se puede usar la anti-diagonal: matching de tamano n.
    n = 6
    z = [[r + c == n - 1 for c in range(n)] for r in range(n)]
    match_col, _ = A._max_bipartite_matching(z)
    ok, motivo = _es_matching_valido(z, match_col)
    assert ok, motivo
    assert sum(1 for v in match_col if v != -1) == n


@pytest.mark.parametrize("n", [1, 2, 3, 7, 11])
@pytest.mark.parametrize("densidad", [0.1, 0.35, 0.6, 0.9, 1.0])
def test_iterativo_coincide_con_el_recursivo(n, densidad):
    """Contrato: mismo TAMAÑO de matching que el algoritmo original.

    No se comparan las asignaciones exactas porque el matching maximo no
    es unico: hay empates legitimos entre distintas soluciones del
    mismo tamano.
    """
    rng = random.Random(n * 1000 + int(densidad * 100))
    z = [[rng.random() < densidad for _ in range(n)] for _ in range(n)]

    esperado, _ = _matching_recursivo(z)
    obtenido, _ = A._max_bipartite_matching(z)

    assert sum(1 for v in obtenido if v != -1) == sum(
        1 for v in esperado if v != -1
    )


def test_no_hay_recursion_error_a_n_1200():
    """El bug que motivations la reescritura.

    Con el limite de recursion por defecto de Python (1000), la version
    recursiva levanta RecursionError con este tamano.
    """
    n = 1200
    z = [[False] * n for _ in range(n)]
    for i in range(n):
        z[i][i] = True
        z[i][(i + 1) % n] = True

    match_col, _ = A._max_bipartite_matching(z)

    assert sum(1 for v in match_col if v != -1) == n


def test_min_line_cover_cubre_todos_los_ceros():
    n = 5
    z = [[r + c == n - 1 for c in range(n)] for r in range(n)]
    filas, columnas = A._min_line_cover(z)

    for r in range(n):
        for c in range(n):
            if z[r][c]:
                assert r in filas or c in columnas, f"celda ({r},{c}) sin cubrir"


def test_min_line_cover_de_matriz_vacia():
    filas, columnas = A._min_line_cover([])
    assert filas == set()
    assert columnas == set()


def test_min_line_cover_de_matriz_sin_ceros():
    filas, columnas = A._min_line_cover([[False] * 3 for _ in range(3)])
    assert filas == set()
    assert columnas == set()


def test_min_line_cover_cubre_todos_los_ceros_en_tablero_grande():
    rng = random.Random(7)
    n = 40
    z = [[rng.random() < 0.3 for _ in range(n)] for _ in range(n)]
    filas, columnas = A._min_line_cover(z)

    for r in range(n):
        for c in range(n):
            if z[r][c]:
                assert r in filas or c in columnas


def test_solve_assignment_no_revienta_en_matriz_grande():
    """El size guard del endpoint lo frena en 20, pero el algoritmo ya
    no tiene una limite de recursion escondido debajo."""
    n = 400
    resultado = A.solve_assignment([[1] * n for _ in range(n)])
    assert len(resultado["assignments"]) == n