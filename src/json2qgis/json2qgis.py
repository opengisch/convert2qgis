import logging
import json
from pathlib import Path
from typing import Any, Callable, cast
import fastjsonschema


from json2qgis.types import LayerDef, LayerType, ProjectDef, VectorLayerDataprovider
from json2qgis.errors import (
    Qgis2JsonError,
    UnknownCrsSystem,
    UnknownVectorLayerDataproviderError,
)
from json2qgis.utils import (
    create_relation,
    normalize_name,
    create_fields,
    get_layer_flags,
    get_layer_edit_form,
    set_layer_fields,
    set_layer_tree,
)


from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsMapLayer,
    QgsCoordinateReferenceSystem,
    QgsVectorFileWriter,
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

        set_layer_tree(self._project, self.definition)

        metadata = self._project.metadata()
        metadata.setAuthor(self.definition.get("author", ""))

        self._project.setTitle(self.definition.get("title", ""))
        self._project.setMetadata(metadata)

        self._project.write(output_destination)

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

    def _set_relation(self):
        relation_manager = self._project.relationManager()

        assert relation_manager is not None

        for relation_def in self.definition.get("relations", []):
            relation = create_relation(relation_def)
            relation_manager.addRelation(relation)

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
