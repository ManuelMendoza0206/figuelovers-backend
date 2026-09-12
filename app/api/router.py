from fastapi import APIRouter
from app.api import health, graph, algorithms

api_router = APIRouter()

# Enganchamos todos los sub-módulos
api_router.include_router(health.router)
api_router.include_router(graph.router)
api_router.include_router(algorithms.router)