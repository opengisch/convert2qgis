from typing import TypedDict, Literal
from enum import StrEnum


RelationStrength = Literal["association", "composition"]
ConstraintStrength = Literal["hard", "soft", "not_set"]
CrsDef = str


class RelationFieldPairDef(TypedDict):
    from_field: str
    to_field: str


class RelationDef(TypedDict):
    id: str
    name: str
    from_layer_id: str
    to_layer_id: str
    field_pairs: list[RelationFieldPairDef]
    strength: RelationStrength


class PolymorphicRelationDef(TypedDict):
    id: str
    name: str
    from_layer_id: str
    to_layer_field: str
    to_layer_expression: str
    to_layer_ids: str
    field_pairs: list[RelationFieldPairDef]
    strength: RelationStrength


class FieldDef(TypedDict):
    id: str
    name: str
    type: str
    length: int
    precision: int
    comment: str

    is_not_null: bool
    is_not_null_strength: ConstraintStrength

    constraint_expression: str
    constraint_expression_description: str
    constraint_expression_strength: ConstraintStrength

    is_unique: bool
    is_unique_strength: ConstraintStrength

    default_value: str | None
    set_default_value_on_update: bool
    alias: str
    widget_type: str
    widget_config: dict[str, object]


class LayerType(StrEnum):
    VECTOR = "vector"
    RASTER = "raster"
    MESH = "mesh"
    VECTOR_TILE = "vector_tile"
    POINT_CLOUD = "point_cloud"


class LayerTreeItemDef(TypedDict):
    id: str
    type: Literal["group", "layer"]
    name: str
    parent: str
    layer_id: str | None
    is_checked: bool


class VectorLayerDataprovider(StrEnum):
    GPKG = "gpkg"
    MEMORY = "memory"


class FormConfigItemDef(TypedDict):
    id: str
    type: Literal["field", "group_box", "tab", "row", "text"]
    name: str
    parent_id: str | None
    visibility_expression: str
    background_color: str
    is_collapsed: bool
    column_count: int
    is_markdown: bool


class FormConfigDef(TypedDict):
    items: list[FormConfigItemDef]


class LayerDef(TypedDict):
    layer_id: str
    name: str
    geometry_type: Literal["Point", "LineString", "Polygon"]
    type: LayerType
    crs: CrsDef
    datasource_format: str
    fields: list[FieldDef]
    form_config: FormConfigDef

    is_read_only: bool
    is_identifiable: bool
    is_private: bool
    is_searchable: bool
    is_removable: bool


class LayerTreeDef(TypedDict):
    children: list[LayerTreeItemDef]


class ProjectDef(TypedDict):
    version: str
    title: str
    author: str
    layers: list[LayerDef]
    layer_tree: LayerTreeDef
