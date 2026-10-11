from __future__ import annotations

from collections import deque

import numpy as np
from scipy.optimize import linear_sum_assignment


class AssignmentService:
    @staticmethod
    def _normalize_matrix(cost_matrix):
        if cost_matrix is None:
            return []

        matrix = [[float(value) for value in row] for row in cost_matrix]
        if not matrix:
            return []

        return matrix

    @staticmethod
    def _pad_to_square(matrix):
        rows = len(matrix)
        cols = len(matrix[0]) if rows else 0
        target = max(rows, cols)

        padded = [list(row) + [0.0] * (target - cols) for row in matrix]
        if len(padded) < target:
            padded.extend([[0.0] * target for _ in range(target - len(padded))])
        return padded

    @staticmethod
    def _row_reduction(matrix):
        reduced = []
        for row in matrix:
            if not row:
                reduced.append(row[:])
                continue
            min_val = min(row)
            reduced.append([value - min_val for value in row])
        return reduced

    @staticmethod
    def _column_reduction(matrix):
        if not matrix or not matrix[0]:
            return [row[:] for row in matrix]
        n_cols = len(matrix[0])
        reduced = [row[:] for row in matrix]
        for c in range(n_cols):
            col_min = min(reduced[r][c] for r in range(len(reduced)))
            for r in range(len(reduced)):
                reduced[r][c] -= col_min
        return reduced

    @staticmethod
    def _find_min_uncovered(matrix, covered_rows, covered_cols):
        uncovered = []
        for r in range(len(matrix)):
            for c in range(len(matrix[0])):
                if r not in covered_rows and c not in covered_cols:
                    uncovered.append(matrix[r][c])
        return min(uncovered) if uncovered else None

    @staticmethod
    def _update_matrix(matrix, covered_rows, covered_cols, min_uncovered):
        rows = len(matrix)
        cols = len(matrix[0]) if rows else 0
        new_matrix = []
        for r in range(rows):
            row = []
            for c in range(cols):
                if r in covered_rows and c in covered_cols:
                    row.append(matrix[r][c] + min_uncovered)
                elif r not in covered_rows and c not in covered_cols:
                    row.append(matrix[r][c] - min_uncovered)
                else:
                    row.append(matrix[r][c])
            new_matrix.append(row)
        return new_matrix

    @staticmethod
    def _max_bipartite_matching(zero_matrix):
        """
        Emparejamiento bipartito maximo (algoritmo de Kuhn augmenting path),
        ITERATIVO a proposito: la version recursiva se desborda con
        n cercano a 1000 (limite de recursion de Python) y el size guard
        del endpoint no deberia ser la unica defensa.
        Devuelve (match_col, match_row).
        """
        n = len(zero_matrix)
        match_col = [-1] * n
        match_row = [-1] * n

        for start in range(n):
            # Camino augmenting como pila explicita: (fila, indice de
            # columna a examinar). Reutilizamos `visited` por busqueda.
            visited = [False] * n
            stack = [(start, 0)]
            # father_col[c] = fila desde la que se llego a la columna c.
            # Se usa para reconstruir el camino al hacer backtrack.
            father_col = {}
            free_col = None

            while stack and free_col is None:
                row, col_cursor = stack[-1]

                advanced = False
                while col_cursor < n:
                    col = col_cursor
                    col_cursor += 1
                    stack[-1] = (row, col_cursor)

                    if not zero_matrix[row][col] or visited[col]:
                        continue

                    visited[col] = True
                    father_col[col] = row

                    if match_col[col] == -1:
                        # Columna libre: armamos el camino de vuelta.
                        free_col = col
                        break

                    # Columna ocupada: seguimos por la fila que la toma.
                    stack.append((match_col[col], 0))
                    advanced = True
                    break

                if free_col is not None or advanced:
                    continue

                # La fila se quedo sin camino: backtrack.
                stack.pop()

            if free_col is None:
                continue

            # Invertimos el camino: cada columna queda asignada a la fila
            # desde la que se llego. `match_row` usa -1 como centinela
            # de "sin asignar", no None.
            col = free_col
            while col != -1:
                row = father_col[col]
                previous = match_row[row]
                match_row[row] = col
                match_col[col] = row
                col = previous

        return match_col, match_row

    @staticmethod
    def _min_line_cover(zero_matrix):
        """
        Minimum set of lines (rows/columns) that covers every zero position,
        computed with Konig's theorem over the maximum bipartite matching.
        Returns (covered_rows, covered_cols) as sets.
        """
        n = len(zero_matrix)
        if n == 0:
            return set(), set()

        match_col, match_row = AssignmentService._max_bipartite_matching(zero_matrix)

        row_in_z = [False] * n
        col_in_z = [False] * n
        queue = deque()

        for r in range(n):
            if match_row[r] == -1:
                row_in_z[r] = True
                queue.append((True, r))

        while queue:
            is_row, idx = queue.popleft()
            if is_row:
                r = idx
                for c in range(n):
                    if zero_matrix[r][c] and c != match_row[r] and not col_in_z[c]:
                        col_in_z[c] = True
                        queue.append((False, c))
            else:
                c = idx
                r = match_col[c]
                if r != -1 and not row_in_z[r]:
                    row_in_z[r] = True
                    queue.append((True, r))

        covered_rows = {r for r in range(n) if not row_in_z[r]}
        covered_cols = {c for c in range(n) if col_in_z[c]}
        return covered_rows, covered_cols

    @staticmethod
    def solve_assignment(cost_matrix, row_labels=None, col_labels=None, maximize: bool = False):
        matrix = AssignmentService._normalize_matrix(cost_matrix)
        if not matrix:
            return {
                "assignments": [],
                "total_cost": 0,
                "initial_cost_matrix": [],
                "steps": [],
            }

        original_rows = len(matrix)
        original_cols = len(matrix[0]) if matrix else 0

        if maximize:
            max_value = max(max(row) for row in matrix) if matrix else 0.0
            transformed = [[max_value - value for value in row] for row in matrix]
        else:
            transformed = [list(row) for row in matrix]

        padded = AssignmentService._pad_to_square(transformed)
        initial_matrix = [row[:] for row in matrix]

        steps = []
        step_no = 1

        if maximize:
            steps.append({
                "step": step_no,
                "name": "Maximization Transform",
                "matrix": [row[:] for row in transformed],
                "description": (
                    f"Convert the maximization problem into a minimization one by "
                    f"turning each profit into an opportunity cost: cell = {max_value:g} - value"
                ),
            })
            step_no += 1

        # Step: Row reduction
        reduced_matrix = AssignmentService._row_reduction(padded)
        steps.append({
            "step": step_no,
            "name": "Row Reduction",
            "matrix": [row[:] for row in reduced_matrix],
            "description": "Subtract the minimum of each row from all elements in that row",
        })
        step_no += 1

        # Step: Column reduction
        after_col = AssignmentService._column_reduction(reduced_matrix)
        steps.append({
            "step": step_no,
            "name": "Column Reduction",
            "matrix": [row[:] for row in after_col],
            "description": "Subtract the minimum of each column from all elements in that column",
        })
        step_no += 1

        n_rows = len(after_col)
        n_cols = len(after_col[0]) if n_rows else 0
        size = max(n_rows, n_cols)

        working = [row[:] + [0.0] * (size - len(row)) for row in after_col]
        if len(working) < size:
            working.extend([[0.0] * size for _ in range(size - len(working))])

        iteration = step_no
        max_iterations = size * 20 + 10
        guard = 0
        while guard < max_iterations:
            guard += 1

            zero_matrix = [
                [abs(working[r][c]) < 1e-9 for c in range(size)]
                for r in range(size)
            ]
            covered_rows, covered_cols = AssignmentService._min_line_cover(zero_matrix)

            num_covered = len(covered_rows) + len(covered_cols)
            if num_covered >= size:
                break

            min_uncovered = AssignmentService._find_min_uncovered(working, covered_rows, covered_cols)
            if min_uncovered is None:
                break

            working = AssignmentService._update_matrix(working, covered_rows, covered_cols, min_uncovered)

            steps.append({
                "step": iteration,
                "name": "Matrix Adjustment",
                "matrix": [row[:] for row in working],
                "description": f"Adjust matrix: subtract {min_uncovered} from uncovered cells, add to covered cells",
                "min_uncovered": min_uncovered,
            })
            iteration += 1

        row_idx, col_idx = linear_sum_assignment(np.array(padded, dtype=float), maximize=False)

        assignments = []
        selected_pairs = []
        for r, c in zip(row_idx, col_idx):
            if r < original_rows and c < original_cols:
                selected_pairs.append((r, c))

        for row, col in sorted(selected_pairs):
            row_name = (row_labels[row] if row_labels and row < len(row_labels) else str(row))
            col_name = (col_labels[col] if col_labels and col < len(col_labels) else str(col))
            original_cost = float(matrix[row][col])
            assignments.append({
                "row": row_name,
                "col": col_name,
                "cost": original_cost,
            })

        total_cost = sum(float(item["cost"]) for item in assignments)

        # Step: Select Independent Zeros (paso didáctico final)
        # Los selected_pairs ya fueron filtrados a celdas reales (r < original_rows, c < original_cols)
        selected_zeros = [(r, c) for r, c in selected_pairs]
        steps.append({
            "step": step_no,
            "name": "Select Independent Zeros",
            "matrix": [row[:] for row in working],
            "description": "Se seleccionan ceros no cubiertos, cada uno en una fila y columna distintas. Estos son los emparejamientos óptimos.",
            "selected_zeros": selected_zeros,
        })
        step_no += 1

        # Metadata de padding para matrices rectangulares
        padding_info = None
        if original_rows != original_cols:
            padded_rows = len(padded)
            padded_cols = len(padded[0]) if padded_rows else 0
            dummy_rows = [i for i in range(padded_rows) if i >= original_rows]
            dummy_cols = [i for i in range(padded_cols) if i >= original_cols]
            padding_info = {
                "original_rows": original_rows,
                "original_cols": original_cols,
                "padded_size": {"rows": padded_rows, "cols": padded_cols},
                "dummy_rows": dummy_rows,
                "dummy_cols": dummy_cols,
            }

        return {
            "assignments": assignments,
            "total_cost": total_cost,
            "initial_cost_matrix": initial_matrix,
            "steps": steps,
            "padding_info": padding_info,
        }