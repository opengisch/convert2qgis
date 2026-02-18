from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, TypedDict

RelationStrength = Literal["association", "composition"]
ConstraintStrength = Literal["hard", "soft", "not_set"]
CrsDef = str
GeometryType = Literal["Point", "LineString", "Polygon", "NoGeometry"]
FormItemTypes = Literal["field", "relation", "group_box", "tab", "row", "text"]
FormItemGroupTypes = Literal["group_box", "tab"]
LayerType = Literal["vector", "raster", "mesh", "vector_tile", "point_cloud"]


class RelationFieldPairDef(TypedDict):
    from_field: str
    to_field: str


class RelationDef(TypedDict):
    relation_id: str
    name: str
    from_layer_id: str
    to_layer_id: str
    field_pairs: list[RelationFieldPairDef]
    strength: RelationStrength


class PolymorphicRelationDef(TypedDict):
    relation_id: str
    name: str
    from_layer_id: str
    to_layer_field: str
    to_layer_expression: str
    to_layer_ids: str
    field_pairs: list[RelationFieldPairDef]
    strength: RelationStrength


class WeakFieldDef(TypedDict, total=False):
    field_id: str
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
    alias_expression: str
    widget_type: str
    widget_config: dict[str, Any]


class FieldDef(TypedDict):
    field_id: str
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
    alias_expression: str
    widget_type: str
    widget_config: dict[str, object]


class LayerTreeItemDef(TypedDict):
    item_id: str
    type: Literal["group", "layer"]
    name: str
    parent_id: str
    layer_id: str | None
    is_checked: bool


class VectorLayerDataprovider(StrEnum):
    GPKG = "gpkg"
    MEMORY = "memory"


class WeakFormItemDef(TypedDict, total=False):
    item_id: str
    type: FormItemTypes
    field_name: str
    label: str
    parent_id: str | None
    visibility_expression: str
    background_color: str
    is_collapsed: bool
    column_count: int
    is_markdown: bool
    show_label: bool
    is_read_only: bool


class FormItemDef(TypedDict):
    item_id: str
    type: FormItemTypes
    field_name: str
    label: str
    parent_id: str | None
    visibility_expression: str
    background_color: str
    is_collapsed: bool
    column_count: int
    is_markdown: bool
    show_label: bool
    is_read_only: bool


class WeakLayerDef(TypedDict, total=False):
    layer_id: str
    name: str
    geometry_type: GeometryType
    layer_type: LayerType
    crs: CrsDef
    datasource_format: str
    fields: list[FieldDef]
    form_config: list[FormItemDef]
    data: list[dict[str, Any]]
    primary_key: str
    indices: list[str]

    is_read_only: bool
    is_identifiable: bool
    is_private: bool
    is_searchable: bool
    is_removable: bool


class LayerDef(TypedDict):
    layer_id: str
    name: str
    geometry_type: GeometryType
    layer_type: LayerType
    crs: CrsDef
    datasource_format: str
    fields: list[FieldDef]
    form_config: list[FormItemDef]
    data: list[dict[str, Any]]
    primary_key: str
    indices: list[str]

    is_read_only: bool
    is_identifiable: bool
    is_private: bool
    is_searchable: bool
    is_removable: bool


class ProjectDef(TypedDict):
    version: str
    title: str
    author: str
    layers: list[LayerDef]
    layer_tree: list[LayerTreeItemDef]

    crs: CrsDef


# we might have more fields in the sheet than we actually use, so we want them in the ChoicesDef
class ChoicesDef(TypedDict, total=False):
    name: str
    label: str


class AliasSimpleDef(TypedDict, total=False):
    alias: str


class AliasWithExpressionDef(TypedDict, total=False):
    alias_expression: str


AliasDef = AliasSimpleDef | AliasWithExpressionDef


PathOrStr = str | Path
