import uuid
from typing import Any

from convert2qgis.json2qgis.type_defs import (
    FieldDef,
    FormItemDef,
    RasterDatasetDef,
    RelationDef,
    VectorDatasetDef,
    VectorLayerDataprovider,
)


def generate_field_def(**kwargs: Any) -> FieldDef:
    field_def = FieldDef(
        field_id=str(uuid.uuid4()),
        name="",
        type="",
        length=0,
        precision=0,
        comment="",
        is_not_null=False,
        is_not_null_strength="not_set",
        constraint_expression="",
        constraint_expression_description="",
        constraint_expression_strength="not_set",
        is_unique=False,
        is_unique_strength="not_set",
        default_value="",
        set_default_value_on_update=False,
        alias="",
        alias_expression="",
        widget_type="",
        widget_config={},
        is_read_only=False,
    )
    field_def.update(kwargs)

    return field_def


def generate_uuid_field_def(**kwargs: Any) -> FieldDef:
    field_def = generate_field_def(
        name="uuid",
        type="string",
        alias="UUID",
        default_value="uuid(format:='WithoutBraces')",
        widget_type="TextEdit",
    )
    field_def.update(kwargs)

    return field_def


def generate_vector_dataset_def(**kwargs: Any) -> VectorDatasetDef:
    vector_dataset_def = VectorDatasetDef(
        layer_id=str(uuid.uuid4()),
        crs="EPSG:4326",
        name="",
        custom_properties={},
        is_read_only=False,
        is_identifiable=False,
        is_private=False,
        is_searchable=False,
        is_removable=True,
        primary_key="",
        geometry_type="NoGeometry",
        layer_type="vector",
        datasource_format=VectorLayerDataprovider.GPKG,
        fields=[],
        form_config=[],
        data=[],
        indices=[],
        foreign_keys=[],
        display_expression="",
    )
    vector_dataset_def.update(kwargs)

    return vector_dataset_def


def generate_raster_dataset_def(**kwargs: Any) -> RasterDatasetDef:
    raster_dataset_def = RasterDatasetDef(
        layer_id=str(uuid.uuid4()),
        crs="EPSG:4326",
        name="",
        custom_properties={},
        is_read_only=False,
        is_identifiable=False,
        is_private=False,
        is_searchable=False,
        is_removable=True,
        layer_type="raster",
        datasource="",
        datasource_format="wms",
    )
    raster_dataset_def.update(kwargs)

    return raster_dataset_def


def generate_form_item_def(**kwargs: Any) -> FormItemDef:
    if kwargs.get("type") in ("field", "relation"):
        form_item = FormItemDef(
            field_name=None,
            item_id=str(uuid.uuid4()),
            parent_id=None,
            type="field",
            is_label_on_top=True,
        )
        form_item.update(kwargs)

        return form_item

    form_item = FormItemDef(
        item_id=str(uuid.uuid4()),
        label="",
        parent_id=None,
        type="group_box",
    )
    form_item.update(kwargs)

    return form_item


def generate_relation_def(**kwargs: Any) -> RelationDef:
    relation_def = RelationDef(
        relation_id=str(uuid.uuid4()),
        name="",
        from_layer_id="",
        to_layer_id="",
        strength="association",
        field_pairs=[],
    )
    relation_def.update(kwargs)

    return relation_def
