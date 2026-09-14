from __future__ import annotations

from math import inf

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
    def solve_assignment(cost_matrix, row_labels=None, col_labels=None, maximize: bool = False):
        matrix = AssignmentService._normalize_matrix(cost_matrix)
        if not matrix:
            return {"assignments": [], "total_cost": 0}

        original_rows = len(matrix)
        original_cols = len(matrix[0]) if matrix else 0

        if maximize:
            max_value = max(max(row) for row in matrix) if matrix else 0.0
            transformed = [[max_value - value for value in row] for row in matrix]
        else:
            transformed = [list(row) for row in matrix]

        padded = AssignmentService._pad_to_square(transformed)
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
        return {
            "assignments": assignments,
            "total_cost": total_cost,
        }
