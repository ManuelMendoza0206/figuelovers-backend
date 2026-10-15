from decimal import Decimal, InvalidOperation
from math import isfinite

from fastapi import HTTPException

from app.schemas.northwest import NorthwestRequestSchema


MAX_NORTHWEST_DIMENSION = 20


def _decimal(value: float, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=400, detail=f"{field} debe ser un número finito.")
    if not result.is_finite():
        raise HTTPException(status_code=400, detail=f"{field} debe ser un número finito.")
    if result < 0:
        raise HTTPException(status_code=400, detail=f"{field} no puede ser negativo.")
    return result


def _to_float(value: Decimal) -> float:
    return float(value)


class NorthwestService:
    @staticmethod
    def solve(payload: NorthwestRequestSchema) -> dict:
        costs = payload.costs
        supply_values = payload.supply
        demand_values = payload.demand

        if not costs or not costs[0]:
            raise HTTPException(status_code=400, detail="La matriz de costos no puede estar vacía.")

        row_count = len(costs)
        col_count = len(costs[0])
        if row_count > MAX_NORTHWEST_DIMENSION or col_count > MAX_NORTHWEST_DIMENSION:
            raise HTTPException(
                status_code=400,
                detail=f"La matriz no puede superar {MAX_NORTHWEST_DIMENSION}x{MAX_NORTHWEST_DIMENSION}.",
            )

        if any(len(row) != col_count for row in costs):
            raise HTTPException(status_code=400, detail="La matriz de costos debe ser rectangular.")
        if len(supply_values) != row_count or len(demand_values) != col_count:
            raise HTTPException(
                status_code=400,
                detail="Las dimensiones de oferta y demanda deben coincidir con la matriz.",
            )
        if payload.row_labels and len(payload.row_labels) != row_count:
            raise HTTPException(status_code=400, detail="La cantidad de etiquetas de origen no coincide con la matriz.")
        if payload.col_labels and len(payload.col_labels) != col_count:
            raise HTTPException(status_code=400, detail="La cantidad de etiquetas de destino no coincide con la matriz.")

        supply = [_decimal(value, f"Oferta {index + 1}") for index, value in enumerate(supply_values)]
        demand = [_decimal(value, f"Demanda {index + 1}") for index, value in enumerate(demand_values)]
        normalized_costs: list[list[Decimal | None]] = []
        for row_index, row in enumerate(costs):
            normalized_row: list[Decimal | None] = []
            for col_index, value in enumerate(row):
                if value is not None:
                    if not isfinite(value):
                        raise HTTPException(
                            status_code=400,
                            detail=f"El costo [{row_index}, {col_index}] debe ser finito.",
                        )
                    normalized_row.append(_decimal(value, f"El costo [{row_index}, {col_index}]"))
                else:
                    normalized_row.append(None)
            normalized_costs.append(normalized_row)

        if not any(value > 0 for value in supply):
            raise HTTPException(status_code=400, detail="La oferta total debe ser mayor que cero.")
        if not any(value > 0 for value in demand):
            raise HTTPException(status_code=400, detail="La demanda total debe ser mayor que cero.")

        total_supply = sum(supply, Decimal(0))
        total_demand = sum(demand, Decimal(0))
        was_balanced = total_supply == total_demand
        row_labels = payload.row_labels or [f"Origen {index + 1}" for index in range(row_count)]
        col_labels = payload.col_labels or [f"Destino {index + 1}" for index in range(col_count)]
        dummy = None
        warnings: list[str] = []

        if total_supply > total_demand:
            quantity = total_supply - total_demand
            normalized_costs = [row + [Decimal(0)] for row in normalized_costs]
            demand.append(quantity)
            col_labels.append("Destino ficticio")
            dummy = {"type": "destination", "index": len(demand) - 1, "quantity": _to_float(quantity)}
            warnings.append("Se agregó un destino ficticio para balancear la oferta excedente.")
        elif total_demand > total_supply:
            quantity = total_demand - total_supply
            normalized_costs.append([Decimal(0)] * col_count)
            supply.append(quantity)
            row_labels.append("Origen ficticio")
            dummy = {"type": "origin", "index": len(supply) - 1, "quantity": _to_float(quantity)}
            warnings.append("Se agregó un origen ficticio para cubrir la demanda excedente.")

        row_count = len(supply)
        col_count = len(demand)
        remaining_supply = supply[:]
        remaining_demand = demand[:]
        allocation = [[Decimal(0) for _ in range(col_count)] for _ in range(row_count)]
        steps: list[dict] = []
        basic_quantities: dict[tuple[int, int], Decimal] = {}
        row = 0
        col = 0

        while row < row_count and col < col_count:
            quantity = min(remaining_supply[row], remaining_demand[col])
            allocation[row][col] += quantity
            basic_quantities[(row, col)] = allocation[row][col]
            remaining_supply[row] -= quantity
            remaining_demand[col] -= quantity

            row_closed = remaining_supply[row] == 0
            col_closed = remaining_demand[col] == 0
            closed = "both" if row_closed and col_closed else "row" if row_closed else "column"
            note = "Se asigna el mínimo entre la oferta y la demanda restantes."
            steps.append({
                "step": len(steps) + 1,
                "cell": (row, col),
                "quantity": _to_float(quantity),
                "supply_remaining": [_to_float(value) for value in remaining_supply],
                "demand_remaining": [_to_float(value) for value in remaining_demand],
                "closed": closed,
                "degenerate": False,
                "note": note,
                "allocation": [[_to_float(value) for value in values] for values in allocation],
            })

            if row_closed and col_closed:
                if row < row_count - 1:
                    row += 1
                    degenerate_cell = (row, col)
                    degenerate_closed = "column"
                elif col < col_count - 1:
                    col += 1
                    degenerate_cell = (row, col)
                    degenerate_closed = "row"
                else:
                    break

                if degenerate_cell not in basic_quantities:
                    basic_quantities[degenerate_cell] = Decimal(0)
                    steps.append({
                        "step": len(steps) + 1,
                        "cell": degenerate_cell,
                        "quantity": 0.0,
                        "supply_remaining": [_to_float(value) for value in remaining_supply],
                        "demand_remaining": [_to_float(value) for value in remaining_demand],
                        "closed": degenerate_closed,
                        "degenerate": True,
                        "note": "Celda básica degenerada con asignación cero para mantener la base.",
                        "allocation": [[_to_float(value) for value in values] for values in allocation],
                    })
                if degenerate_closed == "column":
                    col += 1
                    row = degenerate_cell[0]
                else:
                    row += 1
                    col = degenerate_cell[1]
            elif row_closed:
                row += 1
            else:
                col += 1

        # Completa una base de m+n-1 celdas sin introducir ciclos cuando
        # hay ofertas o demandas cero, o más de una degeneración simultánea.
        parent = list(range(row_count + col_count))

        def find(item: int) -> int:
            while parent[item] != item:
                parent[item] = parent[parent[item]]
                item = parent[item]
            return item

        def union(first: int, second: int) -> bool:
            first_root = find(first)
            second_root = find(second)
            if first_root == second_root:
                return False
            parent[first_root] = second_root
            return True

        for basic_row, basic_col in basic_quantities:
            union(basic_row, row_count + basic_col)

        candidates = sorted(
            ((r, c) for r in range(row_count) for c in range(col_count) if (r, c) not in basic_quantities),
            key=lambda cell: (cell[0] + cell[1], cell[0], cell[1]),
        )
        for basic_row, basic_col in candidates:
            if len(basic_quantities) >= row_count + col_count - 1:
                break
            if union(basic_row, row_count + basic_col):
                basic_quantities[(basic_row, basic_col)] = Decimal(0)
                steps.append({
                    "step": len(steps) + 1,
                    "cell": (basic_row, basic_col),
                    "quantity": 0.0,
                    "supply_remaining": [_to_float(value) for value in remaining_supply],
                    "demand_remaining": [_to_float(value) for value in remaining_demand],
                    "closed": "both",
                    "degenerate": True,
                    "note": "Celda básica degenerada con asignación cero para completar la base.",
                    "allocation": [[_to_float(value) for value in values] for values in allocation],
                })

        blocked_used = []
        total_cost = Decimal(0)
        for (basic_row, basic_col), quantity in basic_quantities.items():
            cell_cost = normalized_costs[basic_row][basic_col]
            if quantity > 0 and cell_cost is None:
                blocked_used.append({
                    "cell": (basic_row, basic_col),
                    "origin": row_labels[basic_row],
                    "destination": col_labels[basic_col],
                    "quantity": _to_float(quantity),
                })
            elif cell_cost is not None:
                total_cost += quantity * cell_cost

        uses_blocked_routes = bool(blocked_used)
        if uses_blocked_routes:
            warnings.append(
                "La solución usa una o más rutas bloqueadas; no es factible. Reordena los orígenes o destinos, o ajusta el grafo."
            )

        return {
            "allocation": [[_to_float(value) for value in values] for values in allocation],
            "basic_cells": [
                {"cell": cell, "quantity": _to_float(quantity)}
                for cell, quantity in sorted(basic_quantities.items())
            ],
            "total_cost": None if uses_blocked_routes else _to_float(total_cost),
            "steps": steps,
            "was_balanced": was_balanced,
            "dummy": dummy,
            "uses_blocked_routes": uses_blocked_routes,
            "blocked_used": blocked_used,
            "warnings": warnings,
        }
