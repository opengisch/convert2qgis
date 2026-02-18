import logging
import os
from pathlib import Path
from typing import Any, cast

import fastjsonschema
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsMapLayer,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

from json2qgis.errors import (
    Qgis2JsonError,
    UnknownCrsSystem,
    UnknownVectorLayerDataproviderError,
)
from json2qgis.type_defs import LayerDef, ProjectDef, VectorLayerDataprovider
from json2qgis.utils import (
    create_fields,
    create_relation,
    get_layer_edit_form,
    get_layer_flags,
    get_schema_validator,
    normalize_name,
    set_layer_fields,
    set_layer_tree,
)

logger = logging.getLogger(__name__)


schema_validator = get_schema_validator()


class ProjectCreator:
    _project: QgsProject

    def __init__(self, definition: ProjectDef) -> None:
        try:
            schema_validator(cast(dict[str, Any], definition))
        except fastjsonschema.JsonSchemaException as e:
            raise Qgis2JsonError(f'{e} with data "{getattr(e, "value", None)}"')

        project = QgsProject().instance()

        assert project, "Failed to get `QgsProject` instance. Very unlikely error."

        self._project = project
        self.definition = definition

    def build(self, output_dir: str) -> None:
        self._output_dir = Path(output_dir)

        self._output_dir.mkdir(parents=True, exist_ok=True)

        if self._output_dir.is_file():
            raise Qgis2JsonError(f"Output directory is a file: {self._output_dir}")

        # TODO: ugly hack as hell, otherwise the `QgsVectorFileWriter` writes wrong paths
        os.chdir(self._output_dir)

        self._create_project()

    def _create_project(self) -> None:
        for layer_def in self.definition["layers"]:
            self._create_layer(layer_def)

        set_layer_tree(self._project, self.definition)

        self._set_relations()

        for layer_def in self.definition["layers"]:
            if layer_def["layer_type"] != "vector":
                continue

            layer = self._project.mapLayer(layer_def["layer_id"])

            assert layer
            assert isinstance(layer, QgsVectorLayer)

            layer.setEditFormConfig(
                get_layer_edit_form(
                    layer.fields(),
                    layer_def,
                    layer.editFormConfig(),
                ),
            )

        metadata = self._project.metadata()
        metadata.setAuthor(self.definition.get("author", ""))

        self._project.setTitle(self.definition.get("title", ""))
        self._project.setMetadata(metadata)

        project_filename = "project.qgs"
        if not self._project.write(str(project_filename)):
            logger.error(f"Failed to write project to {project_filename}")

    def _create_layer(self, layer_def: LayerDef) -> None:
        layer_type = layer_def["layer_type"]
        if layer_type == "vector":
            layer = self._create_vector_layer(layer_def)
        elif layer_type == "raster":
            layer = self._create_raster_layer(layer_def)
        # Additional layer types can be handled here
        elif layer_type == "mesh":
            layer = self._create_mesh_layer(layer_def)
        elif layer_type == "vector_tile":
            layer = self._create_vector_tile_layer(layer_def)
        elif layer_type == "point_cloud":
            layer = self._create_point_cloud_layer(layer_def)
        else:
            raise NotImplementedError(f"Unsupported layer type: {layer_type}")

        try:
            crs = QgsCoordinateReferenceSystem(layer_def["crs"])
        except Exception as e:
            raise UnknownCrsSystem(f"Failed to create CRS: {e}")

        if not crs.isValid():
            raise UnknownCrsSystem(f"Invalid CRS: {layer_def['crs']}")

        if not layer.setId(layer_def["layer_id"]):
            raise Qgis2JsonError(f"Failed to set layer ID: {layer_def['layer_id']}")

        layer.setCrs(crs)
        layer.setFlags(get_layer_flags(layer.flags(), layer_def))

        self._project.addMapLayer(layer, False)

    def _get_geometry_type(self, geometry_type: str) -> str:
        geometry_type_set = {"Point", "LineString", "Polygon", "NoGeometry"}

        if geometry_type not in geometry_type_set:
            raise NotImplementedError(f"Unsupported geometry type: {geometry_type}")

        return geometry_type

    def _create_vector_layer(self, layer_def: LayerDef) -> QgsVectorLayer:
        geometry_type = self._get_geometry_type(layer_def["geometry_type"])
        source = f"{geometry_type}?crs={layer_def['crs']}"

        layer = QgsVectorLayer(source, layer_def["name"], "memory")

        if not layer.isValid():
            raise Qgis2JsonError(f"Vector layer invalid: {layer_def['name']}")

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

        # TODO @suricactus: consider switching to `QgsVectorFileWriter.create()`
        write_result, error_message, new_file, _new_layer = (
            QgsVectorFileWriter.writeAsVectorFormatV3(
                layer,
                file_name,
                self._project.transformContext(),
                options,
            )
        )

        if write_result != QgsVectorFileWriter.WriterError.NoError:
            raise Qgis2JsonError(
                f"Error writing vector layer: {write_result} {error_message}"
            )

        new_layer = QgsVectorLayer(new_file, layer_def["name"], layer_provider_lib)

        set_layer_fields(new_layer, layer_def)

        if layer_def.get("data"):
            self._add_vector_layer_data(new_layer, layer_def)

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

    def _add_vector_layer_data(
        self, layer: QgsVectorLayer, layer_def: LayerDef
    ) -> None:
        layer.startEditing()
        layer_data_provider = layer.dataProvider()

        if not bool(layer_data_provider) or not layer_data_provider.isValid():
            raise UnknownVectorLayerDataproviderError(
                f"Failed to get data provider for layer 1: {layer_def['name']}"
            )

        if layer.geometryType() != Qgis.GeometryType.Null:
            raise NotImplementedError(
                f"Cannot edit geometry layer: {layer_def['name']} has geometry {layer.geometryType()}"
            )

        features = []
        for feature_def in layer_def.get("data", []):
            feature = QgsFeature(layer.fields())

            for field_name, value in feature_def.items():
                feature.setAttribute(field_name, value)

            features.append(feature)

        layer_data_provider.addFeatures(features)
        layer.updateExtents()
        layer.commitChanges()

    def _set_relations(self):
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
