import functools
import json
import logging
import unicodedata
from collections.abc import Callable
from importlib.resources import files
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

from convert2qgis.json2qgis.errors import MissingParentError, Qgis2JsonError
from convert2qgis.json2qgis.type_defs import (
    DatasetDef,
    FieldDef,
    LegendTreeGroupDef,
    LegendTreeItemDef,
    LegendTreeLayerDef,
    PolymorphicRelationDef,
    ProjectDef,
    RelationDef,
    RelationStrength,
    VectorDatasetDef,
    VectorLayerDataprovider,
    dataset_from_data,
)

try:
    import fastjsonschema
    from fastjsonschema.ref_resolver import resolve_path
except ModuleNotFoundError:
    fastjsonschema = None

    resolve_path = None

try:
    import unidecode
except ModuleNotFoundError:
    unidecode = None  # type: ignore

try:
    import markdown
except ModuleNotFoundError:
    markdown = None  # type: ignore

logger = logging.getLogger(__name__)


_VALIDATORS_BY_PATH: dict[str, Callable[[dict[str, Any]], None]] = {}


def get_schema_json() -> dict[str, Any]:
    data_path = files("convert2qgis.json2qgis").joinpath("schema/schema_20251121.json")
    schema_json = data_path.read_text()

    return json.loads(schema_json)


def get_schema_validator() -> Callable[[dict[str, Any]], None]:
    schema = get_schema_json()

    if fastjsonschema:
        return fastjsonschema.compile(schema)  # type: ignore
    else:
        return lambda data: None  # type: ignore


def check_output(path: str):
    """Decorator to quickly do a sanity check if the output of a given function is a valid JSON schema."""
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


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def normalize_name(name: str) -> str:
    """Transliterates any string (including Cyrillic or non-ASCII characters) to ASCII."""
    if unidecode:
        name = unidecode.unidecode(name)
    else:
        name = strip_accents(name)

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
        raise NotImplementedError(f"Unsupported attribute container item type: {type_name}")

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


def get_layer_flags(flags: QgsMapLayer.LayerFlags, dataset_def: DatasetDef | dict[str, Any]) -> QgsMapLayer.LayerFlags:
    dataset_def = dataset_from_data(dataset_def)

    if dataset_def.is_identifiable:
        flags |= QgsMapLayer.LayerFlag.Identifiable
    else:
        flags &= ~QgsMapLayer.LayerFlag.Identifiable  # type: ignore

    if dataset_def.is_removable:
        flags |= QgsMapLayer.LayerFlag.Removable
    else:
        flags &= ~QgsMapLayer.LayerFlag.Removable  # type: ignore

    if dataset_def.is_searchable:
        flags |= QgsMapLayer.LayerFlag.Searchable
    else:
        flags &= ~QgsMapLayer.LayerFlag.Searchable  # type: ignore

    if dataset_def.is_private:
        flags |= QgsMapLayer.LayerFlag.Private
    else:
        flags &= ~QgsMapLayer.LayerFlag.Private  # type: ignore

    return flags


def get_layer_edit_form(  # noqa: C901
    fields: QgsFields,
    dataset_def: VectorDatasetDef | dict[str, Any],
    form_config: QgsEditFormConfig | None = None,
) -> QgsEditFormConfig:
    dataset_def = VectorDatasetDef.from_data(dataset_def)

    if form_config is None:
        form_config = QgsEditFormConfig()

    form_config.setLayout(Qgis.AttributeFormLayout.DragAndDrop)
    form_config.clearTabs()

    containers_mapping: dict[str, QgsAttributeEditorContainer] = {}

    for form_item_def in dataset_def.form_config:
        item_type = form_item_def.type
        item_label = form_item_def.label
        item_parent_id = form_item_def.parent_id

        parent = None
        if item_parent_id:
            parent = containers_mapping.get(item_parent_id)

            if not parent:
                raise MissingParentError(f"Parent with ID '{item_parent_id}' not found for form item '{item_label}'")
        else:
            parent = form_config.invisibleRootContainer()

        if item_type == "field":
            assert form_item_def.field_name is not None
            field_idx = fields.indexOf(form_item_def.field_name)

            assert field_idx != -1, f"Could not find field {form_item_def.field_name}"

            if form_item_def.visibility_expression:
                parent_container = QgsAttributeEditorContainer("~CONDITIONAL~", parent)
                parent_container.setVisibilityExpression(
                    QgsOptionalExpression(QgsExpression(form_item_def.visibility_expression))
                )
                parent_container.setShowLabel(False)
                container = QgsAttributeEditorField(
                    form_item_def.field_name,
                    fields.indexOf(form_item_def.field_name),
                    parent_container,
                )

                parent_container.addChildElement(container)

                if parent:
                    parent.addChildElement(parent_container)
            else:
                container = QgsAttributeEditorField(
                    form_item_def.field_name,
                    fields.indexOf(form_item_def.field_name),
                    parent,
                )

                if parent:
                    parent.addChildElement(container)

            if form_item_def.is_read_only:
                form_config.setReadOnly(field_idx, True)

            if form_item_def.is_label_on_top:
                form_config.setLabelOnTop(field_idx, True)

            container.setShowLabel(form_item_def.show_label)

            continue

        elif item_type == "relation":
            assert form_item_def.field_name is not None
            if form_item_def.visibility_expression:
                parent_container = QgsAttributeEditorContainer("", parent)
                parent_container.setVisibilityExpression(
                    QgsOptionalExpression(QgsExpression(form_item_def.visibility_expression))
                )
                container = QgsAttributeEditorRelation(
                    form_item_def.field_name,
                    form_item_def.item_id,
                    parent_container,
                )

                parent_container.addChildElement(container)

                if parent:
                    parent.addChildElement(parent_container)
            else:
                container = QgsAttributeEditorRelation(
                    form_item_def.field_name,
                    form_item_def.item_id,
                    parent,
                )

                if parent:
                    parent.addChildElement(container)

            continue

        elif item_type == "text":
            if form_item_def.is_markdown:
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

        if form_item_def.visibility_expression:
            container.setVisibilityExpression(QgsOptionalExpression(QgsExpression(form_item_def.visibility_expression)))

        if form_item_def.background_color:
            container.setBackgroundColor(QColor(form_item_def.background_color))

        container.setCollapsed(form_item_def.is_collapsed)
        container.setColumnCount(form_item_def.column_count)

        if parent:
            parent.addChildElement(container)

        containers_mapping[form_item_def.item_id] = container

    for container in containers_mapping.values():
        if container.parent() is None:
            form_config.addTab(container)

    for field_def in dataset_def.fields:
        field_idx = fields.indexOf(field_def.name)

        assert field_idx != -1

        if field_def.alias_expression:
            prop = QgsProperty()
            prop.setExpressionString(field_def.alias_expression)
            props = QgsPropertyCollection()
            props.setProperty(QgsEditFormConfig.DataDefinedProperty.Alias, prop)
            form_config.setDataDefinedFieldProperties(field_def.name, props)

    return form_config


def create_field(field_def: FieldDef | dict[str, Any]) -> QgsField:
    field_def = FieldDef.from_data(field_def)

    # Map FieldDef type to Qt QMetaType type IDs
    qt_type = get_field_type(field_def.type)

    field = QgsField(
        field_def.name,
        qt_type,
        len=field_def.length,
        prec=field_def.precision,
        comment=field_def.comment,
    )

    return field


def create_fields(dataset_def: VectorDatasetDef | dict[str, Any]) -> QgsFields:
    dataset_def = VectorDatasetDef.from_data(dataset_def)

    fields = QgsFields()

    for field_def in dataset_def.fields:
        field = create_field(field_def)
        fields.append(field)

    return fields


def set_layer_fields(layer: QgsVectorLayer, dataset_def: VectorDatasetDef | dict[str, Any]) -> None:
    dataset_def = VectorDatasetDef.from_data(dataset_def)

    fields = layer.fields()

    # For geopackage layers, hide the 'fid' field by default
    if dataset_def.datasource_format == VectorLayerDataprovider.GPKG:
        field_idx = fields.indexOf("fid")

        assert field_idx != -1

        widget_setup = QgsEditorWidgetSetup("Hidden", {})
        layer.setEditorWidgetSetup(field_idx, widget_setup)

    for field_def in dataset_def.fields:
        field_name = field_def.name
        field_idx = fields.indexOf(field_name)

        if field_idx == -1:
            logger.warning(
                f"Field '{field_name}' not found in layer '{dataset_def.name}'. Skipping field configuration."
            )

            continue

        field = fields[field_def.name]

        if field_def.alias:
            field.setAlias(field_def.alias)

        if field_def.is_read_only:
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


def set_field_default_value(field: QgsField, field_def: FieldDef | dict[str, Any]) -> None:
    field_def = FieldDef.from_data(field_def)

    if field_def.default_value is None:
        return

    default_value = QgsDefaultValue(
        field_def.default_value,
        field_def.set_default_value_on_update,
    )
    field.setDefaultValueDefinition(default_value)


def set_field_constraints(field: QgsField, field_def: FieldDef | dict[str, Any]) -> None:
    field_def = FieldDef.from_data(field_def)

    constraints = field.constraints()

    if field_def.is_not_null:
        is_not_null_strength = get_constraint_strength(field_def.is_not_null_strength)

        constraints.setConstraint(
            QgsFieldConstraints.Constraint.ConstraintNotNull,
            QgsFieldConstraints.ConstraintOrigin.ConstraintOriginLayer,
        )
        constraints.setConstraintStrength(
            QgsFieldConstraints.Constraint.ConstraintNotNull,
            is_not_null_strength,
        )

    if field_def.is_unique:
        is_unique_strength = get_constraint_strength(field_def.is_unique_strength)

        constraints.setConstraint(
            QgsFieldConstraints.Constraint.ConstraintUnique,
            QgsFieldConstraints.ConstraintOrigin.ConstraintOriginLayer,
        )
        constraints.setConstraintStrength(
            QgsFieldConstraints.Constraint.ConstraintUnique,
            is_unique_strength,
        )

    if field_def.constraint_expression:
        constraint_expression = field_def.constraint_expression
        constraint_description = field_def.constraint_expression_description
        constraint_expression_strength = get_constraint_strength(field_def.constraint_expression_strength)

        constraints.setConstraint(
            QgsFieldConstraints.Constraint.ConstraintExpression,
            QgsFieldConstraints.ConstraintOrigin.ConstraintOriginLayer,
        )
        constraints.setConstraintStrength(
            QgsFieldConstraints.Constraint.ConstraintExpression,
            constraint_expression_strength,
        )
        constraints.setConstraintExpression(constraint_expression, constraint_description)

    field.setConstraints(constraints)


def set_field_widget(field: QgsField, field_def: FieldDef | dict[str, Any]) -> None:
    field_def = FieldDef.from_data(field_def)

    widget_type = field_def.widget_type
    # Widget configuration
    wc = dict(field_def.widget_config)

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


def set_layer_tree(project: QgsProject, project_def: ProjectDef | dict[str, Any]) -> None:
    project_def = ProjectDef.from_data(project_def)

    tree_root = project.layerTreeRoot()

    assert tree_root, "Failed to get layer tree root. Very unlikely error."

    tree_root.clear()

    def insert_legend_node(
        parent: QgsLayerTreeGroup,
        legend_item_def: LegendTreeItemDef,
    ) -> None:
        if legend_item_def.legend_item_type == "group":
            assert isinstance(legend_item_def, LegendTreeGroupDef)

            tree_item = QgsLayerTreeGroup(legend_item_def.name, legend_item_def.is_checked)
            tree_item.setIsMutuallyExclusive(
                legend_item_def.is_mutually_exclusive,
                legend_item_def.mutually_exclusive_child_index,
            )
            tree_item.setItemVisibilityChecked(legend_item_def.is_checked)
            parent.insertChildNode(len(parent.children()), tree_item)

            for child_item_def in legend_item_def.children:
                insert_legend_node(tree_item, child_item_def)

            return

        assert isinstance(legend_item_def, LegendTreeLayerDef)

        layer = project.mapLayer(legend_item_def.layer_id)

        if not layer:
            raise Qgis2JsonError(f"Layer '{legend_item_def.name}' not found in project for legend tree item.")

        tree_item = QgsLayerTreeLayer(layer)
        tree_item.setItemVisibilityChecked(legend_item_def.is_checked)
        parent.insertChildNode(len(parent.children()), tree_item)

    for child_item_def in project_def.legend_tree.children:
        insert_legend_node(tree_root, child_item_def)


def get_relation_strength(strength_name: RelationStrength) -> Qgis.RelationshipStrength:
    strengths = {
        "association": Qgis.RelationshipStrength.Association,
        "composition": Qgis.RelationshipStrength.Composition,
    }

    if strength_name not in strengths:
        raise NotImplementedError(f"Unknown relation strength: {strength_name}")

    return strengths[strength_name]


def create_relation(relation_def: RelationDef | dict[str, Any]) -> QgsRelation:
    relation_def = RelationDef.from_data(relation_def)

    relation = QgsRelation()
    relation.setId(relation_def.relation_id)
    relation.setName(relation_def.name)
    relation.setReferencingLayer(relation_def.from_layer_id)
    relation.setReferencedLayer(relation_def.to_layer_id)
    relation.setStrength(get_relation_strength(relation_def.strength))

    for field_pair_def in relation_def.field_pairs:
        relation.addFieldPair(
            field_pair_def.from_field,
            field_pair_def.to_field,
        )

    return relation


def create_polymorphic_relation(
    relation_def: PolymorphicRelationDef | dict[str, Any],
) -> QgsPolymorphicRelation:
    relation_def = PolymorphicRelationDef.from_data(relation_def)

    relation = QgsPolymorphicRelation()

    relation.setId(relation_def.relation_id)
    relation.setName(relation_def.name)
    relation.setReferencingLayer(relation_def.from_layer_id)
    relation.setReferencedLayerField(relation_def.to_layer_field)
    relation.setReferencedLayerExpression(relation_def.to_layer_expression)
    relation.setReferencedLayerIds(relation_def.to_layer_ids)
    relation.setRelationStrength(get_relation_strength(relation_def.strength))

    for field_pair_def in relation_def.field_pairs:
        relation.addFieldPair(
            field_pair_def.from_field,
            field_pair_def.to_field,
        )

    return relation
