from unidecode import unidecode

from qgis.PyQt.QtCore import QMetaType
from qgis.core import (
    Qgis,
    QgsFieldConstraints,
    QgsField,
    QgsDefaultValue,
    QgsEditorWidgetSetup,
    QgsMapLayer,
    QgsFields,
)

from json2qgis.types import FieldDef, LayerDef


def normalize_name(name: str) -> str:
    """
    Transliterates any string (including Cyrillic or non-ASCII characters) to ASCII.
    """
    name = unidecode(name)
    name = name.lower()
    name = name.replace(" ", "_")

    return name


def get_constraint_strength(strength: str) -> QgsFieldConstraints.ConstraintStrength:
    strengths = {
        "hard": QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard,
        "soft": QgsFieldConstraints.ConstraintStrength.ConstraintStrengthSoft,
        "not_set": QgsFieldConstraints.ConstraintStrength.ConstraintStrengthNotSet,
    }

    if strength not in strengths:
        raise NotImplementedError(f"Unknown constraint strength: {strength}")

    return strengths[strength]


def get_attribute_form_container_type(
    type_name: str,
) -> Qgis.AttributeEditorContainerType:
    type_names = {
        "group_box": Qgis.AttributeEditorContainerType.GroupBox,
        "tab": Qgis.AttributeEditorContainerType.Tab,
        "row": Qgis.AttributeEditorContainerType.Row,
    }

    if type_name not in type_names:
        raise NotImplementedError(
            f"Unsupported attribute container item type: {type_name}"
        )

    return type_names[type_name]


def get_field_type(type_name: str) -> QMetaType.Type:
    type_map = {
        "integer": QMetaType.Type.Int,
        "real": QMetaType.Type.Double,
        "string": QMetaType.Type.QString,
        "boolean": QMetaType.Type.Bool,
        "date": QMetaType.Type.QDate,
        "datetime": QMetaType.Type.QDateTime,
    }

    if type_name not in type_map:
        raise NotImplementedError(f"Unsupported field type: {type_name}")

    return type_map[type_name]


def get_layer_flags(
    flags: QgsMapLayer.LayerFlags, layer_def: LayerDef
) -> QgsMapLayer.LayerFlags:
    if layer_def.get("is_identifiable", False):
        flags |= QgsMapLayer.LayerFlag.Identifiable
    else:
        flags &= ~QgsMapLayer.LayerFlag.Identifiable  # type: ignore

    if layer_def.get("is_removable", False):
        flags |= QgsMapLayer.LayerFlag.Removable
    else:
        flags &= ~QgsMapLayer.LayerFlag.Removable  # type: ignore

    if layer_def.get("is_searchable", False):
        flags |= QgsMapLayer.LayerFlag.Searchable
    else:
        flags &= ~QgsMapLayer.LayerFlag.Searchable  # type: ignore

    if layer_def.get("is_private", False):
        flags |= QgsMapLayer.LayerFlag.Private
    else:
        flags &= ~QgsMapLayer.LayerFlag.Private  # type: ignore

    return flags


def create_field(field_def: FieldDef) -> QgsField:
    # Map FieldDef type to Qt QMetaType type IDs
    qt_type = get_field_type(field_def["type"])

    field = QgsField(
        field_def["name"],
        qt_type,
        len=field_def.get("length", 0),
        prec=field_def.get("precision", 0),
        comment=field_def.get("comment", ""),
    )

    return field


def create_fields(layer_def: LayerDef) -> QgsFields:
    fields = QgsFields()

    for field_def in layer_def["fields"]:
        field = create_field(field_def)
        fields.append(field)

    return fields


def set_field_default_value(field: QgsField, field_def: FieldDef) -> None:
    if field_def.get("default_value") is None:
        return

    default_value = QgsDefaultValue(
        field_def.get("default_value"),
        field_def.get("set_default_value_on_update", False),
    )
    field.setDefaultValueDefinition(default_value)


def set_field_constraints(field: QgsField, field_def: FieldDef) -> None:
    constraints = field.constraints()

    if field_def.get("is_not_null", False):
        is_not_null_strength = get_constraint_strength(
            field_def["is_not_null_strength"]
        )

        constraints.setConstraint(
            QgsFieldConstraints.Constraint.ConstraintNotNull,
            QgsFieldConstraints.ConstraintOrigin.ConstraintOriginLayer,
        )
        constraints.setConstraintStrength(
            QgsFieldConstraints.Constraint.ConstraintNotNull,
            is_not_null_strength,
        )

    if field_def.get("is_unique", False):
        is_unique_strength = get_constraint_strength(field_def["is_unique_strength"])

        constraints.setConstraint(
            QgsFieldConstraints.Constraint.ConstraintUnique,
            QgsFieldConstraints.ConstraintOrigin.ConstraintOriginLayer,
        )
        constraints.setConstraintStrength(
            QgsFieldConstraints.Constraint.ConstraintUnique,
            is_unique_strength,
        )

    if field_def.get("constraint_expression", ""):
        constraint_expression = field_def.get("constraint_expression", "")
        constraint_description = field_def.get("constraint_expression_description", "")
        constraint_expression_strength = get_constraint_strength(
            field_def["constraint_expression_strength"]
        )

        constraints.setConstraint(
            QgsFieldConstraints.Constraint.ConstraintExpression,
            QgsFieldConstraints.ConstraintOrigin.ConstraintOriginLayer,
        )
        constraints.setConstraintStrength(
            QgsFieldConstraints.Constraint.ConstraintExpression,
            constraint_expression_strength,
        )
        constraints.setConstraintExpression(
            constraint_expression, constraint_description
        )

    field.setConstraints(constraints)


def set_field_widget(field: QgsField, field_def: FieldDef) -> None:
    widget_type = field_def["widget_type"]
    # Widget configuration
    wc = field_def.get("widget_config", {})

    if widget_type == "Hidden":
        pass
    elif widget_type == "Color":
        pass
    elif widget_type == "CheckBox":
        wc.update(
            {
                "AllowNullState": wc.get("allow_null", False),
                "CheckedState": wc.get("checked_state", None),
                "UncheckedState": wc.get("unchecked_state", None),
                "TextDisplayMethod": wc.get("text_display_method", 1),
            }
        )
    elif widget_type == "Range":
        wc.update(
            {
                "Min": wc.get("min", 0),
                "Max": wc.get("max", 100),
                "Step": wc.get("step", 1),
                "Precision": wc.get("precision", 0),
                "Suffix": wc.get("suffix", ""),
                "Style": wc.get("style", "Slider"),
                "AllowNull": wc.get("allow_null", False),
            }
        )
    elif widget_type == "TextEdit":
        wc.update(
            {
                "IsMultiline": wc.get("is_multiline", False),
                "UseHtml": wc.get("use_html", False),
            }
        )
    elif widget_type == "DateTime":
        wc.update(
            {
                "allow_null": wc.get("allow_null", True),
                "calendar_popup": wc.get("calendar_popup", True),
                "display_format": wc.get("display_format", "yyyy-MM-dd HH:mm:ss"),
                "field_format": wc.get("field_format", "yyyy-MM-dd HH:mm:ss"),
                "field_format_overwrite": wc.get("field_format_overwrite", False),
                "field_iso_format": wc.get("field_iso_format", False),
            }
        )
    elif widget_type == "ExternalResource":
        wc.update(
            {
                "DocumentViewer": wc.get("is_document_viewer_enabled", True),
                "DocumentViewerHeight": wc.get("document_viewer_height", 0),
                "DocumentViewerWidth": wc.get("document_viewer_width", 0),
                "FileWidget": wc.get("use_file_widget", True),
                "FileWidgetButton": wc.get("show_file_widget_button", True),
                "FileWidgetFilter": wc.get("file_widget_filter", ""),
                "RelativeStorage": wc.get("use_relative_storage", 1),
                "StorageAuthConfigId": wc.get("storage_auth_config_id", None),
                "StorageMode": wc.get("storage_mode", 0),
                "StorageType": wc.get("storage_type", None),
            }
        )
    elif widget_type == "ValueMap":
        wc.update(
            {
                "map": wc.get("map", {}),
            }
        )
    else:
        raise NotImplementedError(f"Unsupported widget type: {widget_type}")

    widget_setup = QgsEditorWidgetSetup(widget_type, wc)
    field.setEditorWidgetSetup(widget_setup)
