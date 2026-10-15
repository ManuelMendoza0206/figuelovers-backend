from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.graph import GraphPayloadSchema


TreeOrder = Literal["preorder", "inorder", "postorder"]


class TreeNodeSchema(BaseModel):
    id: str
    value: int
    left: str | None = None
    right: str | None = None


class TreeEdgeSchema(BaseModel):
    source: str
    target: str


class TreeSchema(BaseModel):
    root_id: str | None
    nodes: list[TreeNodeSchema]
    edges: list[TreeEdgeSchema]


class TreeBuildRequestSchema(BaseModel):
    mode: Literal["values", "random"]
    values: list[Any] | None = None
    count: int | None = None
    seed: int | None = None


class TreeBuildResponseSchema(BaseModel):
    tree: TreeSchema
    traversals: dict[str, list[int]]


class TreeTraverseRequestSchema(BaseModel):
    tree: TreeSchema | None = None
    graph: GraphPayloadSchema | None = None
    order: TreeOrder


class TreeVisitSchema(BaseModel):
    id: str
    value: int


class TreeTraverseResponseSchema(BaseModel):
    order: TreeOrder
    visits: list[TreeVisitSchema]
    node_ids: list[str]
    values: list[int]


class TreeReconstructRequestSchema(BaseModel):
    inorder: list[Any]
    other: list[Any]
    other_order: Literal["preorder", "postorder"]


class TreeReconstructResponseSchema(BaseModel):
    tree: TreeSchema
    traversals: dict[str, list[int]]
    is_bst: bool
