from unidecode import unidecode

from qgis.PyQt.QtCore import QMetaType
from qgis.core import (
    Qgis,
    QgsFieldConstraints,
    QgsField,
    QgsDefaultValue,
)

from json2qgis.types import FieldDef


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
        "date": QMetaType.Type.QDate,
        "datetime": QMetaType.Type.QDateTime,
    }

    if type_name not in type_map:
        raise NotImplementedError(f"Unsupported field type: {type_name}")

    return type_map[type_name]


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
        unique_strength = get_constraint_strength(field_def["unique_strength"])

        constraints.setConstraint(
            QgsFieldConstraints.Constraint.ConstraintUnique,
            QgsFieldConstraints.ConstraintOrigin.ConstraintOriginLayer,
        )
        constraints.setConstraintStrength(
            QgsFieldConstraints.Constraint.ConstraintUnique,
            unique_strength,
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
