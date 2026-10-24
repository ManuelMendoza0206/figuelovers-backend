# AGENTS.md — MAT-361 Graph Editor API

**Purpose**: Compact instruction file for future OpenCode sessions. Covers test commands, project quirks, and conventions inferred from code.

---

## ⚡ Quick commands

| Action | Command |
|--------|---------|
| Run all tests (venv) | `.venv/bin/python -m pytest -q` |
| Run all tests (python -m) | `python -m pytest -q` (from the repository root) |
| Quick inline test | Use `TestClient(app)` from `app.main` in a python script |
| Lint / typecheck | Not configured — no `pyproject.toml`, `ruff.toml`, or `setup.cfg` |

---

## 📦 Dependencies / environment

- **`requirements.txt`**: Was UTF-16LE with BOM; now UTF-8. Omits `numpy` and `scipy` even though `assignment_service.py:6-7` imports both. On a fresh machine: `pip install -r requirements.txt` then `python -c "import numpy; import scipy"` will fail until you `pip install numpy scipy` manually.
- **`venv/`**: Present in the working tree. Correctly `.gitignored` (0 tracked files). Do not commit `venv/`.
- **Pydantic v2**: Two files use deprecated `class Config`:
  - `app/core/config.py:17` → `model_config = {"case_sensitive": True}`
  - `app/schemas/responses.py:31` → `model_config = {"json_schema_extra": {...}}`

---

## 🧪 Testing

- Tests under `tests/` cover graph validation, assignment, Northwest, trees, Dijkstra, and Kruskal.
- Run the complete suite from the repository root with `.venv/bin/python -m pytest -q`.
- **Quirk**: `from app.main import app` works when running `python -m pytest` from `E:\IV0_5\MAT-361` but may fail if CWD is not on `sys.path`. Prefer the inline `TestClient` approach or running pytest from the root.

---

## 🔌 API endpoints (key behaviours)

| Endpoint | Notes |
|----------|-------|
| `GET /` | Root healthcheck. Returns `{"status":"online", ...}`. |
| `GET /health` | `SuccessResponse` envelope. |
| `POST /api/v1/graph/algorithms/dijkstra` | Real single-source shortest paths with step trace. Respects directed/undirected edges, requires non-negative weights, and optionally highlights a target path. |
| `POST /api/v1/graph/algorithms/kruskal` | Real minimum or maximum spanning tree/forest. Ignores edge direction with a warning and reports each edge decision. |
| `POST /api/v1/graph/algorithms/bfs` | **Stub**: returns `{"orden_recorrido": [start_node], "simulated": true}`. Same — payload ignored. |
| `POST /api/v1/graph/algorithms/johnson` | Real algorithm. Requires directed edges (`is_directed=True`). Returns `has_negative_cycle`, `distances`, `paths`. **Response**: does NOT use `response_model` — returns raw dict compatible with `SuccessResponse` fields. |
| `POST /api/v1/graph/algorithms/assignment` | Real Hungarian algorithm. Returns `assignments`, `total_cost`, `initial_cost_matrix`, `steps`, **and new**: `padding_info` (for rectangular matrices) and each step may have `selected_zeros`. Uses `response_model=AssignmentResponseSchema`. |
| `POST /api/v1/graph/algorithms` (router) | Router includes health, graph, and algorithms sub-routers. |

**CORS**: The custom preflight middleware was **removed** (was in `app/main.py`). It reflected any origin with `allow-credentials: true`, which is a latent risk. CORS is now handled solely by the `CORSMiddleware` added in FastAPI startup, with `allow_origin_regex` limiting to `localhost` and `127.0.0.1`.

---

## 🐛 Known gotchas / recent fixes

| Issue | File | Fix |
|-------|------|-----|
| `requirements.txt` UTF-16LE + missing numpy/scipy | `requirements.txt` | Converted to UTF-8; added `numpy>=1.26.0` and `scipy>=1.11.0` |
| CORS preflight middleware reflected any origin | `app/main.py` | Removed custom `handle_cors_preflight` middleware. CORSMiddleware only now. |
| 500 handler leaked `str(exc)` | `app/main.py:71-81` | Removed `details=str(exc)`; added `traceback.print_exc()` for server-side logging only. |
| `/bfs` is not implemented | `app/api/algorithms.py` | The response is explicitly marked `simulated: True`; Dijkstra and Kruskal are implemented separately. |
| Hungarian `steps` matrices wider than `initial_cost_matrix` for rect. matrices | `app/services/assignment_service.py:160-262` | Added `padding_info` to response and `selected_zeros` to `AssignmentStepSchema`. Frontend now knows which columns/rows are dummy. |
| `EdgeSchema` allowed negative weights on undirected graphs | `app/schemas/graph.py:28-48` | Added `@root_validator` that rejects `weight < 0` when `is_directed=False` (negative weights are valid only for directed graphs, used by Johnson). |
| `johnson_service.py` used `__import__("networkx").DiGraph` | `app/services/johnson_service.py:87` | Replaced with `import networkx as nx` + `nx.DiGraph`. |
| Pydantic v2 `class Config` deprecation warnings | `app/core/config.py`, `app/schemas/responses.py` | Changed to `model_config = {...}` syntax. |

---

## 📁 Project structure (high‑level)

```
MAT-361/
├── app/              # FastAPI application
│   ├── main.py       # App creation, CORS, exception handlers
│   ├── core/config.py # Settings (pydantic_settings.BaseSettings)
│   ├── api/router.py # Includes health, graph, algorithms routers
│   ├── api/health.py # /health endpoint
│   ├── api/algorithms.py # /dijkstra, /kruskal, /bfs, /johnson, /assignment
│   ├── schemas/      # Pydantic models for graphs, requests, and responses
│   └── services/     # Business logic for graph algorithms
├── requirements.txt  # Deps (UTF-8 now; numpy/scipy added)
├── tests/            # pytest tests (5 tests covering algorithms)
├── venv/             # Virtual environment — .gitignored
└── AGENTS.md         # This file
```

**No** `README.md`, `pyproject.toml`, `Dockerfile`, `.github/`, `Makefile`, or lint/formatter config exists. The project is small enough to read all source files in a single session.

---

## 🛠️ If you need to make changes

1. **Always check `requirements.txt` encoding** — if `import numpy` fails on a fresh clone, the file may have reverted to UTF-16LE. Convert with Notepad++ or `powershell -command [System.Text.Encoding]::UTF8.GetString([io.file]::ReadAllBytes("requirements.txt"))`.
2. **Pydantic v2 `model_config`** — use `model_config = {...}` not `class Config`.
3. **No `max_size` on `cost_matrix`** — the Hungarian algorithm will process arbitrary sizes; 60×60 produces ~585 KB of steps. Add a size guard if needed.
4. **Negative weight validation** is now in `EdgeSchema` — don't add `is_directed=False` edges with negative weight, or the validator will raise a 422 error.
5. **Tests**: run with `.\venv\Scripts\pytest.exe -q tests/test_algorithms.py` from the repo root.