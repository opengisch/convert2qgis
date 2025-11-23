import logging
import json
from pathlib import Path
import click
from enum import StrEnum
from typing import IO, Any, Callable, Literal, TypedDict, cast
import fastjsonschema


from .types import FieldDef
from .utils import (
    normalize_name,
    get_constraint_strength,
    get_attribute_form_container_type,
    create_field,
    set_field_default_value,
)


from qgis.PyQt.QtGui import QColor
from qgis.core import (
    Qgis,
    QgsProject,
    QgsField,
    QgsFields,
    QgsVectorLayer,
    QgsMapLayer,
    QgsCoordinateReferenceSystem,
    QgsVectorFileWriter,
    QgsFieldConstraints,
    QgsEditorWidgetSetup,
    QgsAttributeEditorField,
    QgsAttributeEditorContainer,
    QgsExpression,
    QgsOptionalExpression,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
)

logger = logging.getLogger(__name__)


class Qgis2JsonError(Exception): ...


class UnknownQgisTypeError(Qgis2JsonError): ...


class UnknownCrsSystem(Qgis2JsonError): ...


class MissingParentError(Qgis2JsonError): ...


class UnknownVectorLayerDataproviderError(Qgis2JsonError): ...


CrsDef = str


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


class FormConfigItemDef(TypedDict):
    id: str
    type: Literal["field", "group_box", "tab", "row"]
    name: str
    parent_id: str | None
    visibility_expression: str
    background_color: str
    is_collapsed: bool
    column_count: int


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


def get_schema() -> Callable[[dict[str, Any]], None]:
    schema_json = (
        Path(__file__).parent.joinpath("./schema/schema_20251121.json").read_text()
    )
    schema = json.loads(schema_json)
    schema_validator = fastjsonschema.compile(schema)

    return schema_validator  # type: ignore


schema_validator = get_schema()


class ProjectCreator:
    _project: QgsProject

    def __init__(self, definition: ProjectDef) -> None:
        schema_validator(cast(dict[str, Any], definition))
        project = QgsProject().instance()

        assert project, "Failed to get `QgsProject` instance. Very unlikely error."

        self._project = project
        self.definition = definition

    def build(self) -> None:
        self._create_project()

    def _create_project(self) -> None:
        for layer in self.definition["layers"]:
            self._create_layer(layer)

        self._create_layer_tree()

        metadata = self._project.metadata()
        metadata.setAuthor(self.definition.get("author", ""))

        self._project.setTitle(self.definition.get("title", ""))
        self._project.setMetadata(metadata)

        self._project.write("project.qgs")

    def _create_layer_tree(self) -> None:
        tree_root = self._project.layerTreeRoot()

        assert tree_root, "Failed to get layer tree root. Very unlikely error."

        tree_root.clear()

        layer_tree_items_mapping: dict[str, QgsLayerTreeGroup | QgsLayerTreeLayer] = {}

        for layer_tree_def in self.definition.get("layer_tree", {}).get("children", []):
            item_type = layer_tree_def["type"]
            item_name = layer_tree_def["name"]
            parent_name = layer_tree_def["parent"]
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
                layer = self._project.mapLayer(layer_tree_def["layer_id"])

                if not layer:
                    raise Qgis2JsonError(
                        f"Layer '{item_name}' not found in project for layer tree item."
                    )

                tree_item = QgsLayerTreeLayer(layer)

            else:
                raise NotImplementedError(
                    f"Unsupported layer tree item type: {item_type}"
                )

            tree_item.setItemVisibilityChecked(is_checked)

            layer_tree_items_mapping[layer_tree_def["id"]] = tree_item

            parent_children_count = len(parent.children())
            parent.insertChildNode(parent_children_count, tree_item)

    def _create_layer(self, layer_def: LayerDef) -> None:
        layer_type = layer_def["type"]
        if layer_type == LayerType.VECTOR:
            layer = self._create_vector_layer(layer_def)
        elif layer_type == LayerType.RASTER:
            layer = self._create_raster_layer(layer_def)
        # Additional layer types can be handled here
        elif layer_type == LayerType.MESH:
            layer = self._create_mesh_layer(layer_def)
        elif layer_type == LayerType.VECTOR_TILE:
            layer = self._create_vector_tile_layer(layer_def)
        elif layer_type == LayerType.POINT_CLOUD:
            layer = self._create_point_cloud_layer(layer_def)
        else:
            raise NotImplementedError(f"Unsupported layer type: {layer_type}")

        try:
            crs = QgsCoordinateReferenceSystem(layer_def["crs"])
        except Exception as e:
            raise UnknownCrsSystem(f"Failed to create CRS: {e}")

        layer.setCrs(crs)
        layer.setId(layer_def["layer_id"])

        self._set_layer_flags(layer, layer_def)

        self._project.addMapLayer(layer, False)

    def _set_layer_flags(self, layer: QgsMapLayer, layer_def: LayerDef) -> None:
        flags = layer.flags()

        if layer_def.get("is_identifiable", False):
            flags |= QgsMapLayer.LayerFlag.Identifiable

        if layer_def.get("is_removable", False):
            flags |= QgsMapLayer.LayerFlag.Removable

        if layer_def.get("is_searchable", False):
            flags |= QgsMapLayer.LayerFlag.Searchable

        if layer_def.get("is_private", False):
            flags |= QgsMapLayer.LayerFlag.Private

        layer.setFlags(flags)

    def _create_vector_layer(self, layer_def: LayerDef) -> QgsVectorLayer:
        geometry_type = layer_def["geometry_type"]
        layer = QgsVectorLayer(geometry_type, layer_def["name"], "memory")

        self._set_fields(layer, layer_def)

        try:
            driver_name = VectorLayerDataprovider(layer_def["datasource_format"])
            layer_provider_lib = "ogr"
        except ValueError:
            raise UnknownVectorLayerDataproviderError(
                f"Unknown vector layer data provider: {layer_def['datasource_format']}"
            )

        normalized_name = normalize_name(layer_def["name"])

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.layerName = normalized_name
        options.driverName = driver_name.value

        file_name = normalized_name + "." + driver_name.value.lower()

        write_result, error_message, new_file, _new_layer = (
            QgsVectorFileWriter.writeAsVectorFormatV3(
                layer,
                file_name,
                self._project.transformContext(),
                options,
            )
        )

        if write_result != QgsVectorFileWriter.WriterError.NoError:
            raise Qgis2JsonError(f"Error writing vector layer: {error_message}")

        new_layer = QgsVectorLayer(new_file, layer_def["name"], layer_provider_lib)

        self._set_field_configurations(new_layer, layer_def)
        self._set_layer_edit_form(new_layer, layer_def)

        new_layer.setReadOnly(layer_def.get("is_read_only", False))

        return new_layer

    def _set_field_configurations(
        self, layer: QgsVectorLayer, layer_def: LayerDef
    ) -> None:
        fields = layer.fields()

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

            self._set_field_constraints(field, field_def)
            set_field_default_value(field, field_def)
            self._set_field_widget(field, field_def)

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

                if (
                    constraint_type
                    == QgsFieldConstraints.Constraint.ConstraintExpression
                ):
                    layer.setConstraintExpression(
                        field_idx,
                        constraints.constraintExpression(),
                        constraints.constraintDescription(),
                    )

    def _set_field_widget(self, field: QgsField, field_def: FieldDef) -> None:
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

    def _set_field_constraints(self, field: QgsField, field_def: FieldDef) -> None:
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
            constraint_description = field_def.get(
                "constraint_expression_description", ""
            )
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

    def _set_layer_edit_form(self, layer: QgsVectorLayer, layer_def: LayerDef) -> None:
        fields = layer.fields()

        form_config = layer.editFormConfig()
        form_config.setLayout(Qgis.AttributeFormLayout.DragAndDrop)
        form_config.clearTabs()

        containers_mapping: dict[str, QgsAttributeEditorContainer] = {}

        for form_item_def in layer_def.get("form_config", {}).get("items", []):
            item_type = form_item_def["type"]
            item_name = form_item_def["name"]
            item_parent_id = form_item_def.get("parent_id")

            if item_parent_id:
                parent = containers_mapping.get(item_parent_id)

                if not parent:
                    raise MissingParentError(
                        f"Parent with ID '{item_parent_id}' not found for form item '{item_name}'"
                    )
            else:
                parent = None

            if item_type == "field":
                container = QgsAttributeEditorField(
                    item_name, fields.indexOf(item_name), parent
                )

                if parent:
                    parent.addChildElement(container)

                continue

            container = QgsAttributeEditorContainer(item_name, parent)
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

            containers_mapping[form_item_def["id"]] = container

        for container in containers_mapping.values():
            if container.parent() is None:
                form_config.addTab(container)

        layer.setEditFormConfig(form_config)

    def _set_fields(self, layer: QgsVectorLayer, layer_def: LayerDef) -> None:
        layer_data_provider = layer.dataProvider()
        fields = QgsFields()

        if layer_data_provider is None:
            raise UnknownVectorLayerDataproviderError(
                f"Failed to get data provider for layer: {layer_def['name']}"
            )

        for field_def in layer_def["fields"]:
            field = create_field(field_def)
            fields.append(field)

        layer_data_provider.addAttributes(fields)
        layer.updateFields()

    def _create_raster_layer(self, layer: LayerDef) -> QgsMapLayer:
        # Implementation for creating a raster layer
        raise NotImplementedError("Raster layer creation not implemented yet.")

    def _create_mesh_layer(self, layer: LayerDef) -> QgsMapLayer:
        # Implementation for creating a mesh layer
        raise NotImplementedError("Mesh layer creation not implemented yet.")

    def _create_vector_tile_layer(self, layer: LayerDef) -> QgsMapLayer:
        # Implementation for creating a vector tile layer
        raise NotImplementedError("Vector tile layer creation not implemented yet.")

    def _create_point_cloud_layer(self, layer: LayerDef) -> QgsMapLayer:
        # Implementation for creating a point cloud layer
        raise NotImplementedError("Point cloud layer creation not implemented yet.")


@click.command()
@click.option(
    "--json",
    "json_file",
    type=click.File("r"),
    help="Path to the JSON project definition file",
)
def main(json_file: IO) -> None:
    project_def = json.load(json_file)

    creator = ProjectCreator(project_def)
    creator.build()


if __name__ == "__main__":
    main()
