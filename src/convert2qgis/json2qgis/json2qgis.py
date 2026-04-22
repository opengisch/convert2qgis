import logging
import os
from pathlib import Path
from typing import Any

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsMapLayer,
    QgsMapSettings,
    QgsPointXY,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
    QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtXml import QDomDocument

from convert2qgis.json2qgis.errors import (
    Qgis2JsonError,
    UnknownCrsSystem,
    UnknownVectorLayerDataproviderError,
)
from convert2qgis.json2qgis.type_defs import (
    DatasetDef,
    PathOrStr,
    ProjectDef,
    RasterDatasetDef,
    VectorDatasetDef,
    VectorLayerDataprovider,
)
from convert2qgis.json2qgis.utils import (
    create_fields,
    create_relation,
    get_layer_edit_form,
    get_layer_flags,
    get_schema_validator,
    normalize_name,
    set_layer_fields,
    set_layer_tree,
    set_project_custom_properties,
)

try:
    import fastjsonschema
except ModuleNotFoundError:
    fastjsonschema = None

logger = logging.getLogger(__name__)


schema_validator = get_schema_validator()


class ProjectCreator:
    _project: QgsProject
    _output_dir: Path

    _has_geometry: bool = False
    """Whether any of the project vector layers has a geometry type."""

    def __init__(self, definition: ProjectDef | dict[str, Any]) -> None:
        normalized_definition = ProjectDef.from_data(definition)

        # validate the project definition against the JSON schema if a schema validator is available
        if fastjsonschema:
            try:
                schema_validator(normalized_definition.to_dict())
            except fastjsonschema.JsonSchemaException as err:
                raise Qgis2JsonError(f'{err} with data "{getattr(err, "value", None)}"') from err

        self._project = QgsProject()
        self.definition = normalized_definition
        self._output_dir = Path()

    def build(self, output_dir: PathOrStr) -> QgsProject:
        self._output_dir = Path(output_dir)

        self._output_dir.mkdir(parents=True, exist_ok=True)

        if self._output_dir.is_file():
            raise Qgis2JsonError(f"Output directory is a file: {self._output_dir}")

        # TODO: ugly hack as hell, otherwise the `QgsVectorFileWriter` writes wrong paths
        os.chdir(self._output_dir)

        return self._create_project()

    def _create_project(self) -> QgsProject:
        for dataset_def in self.definition.all_datasets:
            self._create_layer(dataset_def)

        set_layer_tree(self._project, self.definition)

        self._project.setCrs(self._get_project_crs())

        self._set_relations()

        for dataset_def in self.definition.all_datasets:
            if dataset_def.layer_type != "vector":
                continue

            assert isinstance(dataset_def, VectorDatasetDef)
            layer = self._project.mapLayer(dataset_def.layer_id)

            assert layer
            assert isinstance(layer, QgsVectorLayer)

            layer.setEditFormConfig(
                get_layer_edit_form(
                    layer.fields(),
                    dataset_def,
                    layer.editFormConfig(),
                ),
            )

        project_title = self.definition.project.title or "xlsform_project"

        metadata = self._project.metadata()
        metadata.setAuthor(self.definition.project.author)

        if self._project.crs().authid() == "EPSG:3857":
            display_settings = self._project.displaySettings()

            assert display_settings

            # Display coordinates in WGS84 to provide a more useful experience for the average person
            display_settings.setCoordinateType(Qgis.CoordinateDisplayType.CustomCrs)
            display_settings.setCoordinateCustomCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

        self._project.setTitle(project_title)
        self._project.setMetadata(metadata)

        if self.definition.project.custom_properties:
            logger.info("Set project custom properties...")

            set_project_custom_properties(self._project, self.definition.project.custom_properties)

        # NOTE: Connect to the `writeProject` signal to set the project extent before the project is written to disk.
        self._project.writeProject.connect(self._process_project_write)

        project_filename = f"{normalize_name(project_title)}.qgs"
        if not self._project.write(str(project_filename)):
            logger.error(f'Failed to write project to "{project_filename}": {self._project.error()}')

        return self._project

    def _get_project_crs(self) -> QgsCoordinateReferenceSystem:
        crs = QgsCoordinateReferenceSystem(self.definition.project.crs)
        if not crs.isValid():
            crs = QgsCoordinateReferenceSystem("EPSG:3857")

        return crs

    def _process_project_write(self, document: QDomDocument) -> None:
        nl = document.elementsByTagName("qgis")

        if nl.count() == 0:
            logger.warning("Failed to find qgis node, skip saving project extent and CRS!")

            return

        qgis_node = nl.item(0)

        map_canvas_node = document.createElement("mapcanvas")
        map_canvas_node.setAttribute("name", "theMapCanvas")
        qgis_node.appendChild(map_canvas_node)

        map_settings = QgsMapSettings()
        map_settings.setDestinationCrs(self._get_project_crs())
        map_settings.setOutputSize(QSize(500, 500))

        extent_coords = self.definition.project.extent
        if extent_coords.strip():
            logger.info(f'Attempting to set project extent to "{extent_coords}"')

            try:
                coords = extent_coords.split(",")

                if len(coords) != 4:
                    raise ValueError(
                        f'Invalid number of coordinates: expected 4, got {len(coords)} in "{extent_coords}"'
                    )

                p1_x, p1_y, p2_x, p2_y = map(float, coords)

                extent = QgsRectangle(QgsPointXY(p1_x, p1_y), QgsPointXY(p2_x, p2_y))

                if extent.isEmpty() or not extent.isFinite():
                    raise Exception(f"Invalid WKT extent: {extent_coords}")

                map_settings.setExtent(extent)
            except Exception as err:
                logger.warning(f'Failed to set WKT extent "{extent_coords}": {err}')

        map_settings.writeXml(map_canvas_node, document)

    def _create_layer(self, dataset_def: DatasetDef) -> None:
        layer_type = dataset_def.layer_type
        if layer_type == "vector":
            assert isinstance(dataset_def, VectorDatasetDef)
            layer = self._create_vector_layer(dataset_def)

            if layer.geometryType() not in (
                Qgis.GeometryType.Unknown,
                Qgis.GeometryType.Null,
            ):
                self._has_geometry = True

        elif layer_type == "raster":
            assert isinstance(dataset_def, RasterDatasetDef)
            layer = self._create_raster_layer(dataset_def)
        # Additional layer types can be handled here
        elif layer_type == "mesh":
            layer = self._create_mesh_layer(dataset_def)
        elif layer_type == "vector_tile":
            layer = self._create_vector_tile_layer(dataset_def)
        elif layer_type == "point_cloud":
            layer = self._create_point_cloud_layer(dataset_def)
        else:
            raise NotImplementedError(f"Unsupported layer type: {layer_type}")

        try:
            crs = QgsCoordinateReferenceSystem(dataset_def.crs)
        except Exception as err:
            raise UnknownCrsSystem(f"Failed to create CRS: {err}") from err

        if not crs.isValid():
            raise UnknownCrsSystem(f"Invalid CRS: {dataset_def.crs}")

        if not layer.setId(dataset_def.layer_id):
            raise Qgis2JsonError(f"Failed to set layer ID: {dataset_def.layer_id}")

        layer.setCrs(crs)
        layer.setFlags(get_layer_flags(layer.flags(), dataset_def))

        self._project.addMapLayer(layer, False)

    def _get_geometry_type(self, geometry_type: str) -> str:
        geometry_type_set = {"Point", "LineString", "Polygon", "NoGeometry"}

        if geometry_type not in geometry_type_set:
            raise NotImplementedError(f"Unsupported geometry type: {geometry_type}")

        return geometry_type

    def _create_vector_layer(self, dataset_def: VectorDatasetDef) -> QgsVectorLayer:
        geometry_type = self._get_geometry_type(dataset_def.geometry_type)
        source = f"{geometry_type}?crs={dataset_def.crs}"

        layer = QgsVectorLayer(source, dataset_def.name, "memory")

        if not layer.isValid():
            raise Qgis2JsonError(f"Vector layer invalid: {dataset_def.name}")

        self._set_fields(layer, dataset_def)

        try:
            driver_name = VectorLayerDataprovider(dataset_def.datasource_format)
            layer_provider_lib = "ogr"
        except ValueError:
            raise UnknownVectorLayerDataproviderError(
                f"Unknown vector layer data provider: {dataset_def.datasource_format}"
            ) from None

        normalized_name = normalize_name(dataset_def.name)

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.layerName = normalized_name
        options.driverName = driver_name.value

        file_name = normalized_name + "." + driver_name.value.lower()

        # TODO @suricactus: consider switching to `QgsVectorFileWriter.create()`
        write_result, error_message, new_file, _new_layer = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer,
            file_name,
            self._project.transformContext(),
            options,
        )

        if write_result != QgsVectorFileWriter.WriterError.NoError:
            raise Qgis2JsonError(f"Error writing vector layer: {write_result} {error_message}")

        new_layer = QgsVectorLayer(new_file, dataset_def.name, layer_provider_lib)

        set_layer_fields(new_layer, dataset_def)

        if dataset_def.data:
            self._add_vector_layer_data(new_layer, dataset_def)

        new_layer.setReadOnly(
            dataset_def.is_read_only,
        )

        return new_layer

    def _set_fields(self, layer: QgsVectorLayer, dataset_def: VectorDatasetDef) -> None:
        layer_data_provider = layer.dataProvider()

        if layer_data_provider is None:
            raise UnknownVectorLayerDataproviderError(f"Failed to get data provider for layer: {dataset_def.name}")

        fields = create_fields(dataset_def)

        layer_data_provider.addAttributes(fields)
        layer.updateFields()

    def _add_vector_layer_data(self, layer: QgsVectorLayer, dataset_def: VectorDatasetDef) -> None:
        layer.startEditing()
        layer_data_provider = layer.dataProvider()

        if not bool(layer_data_provider) or not layer_data_provider.isValid():
            raise UnknownVectorLayerDataproviderError(f"Failed to get data provider for layer 1: {dataset_def.name}")

        if layer.geometryType() != Qgis.GeometryType.Null:
            raise NotImplementedError(
                f"Cannot edit geometry layer: {dataset_def.name} has geometry {layer.geometryType()}"
            )

        layer_data = dataset_def.data
        if not layer_data:
            logger.debug(f"No feature data to be added to layer {dataset_def.name}!")

            return

        features = []
        for feature_def in layer_data:
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

        for relation_def in self.definition.relations:
            relation = create_relation(relation_def)
            relation_manager.addRelation(relation)

    def _create_raster_layer(self, dataset: RasterDatasetDef) -> QgsMapLayer:
        # Implementation for creating a raster layer
        return QgsRasterLayer(
            dataset.datasource,
            dataset.name,
            dataset.datasource_format,
        )

    def _create_mesh_layer(self, dataset: DatasetDef) -> QgsMapLayer:
        # Implementation for creating a mesh layer
        raise NotImplementedError("Mesh layer creation not implemented yet.")

    def _create_vector_tile_layer(self, dataset: DatasetDef) -> QgsMapLayer:
        # Implementation for creating a vector tile layer
        raise NotImplementedError("Vector tile layer creation not implemented yet.")

    def _create_point_cloud_layer(self, dataset: DatasetDef) -> QgsMapLayer:
        # Implementation for creating a point cloud layer
        raise NotImplementedError("Point cloud layer creation not implemented yet.")
