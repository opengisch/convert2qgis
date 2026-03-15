import functools
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from qgis.core import (
    Qgis,
    QgsAttributeEditorContainer,
    QgsAttributeEditorField,
    QgsAttributeEditorRelation,
    QgsAttributeEditorTextElement,
    QgsDefaultValue,
    QgsEditFormConfig,
    QgsEditorWidgetSetup,
    QgsExpression,
    QgsField,
    QgsFieldConstraints,
    QgsFields,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsMapLayer,
    QgsOptionalExpression,
    QgsPolymorphicRelation,
    QgsProject,
    QgsProperty,
    QgsPropertyCollection,
    QgsRelation,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QMetaType
from qgis.PyQt.QtGui import QColor
from unidecode import unidecode

from convert2qgis.json2qgis.errors import MissingParentError, Qgis2JsonError
from convert2qgis.json2qgis.type_defs import (
    FieldDef,
    LayerDef,
    PolymorphicRelationDef,
    ProjectDef,
    RelationDef,
    RelationStrength,
    VectorLayerDataprovider,
    VectorLayerDef,
)

try:
    import fastjsonschema
    from fastjsonschema.ref_resolver import resolve_path
except ModuleNotFoundError:
    fastjsonschema = None

    resolve_path = None


try:
    import markdown
except ModuleNotFoundError:
    markdown = None  # type: ignore

logger = logging.getLogger(__name__)


_VALIDATORS_BY_PATH: dict[str, Callable[[dict[str, Any]], None]] = {}


def get_schema_json() -> dict[str, Any]:
    schema_json = (
        Path(__file__).parent.joinpath("./schema/schema_20251121.json").read_text()
    )
    return json.loads(schema_json)


def get_schema_validator() -> Callable[[dict[str, Any]], None]:
    schema = get_schema_json()

    if fastjsonschema:
        return fastjsonschema.compile(schema)  # type: ignore
    else:
        return lambda data: None  # type: ignore


def check_output(path: str):
    schema = get_schema_json()

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # If `fastjsonschema` is not available, skip validation and just execute the function
            if resolve_path is None or fastjsonschema is None:
                return func(*args, **kwargs)

            validate = _VALIDATORS_BY_PATH.get(path)
            if validate is None:
                schema_node = resolve_path(schema, path)
                if isinstance(schema_node, dict):
                    schema_node = {
                        "definitions": schema.get("definitions", {}),
                        **schema_node,
                    }
                validate = cast(
                    Callable[[dict[str, Any]], None],
                    fastjsonschema.compile(schema_node),
                )
                _VALIDATORS_BY_PATH[path] = validate

            output = func(*args, **kwargs)
            try:
                validate(output)
            except Exception as e:
                logger.error(f"Error during function '{func.__name__}' execution: {e}")
                raise

            return output

        return wrapper

    return decorator


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


def get_layer_edit_form(
    fields: QgsFields,
    layer_def: VectorLayerDef,
    form_config: QgsEditFormConfig | None = None,
) -> QgsEditFormConfig:
    if form_config is None:
        form_config = QgsEditFormConfig()

    form_config.setLayout(Qgis.AttributeFormLayout.DragAndDrop)
    form_config.clearTabs()

    containers_mapping: dict[str, QgsAttributeEditorContainer] = {}

    for form_item_def in layer_def["form_config"]:
        item_type = form_item_def["type"]
        # TODO @suricactus: ensure we should use `dict().get()`` here
        item_label = form_item_def.get("label", "")
        item_parent_id = form_item_def.get("parent_id")

        parent = None
        if item_parent_id:
            parent = containers_mapping.get(item_parent_id)

            if not parent:
                raise MissingParentError(
                    f"Parent with ID '{item_parent_id}' not found for form item '{item_label}'"
                )
        else:
            parent = form_config.invisibleRootContainer()

        if item_type == "field":
            field_idx = fields.indexOf(form_item_def["field_name"])

            assert field_idx != -1, (
                f"Could not find field {form_item_def['field_name']}"
            )

            if form_item_def.get("visibility_expression", ""):
                parent_container = QgsAttributeEditorContainer("~CONDITIONAL~", parent)
                parent_container.setVisibilityExpression(
                    QgsOptionalExpression(
                        QgsExpression(form_item_def["visibility_expression"])
                    )
                )
                parent_container.setShowLabel(False)
                container = QgsAttributeEditorField(
                    form_item_def["field_name"],
                    fields.indexOf(form_item_def["field_name"]),
                    parent_container,
                )

                parent_container.addChildElement(container)

                if parent:
                    parent.addChildElement(parent_container)
            else:
                container = QgsAttributeEditorField(
                    form_item_def["field_name"],
                    fields.indexOf(form_item_def["field_name"]),
                    parent,
                )

                if parent:
                    parent.addChildElement(container)

            if form_item_def.get("is_read_only", False):
                form_config.setReadOnly(field_idx, True)

            if form_item_def.get("is_label_on_top", False):
                form_config.setLabelOnTop(field_idx, True)

            container.setShowLabel(form_item_def.get("show_label", True))

            continue

        elif item_type == "relation":
            if form_item_def.get("visibility_expression", ""):
                parent_container = QgsAttributeEditorContainer("", parent)
                parent_container.setVisibilityExpression(
                    QgsOptionalExpression(
                        QgsExpression(form_item_def["visibility_expression"])
                    )
                )
                container = QgsAttributeEditorRelation(
                    form_item_def["field_name"],
                    form_item_def["item_id"],
                    parent_container,
                )

                parent_container.addChildElement(container)

                if parent:
                    parent.addChildElement(parent_container)
            else:
                container = QgsAttributeEditorRelation(
                    form_item_def["field_name"],
                    form_item_def["item_id"],
                    parent,
                )

                if parent:
                    parent.addChildElement(container)

            continue

        elif item_type == "text":
            if form_item_def["is_markdown"]:
                if markdown:
                    item_label = markdown.markdown(item_label)
                else:
                    logger.warning(
                        f"Markdown support is not available. Text item '{item_label}' will not be rendered as HTML, but as raw markdown."
                    )

            container = QgsAttributeEditorTextElement(item_label, parent)

            if parent:
                parent.addChildElement(container)

            container.setText(item_label)
            container.setShowLabel(False)

            continue

        container = QgsAttributeEditorContainer(item_label, parent)
        container.setType(get_attribute_form_container_type(item_type))

        if form_item_def.get("visibility_expression", ""):
            container.setVisibilityExpression(
                QgsOptionalExpression(
                    QgsExpression(form_item_def.get("visibility_expression", ""))
                )
            )

        if form_item_def.get("background_color", ""):
            container.setBackgroundColor(
                QColor(form_item_def.get("background_color", ""))
            )

        container.setCollapsed(form_item_def.get("is_collapsed", False))
        container.setColumnCount(form_item_def.get("column_count", 1))

        if parent:
            parent.addChildElement(container)

        containers_mapping[form_item_def["item_id"]] = container

    for container in containers_mapping.values():
        if container.parent() is None:
            form_config.addTab(container)

    for field_def in layer_def.get("fields", []):
        field_idx = fields.indexOf(field_def["name"])

        assert field_idx != -1

        if field_def.get("alias_expression"):
            prop = QgsProperty()
            prop.setExpressionString(field_def["alias_expression"])
            props = QgsPropertyCollection()
            props.setProperty(QgsEditFormConfig.DataDefinedProperty.Alias, prop)
            form_config.setDataDefinedFieldProperties(field_def["name"], props)

    return form_config


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


def create_fields(layer_def: VectorLayerDef) -> QgsFields:
    fields = QgsFields()

    for field_def in layer_def["fields"]:
        field = create_field(field_def)
        fields.append(field)

    return fields


def set_layer_fields(layer: QgsVectorLayer, layer_def: VectorLayerDef) -> None:
    fields = layer.fields()

    # For geopackage layers, hide the 'fid' field by default
    if layer_def["datasource_format"] == VectorLayerDataprovider.GPKG:
        field_idx = fields.indexOf("fid")

        assert field_idx != -1

        widget_setup = QgsEditorWidgetSetup("Hidden", {})
        layer.setEditorWidgetSetup(field_idx, widget_setup)

    for field_def in layer_def.get("fields", []):
        field_name = field_def["name"]
        field_idx = fields.indexOf(field_name)

        if field_idx == -1:
            logger.warning(
                f"Field '{field_name}' not found in layer '{layer_def['name']}'. Skipping field configuration."
            )

            continue

        field = fields[field_def["name"]]

        if field_def.get("alias"):
            field.setAlias(field_def["alias"])

        if field_def.get("is_read_only", False):
            field.setReadOnly(True)

        set_field_constraints(field, field_def)
        set_field_default_value(field, field_def)
        set_field_widget(field, field_def)

        layer.setFieldAlias(field_idx, field.alias())
        layer.setDefaultValueDefinition(field_idx, field.defaultValueDefinition())
        layer.setEditorWidgetSetup(field_idx, field.editorWidgetSetup())

        constraints = field.constraints()
        for constraint_type in (
            QgsFieldConstraints.Constraint.ConstraintNotNull,
            QgsFieldConstraints.Constraint.ConstraintUnique,
            QgsFieldConstraints.Constraint.ConstraintExpression,
        ):
            if not (constraints.constraints() & constraint_type):  # type: ignore
                continue

            layer.setFieldConstraint(
                field_idx,
                constraint_type,
                constraints.constraintStrength(constraint_type),
            )

            if constraint_type == QgsFieldConstraints.Constraint.ConstraintExpression:
                layer.setConstraintExpression(
                    field_idx,
                    constraints.constraintExpression(),
                    constraints.constraintDescription(),
                )


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
        wc.update(wc)
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
        wc.update(wc)
    elif widget_type == "ValueMap":
        wc.update(
            {
                "map": wc.get("map", {}),
            }
        )
    elif widget_type == "ValueRelation":
        wc.update(wc)
    else:
        raise NotImplementedError(f"Unsupported widget type: {widget_type}")

    widget_setup = QgsEditorWidgetSetup(widget_type, wc)
    field.setEditorWidgetSetup(widget_setup)


def set_layer_tree(project: QgsProject, project_def: ProjectDef) -> None:
    tree_root = project.layerTreeRoot()

    assert tree_root, "Failed to get layer tree root. Very unlikely error."

    tree_root.clear()

    layer_tree_items_mapping: dict[str, QgsLayerTreeGroup | QgsLayerTreeLayer] = {}

    for layer_tree_def in project_def["layer_tree"]:
        item_type = layer_tree_def["type"]
        item_name = layer_tree_def["name"]
        parent_name = layer_tree_def["parent_id"]
        is_checked = layer_tree_def["is_checked"]

        if parent_name:
            parent = layer_tree_items_mapping[parent_name]

            if not parent:
                raise MissingParentError(
                    f"Parent group '{parent_name}' not found for layer tree item '{item_name}'"
                )

            assert isinstance(parent, QgsLayerTreeGroup)
        else:
            parent = tree_root

        if item_type == "group":
            tree_item = QgsLayerTreeGroup(item_name, is_checked)

            tree_item.setIsMutuallyExclusive(
                layer_tree_def.get("is_mutually_exclusive", False),
                layer_tree_def.get("mutually_exclusive_child_index", -1),
            )
        elif item_type == "layer":
            layer = project.mapLayer(layer_tree_def["layer_id"])

            if not layer:
                raise Qgis2JsonError(
                    f"Layer '{item_name}' not found in project for layer tree item."
                )

            tree_item = QgsLayerTreeLayer(layer)

        else:
            raise NotImplementedError(f"Unsupported layer tree item type: {item_type}")

        tree_item.setItemVisibilityChecked(is_checked)

        layer_tree_items_mapping[layer_tree_def["item_id"]] = tree_item

        parent_children_count = len(parent.children())
        parent.insertChildNode(parent_children_count, tree_item)


def get_relation_strength(strength_name: RelationStrength) -> Qgis.RelationshipStrength:
    strengths = {
        "association": Qgis.RelationshipStrength.Association,
        "composition": Qgis.RelationshipStrength.Composition,
    }

    if strength_name not in strengths:
        raise NotImplementedError(f"Unknown relation strength: {strength_name}")

    return strengths[strength_name]


def create_relation(relation_def: RelationDef) -> QgsRelation:
    relation = QgsRelation()
    relation.setId(relation_def["relation_id"])
    relation.setName(relation_def["name"])
    relation.setReferencingLayer(relation_def["from_layer_id"])
    relation.setReferencedLayer(relation_def["to_layer_id"])
    relation.setStrength(get_relation_strength(relation_def["strength"]))

    for field_pair_def in relation_def["field_pairs"]:
        relation.addFieldPair(
            field_pair_def["from_field"],
            field_pair_def["to_field"],
        )

    return relation


def create_polymorphic_relation(
    relation_def: PolymorphicRelationDef,
) -> QgsPolymorphicRelation:
    relation = QgsPolymorphicRelation()

    relation.setId(relation_def["relation_id"])
    relation.setName(relation_def["name"])
    relation.setReferencingLayer(relation_def["from_layer_id"])
    relation.setReferencedLayerField(relation_def["to_layer_field"])
    relation.setReferencedLayerExpression(relation_def["to_layer_expression"])
    relation.setReferencedLayerIds(relation_def["to_layer_ids"])
    relation.setRelationStrength(get_relation_strength(relation_def["strength"]))

    for field_pair_def in relation_def["field_pairs"]:
        relation.addFieldPair(
            field_pair_def["from_field"],
            field_pair_def["to_field"],
        )

    return relation
