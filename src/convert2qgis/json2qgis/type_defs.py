from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, fields
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, TypeAlias, TypeVar, cast

RelationStrength: TypeAlias = Literal["association", "composition"]
ConstraintStrength: TypeAlias = Literal["hard", "soft", "not_set"]
CrsDef = str
GeometryType: TypeAlias = Literal[
    "Point",
    "LineString",
    "Polygon",
    "MultiPoint",
    "MultiLineString",
    "MultiPolygon",
    "NoGeometry",
]
FormItemTypes: TypeAlias = Literal[
    "field", "relation", "group_box", "tab", "row", "text"
]
FormItemGroupTypes: TypeAlias = Literal["group_box", "tab"]
LayerType: TypeAlias = Literal["vector", "raster", "mesh", "vector_tile", "point_cloud"]


T = TypeVar("T", bound="DataclassModelMixin")


def _serialize(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, DataclassModelMixin):
        return value.to_dict()
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}

    return value


class DataclassModelMixin:
    __SKIP_FIELDS__: set[str] = set()
    """List of field names to skip when serializing to dict or comparing for equality. This is useful for fields that are not part of the actual data model, but are used for internal purposes."""

    def _iter_items(self) -> Iterable[tuple[str, Any]]:
        for key, value in self.__dict__.items():
            if key.startswith("_") or value is None or key in self.__SKIP_FIELDS__:
                continue
            yield key, value

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __bool__(self) -> bool:
        return any(True for _ in self._iter_items())

    def update(self, *args: object, **kwargs: Any) -> None:
        data: dict[str, Any] = {}
        if args:
            [other] = args
            if isinstance(other, DataclassModelMixin):
                data.update(dict(other._iter_items()))
            elif isinstance(other, Mapping):
                data.update(other)
            else:
                data.update(dict(cast(Iterable[tuple[str, Any]], other)))
        data.update(kwargs)
        for key, value in data.items():
            setattr(self, key, value)

    def to_dict(self) -> dict[str, Any]:
        return {key: _serialize(value) for key, value in self._iter_items()}

    @classmethod
    def from_data(cls: type[T], data: T | Mapping[str, Any]) -> T:
        if isinstance(data, cls):
            return data

        return cls._from_dict(cast(Mapping[str, Any], data))

    @classmethod
    def _from_dict(cls: type[T], data: Mapping[str, Any]) -> T:
        instance = cls()
        instance.update(data)
        return instance


@dataclass
class RelationFieldPairDef(DataclassModelMixin):
    from_field: str = ""
    to_field: str = ""


@dataclass
class RelationDef(DataclassModelMixin):
    relation_id: str = ""
    name: str = ""
    from_layer_id: str = ""
    to_layer_id: str = ""
    field_pairs: list[RelationFieldPairDef] = field(default_factory=list)
    strength: RelationStrength = "association"

    @classmethod
    def _from_dict(cls, data: Mapping[str, Any]) -> "RelationDef":
        return cls(
            relation_id=data.get("relation_id", ""),
            name=data.get("name", ""),
            from_layer_id=data.get("from_layer_id", ""),
            to_layer_id=data.get("to_layer_id", ""),
            field_pairs=[
                RelationFieldPairDef.from_data(item)
                for item in data.get("field_pairs", [])
            ],
            strength=data.get("strength", "association"),
        )


@dataclass
class PolymorphicRelationDef(DataclassModelMixin):
    relation_id: str = ""
    name: str = ""
    from_layer_id: str = ""
    to_layer_field: str = ""
    to_layer_expression: str = ""
    to_layer_ids: list[str] = field(default_factory=list)
    field_pairs: list[RelationFieldPairDef] = field(default_factory=list)
    strength: RelationStrength = "association"

    @classmethod
    def _from_dict(cls, data: Mapping[str, Any]) -> "PolymorphicRelationDef":
        return cls(
            relation_id=data.get("relation_id", ""),
            name=data.get("name", ""),
            from_layer_id=data.get("from_layer_id", ""),
            to_layer_field=data.get("to_layer_field", ""),
            to_layer_expression=data.get("to_layer_expression", ""),
            to_layer_ids=list(data.get("to_layer_ids", [])),
            field_pairs=[
                RelationFieldPairDef.from_data(item)
                for item in data.get("field_pairs", [])
            ],
            strength=data.get("strength", "association"),
        )


@dataclass
class WeakFieldDef(DataclassModelMixin):
    field_id: str | None = None
    name: str | None = None
    type: str | None = None
    length: int | None = None
    precision: int | None = None
    comment: str | None = None
    is_not_null: bool | None = None
    is_not_null_strength: ConstraintStrength | None = None
    constraint_expression: str | None = None
    constraint_expression_description: str | None = None
    constraint_expression_strength: ConstraintStrength | None = None
    is_unique: bool | None = None
    is_unique_strength: ConstraintStrength | None = None
    default_value: str | None = None
    set_default_value_on_update: bool | None = None
    alias: str | None = None
    alias_expression: str | None = None
    widget_type: str | None = None
    widget_config: dict[str, Any] | None = None
    is_read_only: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            field_def.name: _serialize(getattr(self, field_def.name))
            for field_def in fields(self)
            if getattr(self, field_def.name) is not None
        }


@dataclass
class FieldDef(DataclassModelMixin):
    field_id: str = ""
    name: str = ""
    type: str = ""
    length: int = 0
    precision: int = 0
    comment: str = ""
    is_not_null: bool = False
    is_not_null_strength: ConstraintStrength = "not_set"
    constraint_expression: str = ""
    constraint_expression_description: str = ""
    constraint_expression_strength: ConstraintStrength = "not_set"
    is_unique: bool = False
    is_unique_strength: ConstraintStrength = "not_set"
    default_value: str | None = ""
    set_default_value_on_update: bool = False
    alias: str = ""
    alias_expression: str = ""
    widget_type: str = ""
    widget_config: dict[str, object] = field(default_factory=dict)
    is_read_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_id": self.field_id,
            "name": self.name,
            "type": self.type,
            "length": self.length,
            "precision": self.precision,
            "comment": self.comment,
            "is_not_null": self.is_not_null,
            "is_not_null_strength": self.is_not_null_strength,
            "constraint_expression": self.constraint_expression,
            "constraint_expression_description": self.constraint_expression_description,
            "constraint_expression_strength": self.constraint_expression_strength,
            "is_unique": self.is_unique,
            "is_unique_strength": self.is_unique_strength,
            "default_value": self.default_value,
            "set_default_value_on_update": self.set_default_value_on_update,
            "alias": self.alias,
            "alias_expression": self.alias_expression,
            "widget_type": self.widget_type,
            "widget_config": _serialize(self.widget_config),
        }


@dataclass
class LayerTreeItemDef(DataclassModelMixin):
    item_id: str = ""
    type: Literal["group", "layer"] = "group"
    name: str = ""
    parent_id: str | None = None
    layer_id: str | None = None
    is_checked: bool = True
    is_mutually_exclusive: bool = False
    mutually_exclusive_child_index: int = -1

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "item_id": self.item_id,
            "type": self.type,
            "name": self.name,
            "parent_id": self.parent_id,
            "is_checked": self.is_checked,
        }
        if self.layer_id is not None:
            data["layer_id"] = self.layer_id
        if self.type == "group":
            data["is_mutually_exclusive"] = self.is_mutually_exclusive
            data["mutually_exclusive_child_index"] = self.mutually_exclusive_child_index

        return data


class VectorLayerDataprovider(StrEnum):
    GPKG = "gpkg"
    MEMORY = "memory"


@dataclass
class WeakFormItemDef(DataclassModelMixin):
    item_id: str | None = None
    type: FormItemTypes | None = None
    field_name: str | None = None
    label: str | None = None
    parent_id: str | None = None
    visibility_expression: str | None = None
    background_color: str | None = None
    is_collapsed: bool | None = None
    column_count: int | None = None
    is_markdown: bool | None = None
    show_label: bool | None = None
    is_read_only: bool | None = None
    is_label_on_top: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            field_def.name: _serialize(getattr(self, field_def.name))
            for field_def in fields(self)
            if getattr(self, field_def.name) is not None
        }


@dataclass
class FormItemDef(DataclassModelMixin):
    item_id: str = ""
    type: FormItemTypes = "group_box"
    field_name: str | None = None
    label: str = ""
    parent_id: str | None = None
    visibility_expression: str = ""
    background_color: str = ""
    is_collapsed: bool = False
    column_count: int = 1
    is_markdown: bool = False
    show_label: bool = True
    is_read_only: bool = False
    is_label_on_top: bool = False

    def to_dict(self) -> dict[str, Any]:
        if self.type in ("field", "relation"):
            field_data: dict[str, Any] = {
                "item_id": self.item_id,
                "type": self.type,
                "field_name": self.field_name,
                "parent_id": self.parent_id,
            }
            if self.visibility_expression:
                field_data["visibility_expression"] = self.visibility_expression
            if self.show_label is not True:
                field_data["show_label"] = self.show_label
            if self.is_read_only:
                field_data["is_read_only"] = self.is_read_only
            if self.is_label_on_top:
                field_data["is_label_on_top"] = self.is_label_on_top

            return field_data

        container_data: dict[str, Any] = {
            "item_id": self.item_id,
            "type": self.type,
            "label": self.label,
            "parent_id": self.parent_id,
        }
        if self.visibility_expression:
            container_data["visibility_expression"] = self.visibility_expression
        if self.background_color:
            container_data["background_color"] = self.background_color
        if self.is_collapsed:
            container_data["is_collapsed"] = self.is_collapsed
        if self.column_count != 1:
            container_data["column_count"] = self.column_count
        if self.is_markdown:
            container_data["is_markdown"] = self.is_markdown

        return container_data


@dataclass
class WeakLayerDef(DataclassModelMixin):
    layer_id: str | None = None
    name: str | None = None
    geometry_type: GeometryType | None = None
    layer_type: LayerType | None = None
    crs: CrsDef | None = None
    datasource_format: str | None = None
    fields: list[FieldDef] | None = None
    form_config: list[FormItemDef] | None = None
    data: list[dict[str, Any]] | None = None
    primary_key: str | None = None
    indices: list[str] | None = None
    foreign_keys: list[Any] | None = None
    custom_properties: dict[str, Any] | None = None
    display_expression: str | None = None
    datasource: str | None = None
    is_read_only: bool | None = None
    is_identifiable: bool | None = None
    is_private: bool | None = None
    is_searchable: bool | None = None
    is_removable: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            field_def.name: _serialize(getattr(self, field_def.name))
            for field_def in fields(self)
            if getattr(self, field_def.name) is not None
        }


@dataclass
class BaseLayerDef(DataclassModelMixin):
    layer_id: str = ""
    name: str = ""
    layer_type: LayerType = "vector"
    crs: CrsDef = "EPSG:4326"
    custom_properties: dict[str, Any] = field(default_factory=dict)
    is_read_only: bool = False
    is_identifiable: bool = False
    is_private: bool = False
    is_searchable: bool = False
    is_removable: bool = True


@dataclass
class VectorLayerDef(BaseLayerDef):
    layer_type: Literal["vector"] = "vector"
    geometry_type: GeometryType = "NoGeometry"
    datasource_format: str = VectorLayerDataprovider.GPKG
    fields: list[FieldDef] = field(default_factory=list)
    form_config: list[FormItemDef] = field(default_factory=list)
    data: list[dict[str, Any]] = field(default_factory=list)
    primary_key: str = ""
    indices: list[str] = field(default_factory=list)
    foreign_keys: list[Any] = field(default_factory=list)
    display_expression: str = ""

    @classmethod
    def _from_dict(cls, data: Mapping[str, Any]) -> "VectorLayerDef":
        return cls(
            layer_id=data.get("layer_id", ""),
            name=data.get("name", ""),
            layer_type="vector",
            crs=data.get("crs", "EPSG:4326"),
            custom_properties=dict(data.get("custom_properties", {})),
            is_read_only=data.get("is_read_only", False),
            is_identifiable=data.get("is_identifiable", False),
            is_private=data.get("is_private", False),
            is_searchable=data.get("is_searchable", False),
            is_removable=data.get("is_removable", True),
            geometry_type=data.get("geometry_type", "NoGeometry"),
            datasource_format=data.get(
                "datasource_format", VectorLayerDataprovider.GPKG
            ),
            fields=[FieldDef.from_data(item) for item in data.get("fields", [])],
            form_config=[
                FormItemDef.from_data(item) for item in data.get("form_config", [])
            ],
            data=list(data.get("data", [])),
            primary_key=data.get("primary_key", ""),
            indices=list(data.get("indices", [])),
            foreign_keys=list(data.get("foreign_keys", [])),
            display_expression=data.get("display_expression", ""),
        )


@dataclass
class RasterLayerDef(BaseLayerDef):
    layer_type: Literal["raster"] = "raster"
    datasource: str = ""
    datasource_format: str = "wms"

    @classmethod
    def _from_dict(cls, data: Mapping[str, Any]) -> "RasterLayerDef":
        return cls(
            layer_id=data.get("layer_id", ""),
            name=data.get("name", ""),
            layer_type="raster",
            crs=data.get("crs", "EPSG:4326"),
            custom_properties=dict(data.get("custom_properties", {})),
            is_read_only=data.get("is_read_only", False),
            is_identifiable=data.get("is_identifiable", False),
            is_private=data.get("is_private", False),
            is_searchable=data.get("is_searchable", False),
            is_removable=data.get("is_removable", True),
            datasource=data.get("datasource", ""),
            datasource_format=data.get("datasource_format", "wms"),
        )


LayerDef = VectorLayerDef | RasterLayerDef


@dataclass
class ProjectMetadataDef(DataclassModelMixin):
    custom_properties: dict[str, Any] = field(default_factory=dict)
    crs: CrsDef = "EPSG:4326"
    author: str = ""
    title: str = ""
    extent: str = ""


@dataclass
class ProjectDef(DataclassModelMixin):
    project: ProjectMetadataDef = field(default_factory=ProjectMetadataDef)
    version: str = ""
    layers: list[LayerDef] = field(default_factory=list)
    layer_tree: list[LayerTreeItemDef] = field(default_factory=list)
    relations: list[RelationDef] = field(default_factory=list)
    polymorphic_relations: list[PolymorphicRelationDef] = field(default_factory=list)

    @classmethod
    def _from_dict(cls, data: Mapping[str, Any]) -> "ProjectDef":
        return cls(
            project=ProjectMetadataDef.from_data(data.get("project", {})),
            version=data.get("version", ""),
            layers=[layer_from_data(item) for item in data.get("layers", [])],
            layer_tree=[
                LayerTreeItemDef.from_data(item) for item in data.get("layer_tree", [])
            ],
            relations=[
                RelationDef.from_data(item) for item in data.get("relations", [])
            ],
            polymorphic_relations=[
                PolymorphicRelationDef.from_data(item)
                for item in data.get("polymorphic_relations", [])
            ],
        )


def layer_from_data(data: LayerDef | Mapping[str, Any]) -> LayerDef:
    if isinstance(data, VectorLayerDef):
        return data
    if isinstance(data, RasterLayerDef):
        return data

    layer_type = data.get("layer_type")
    if layer_type == "vector":
        return VectorLayerDef.from_data(data)
    if layer_type == "raster":
        return RasterLayerDef.from_data(data)

    raise NotImplementedError(f"Unsupported layer type: {layer_type}")


# we might have more fields in the sheet than we actually use, so we want them in the ChoicesDef
@dataclass(eq=False)
class ChoicesDef(DataclassModelMixin):
    __SKIP_FIELDS__ = {"additional_columns"}

    name: str
    label: str
    list_name: str

    additional_columns: dict[str, str] = field(default_factory=dict)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ChoicesDef):
            return self.to_dict() == other.to_dict()
        if isinstance(other, Mapping):
            return self.to_dict() == dict(other)

        return False


@dataclass
class AliasSimpleDef(DataclassModelMixin):
    alias: str = ""


@dataclass
class AliasWithExpressionDef(DataclassModelMixin):
    alias_expression: str = ""


AliasDef = AliasSimpleDef | AliasWithExpressionDef


PathOrStr = str | Path
