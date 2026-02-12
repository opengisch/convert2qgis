from typing import cast
import uuid
from json2qgis.type_defs import FieldDef, LayerDef, FormItemDef, RelationDef


def generate_field_def(**kwargs) -> FieldDef:
    return cast(
        FieldDef,
        {
            "field_id": str(uuid.uuid4()),
            "name": "",
            "type": "",
            "length": 0,
            "precision": 0,
            "comment": "",
            "is_not_null": False,
            "is_not_null_strength": "not_set",
            "constraint_expression": "",
            "constraint_expression_description": "",
            "constraint_expression_strength": "not_set",
            "is_unique": False,
            "is_unique_strength": "not_set",
            "default_value": "",
            "set_default_value_on_update": False,
            "alias": "",
            "widget_type": "",
            "widget_config": {},
            **kwargs,
        },
    )


def generate_layer_def(**kwargs) -> LayerDef:
    return cast(
        LayerDef,
        {
            "layer_id": str(uuid.uuid4()),
            "name": "",
            "primary_key": "",
            "geometry_type": "NoGeometry",
            "layer_type": "vector",
            "crs": "EPSG:4326",
            "datasource_format": "gpkg",
            "fields": [],
            "form_config": [],
            "is_read_only": False,
            "is_identifiable": False,
            "is_private": False,
            "is_searchable": False,
            "is_removable": True,
            "indices": [],
            "foreign_keys": [],
            **kwargs,
        },
    )


def generate_form_item_def(**kwargs) -> FormItemDef:
    return cast(
        FormItemDef,
        {
            "item_id": str(uuid.uuid4()),
            "field_name": None,
            "label": "",
            "type": "group_box",
            "parent_id": None,
            "visibility_expression": "",
            "background_color": "",
            "is_collapsed": False,
            "column_count": 1,
            "is_markdown": False,
            "is_label_on_top": True,
            **kwargs,
        },
    )


def generate_relation_def(**kwargs) -> RelationDef:
    return cast(
        RelationDef,
        {
            "relation_id": str(uuid.uuid4()),
            "name": "",
            "from_layer_id": "",
            "to_layer_id": "",
            "strength": "association",
            "field_pairs": [],
            **kwargs,
        },
    )
