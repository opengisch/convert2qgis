import logging
import json
from pathlib import Path
from typing import Any, Callable, cast
import fastjsonschema


from json2qgis.types import LayerDef, LayerType, ProjectDef, VectorLayerDataprovider
from json2qgis.errors import (
    Qgis2JsonError,
    UnknownCrsSystem,
    MissingParentError,
    UnknownVectorLayerDataproviderError,
)
from json2qgis.utils import (
    normalize_name,
    create_fields,
    get_layer_flags,
    get_layer_edit_form,
    set_layer_fields,
)


from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsMapLayer,
    QgsCoordinateReferenceSystem,
    QgsVectorFileWriter,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
)

logger = logging.getLogger(__name__)


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

    def build(self, destination: str) -> None:
        self._create_project(destination)

    def _create_project(self, output_destination: str) -> None:
        for layer in self.definition["layers"]:
            self._create_layer(layer)

        self._create_layer_tree()

        metadata = self._project.metadata()
        metadata.setAuthor(self.definition.get("author", ""))

        self._project.setTitle(self.definition.get("title", ""))
        self._project.setMetadata(metadata)

        self._project.write(output_destination)

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
        layer.setFlags(get_layer_flags(layer.flags(), layer_def))

        self._project.addMapLayer(layer, False)

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

        set_layer_fields(new_layer, layer_def)

        new_layer.setEditFormConfig(
            get_layer_edit_form(
                new_layer.fields(),
                layer_def,
                new_layer.editFormConfig(),
            ),
        )
        new_layer.setReadOnly(
            layer_def.get("is_read_only", False),
        )

        return new_layer

    def _set_fields(self, layer: QgsVectorLayer, layer_def: LayerDef) -> None:
        layer_data_provider = layer.dataProvider()

        if layer_data_provider is None:
            raise UnknownVectorLayerDataproviderError(
                f"Failed to get data provider for layer: {layer_def['name']}"
            )

        fields = create_fields(layer_def)

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
