import logging
from pathlib import Path
from typing import Any

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsMapLayer,
    QgsMapSettings,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
    QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtXml import QDomDocument

from convert2qgis.json2qgis.errors import (
    InvalidExtentError,
    Qgis2JsonError,
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
    create_polymorphic_relation,
    create_relation,
    get_extent_or_defaults,
    get_layer_edit_form,
    get_layer_flags,
    get_schema_validator,
    normalize_name,
    parse_extent_str,
    set_layer_custom_properties,
    set_layer_fields,
    set_layer_tree,
    set_layer_virtual_fields,
    set_project_custom_properties,
    str_to_crs,
)

try:
    import fastjsonschema
except ModuleNotFoundError:
    fastjsonschema = None

logger = logging.getLogger(__name__)


schema_validator = get_schema_validator()


class ProjectCreator:
    definition: ProjectDef
    """The project definition as a normalized dataclass instance to create a QGIS project from."""

    _project: QgsProject
    """The QGIS project instance being created."""

    _output_dir: Path
    """Absolute path to the output directory where the project file and any associated files (e.g. GPKG files for vector layers) will be written."""

    _created_files: set[Path]
    """List of absolute file paths that have been created during the project creation process, used to avoid logging duplicate warnings when a file already exists."""

    _has_geometry: bool = False
    """Whether any of the project vector layers has a geometry type."""

    _consolidate_gpkgs: bool = True
    """Whether to consolidate all vector layers into a single GeoPackage file."""

    def __init__(self, definition: "ProjectDef | dict[str, Any]") -> None:
        # validate the project definition against the JSON schema if a schema validator is available
        if fastjsonschema:
            try:
                if isinstance(definition, ProjectDef):
                    schema_validator(definition.to_dict())
                else:
                    schema_validator(definition)
            except fastjsonschema.JsonSchemaException as err:
                raise Qgis2JsonError(
                    f'{err} with data "{getattr(err, "value", None)}"'
                ) from err

        normalized_definition = ProjectDef.from_data(definition)

        self._project = QgsProject()
        self.definition = normalized_definition
        self._output_dir = Path()
        self._created_files = set()

    def build(self, output_dir: PathOrStr) -> QgsProject:
        self._output_dir = Path(output_dir)

        if self._output_dir.is_file():
            raise Qgis2JsonError(f"Output directory is a file: {self._output_dir}")

        self._output_dir.mkdir(parents=True, exist_ok=True)

        return self._create_project()

    def _create_project(self) -> QgsProject:
        project_title = self._get_project_title()

        logger.info("Creating project with title: %s", project_title)
        logger.info("Creating %d layers...", len(self.definition.all_datasets))

        for dataset_def in self.definition.all_datasets:
            self._create_layer(dataset_def)

        logger.info("Set layer tree structure...")

        set_layer_tree(self._project, self.definition)

        logger.info("Set project CRS to %s", self._get_project_crs().authid())

        self._project.setCrs(self._get_project_crs())

        logger.info("Set project relations...")

        self._set_relations()

        logger.info("Set layer form configurations...")

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

        metadata = self._project.metadata()
        metadata.setAuthor(self.definition.project.author)

        if self._project.crs().authid() == "EPSG:3857":
            logger.debug(
                "Project CRS is EPSG:3857, set coordinate display to WGS84 for better user experience!"
            )

            display_settings = self._project.displaySettings()

            assert display_settings

            # Display coordinates in WGS84 to provide a more useful experience for the average person
            display_settings.setCoordinateType(Qgis.CoordinateDisplayType.CustomCrs)
            display_settings.setCoordinateCustomCrs(
                QgsCoordinateReferenceSystem("EPSG:4326")
            )

        logger.info("Set project properties...")

        self._project.setTitle(project_title)
        self._project.setMetadata(metadata)

        if self.definition.project.custom_properties:
            logger.info("Set project custom properties...")

            set_project_custom_properties(
                self._project, self.definition.project.custom_properties
            )

        # NOTE: Connect to the `writeProject` signal to set the project extent before the project is written to disk.
        self._project.writeProject.connect(self._process_project_write)

        project_filename = f"{self._output_dir}/{normalize_name(project_title)}.qgz"

        logger.info('Writing project to "%s"...', project_filename)

        if not self._project.write(str(project_filename)):
            logger.error(
                'Failed to write project to "%s": %s',
                project_filename,
                self._project.error(),
            )

        return self._project

    def _get_project_title(self) -> str:
        return self.definition.project.title or "xlsform_project"

    def _get_project_crs(self) -> QgsCoordinateReferenceSystem:
        return str_to_crs(self.definition.project.crs, "EPSG:3857")

    def _process_project_write(self, document: QDomDocument) -> None:
        nl = document.elementsByTagName("qgis")

        if nl.count() == 0:
            logger.warning(
                "Failed to find qgis node, skip saving project extent and CRS!"
            )

            return

        qgis_node = nl.item(0)

        map_canvas_node = document.createElement("mapcanvas")
        map_canvas_node.setAttribute("name", "theMapCanvas")
        qgis_node.appendChild(map_canvas_node)

        map_settings = QgsMapSettings()
        map_settings.setDestinationCrs(self._get_project_crs())
        map_settings.setOutputSize(QSize(500, 500))

        extent = QgsRectangle()

        extent_coords = self.definition.project.extent
        if extent_coords.strip():
            try:
                extent = parse_extent_str(extent_coords)
            except (ValueError, InvalidExtentError) as err:
                logger.warning("Failed to set WKT extent: %s", err)

        extent = get_extent_or_defaults(self._project, extent)

        logger.info("Setting project extent to: %s.", extent.toString())

        map_settings.setExtent(extent)

        map_settings.writeXml(map_canvas_node, document)

    def _create_layer(self, dataset_def: DatasetDef) -> None:
        layer_type = dataset_def.layer_type
        is_spatial = True
        if layer_type == "vector":
            assert isinstance(dataset_def, VectorDatasetDef)
            layer = self._create_vector_layer(dataset_def)

            if layer.geometryType() not in (
                Qgis.GeometryType.Unknown,
                Qgis.GeometryType.Null,
            ):
                self._has_geometry = True
            else:
                is_spatial = False

        elif layer_type == "raster":
            assert isinstance(dataset_def, RasterDatasetDef)
            layer = self._create_raster_layer(dataset_def)
        # Additional layer types can be handled here
        elif layer_type == "mesh":  # type: ignore[unreachable]
            layer = self._create_mesh_layer(dataset_def)
        elif layer_type == "vector_tile":
            layer = self._create_vector_tile_layer(dataset_def)
        elif layer_type == "point_cloud":
            layer = self._create_point_cloud_layer(dataset_def)
        else:
            raise NotImplementedError(f"Unsupported layer type: {layer_type}")

        if is_spatial:
            crs = str_to_crs(dataset_def.crs)
        else:
            crs = str_to_crs(dataset_def.crs, empty_crs_ok=True)

        logger.debug('Set layer CRS to "%s"...', crs.authid())

        layer.setCrs(crs)

        logger.debug('Set layer ID to "%s"...', dataset_def.layer_id)

        if not layer.setId(dataset_def.layer_id):
            raise Qgis2JsonError(f"Failed to set layer ID: {dataset_def.layer_id}")

        logger.debug("Set layer flags...")

        layer.setFlags(get_layer_flags(layer.flags(), dataset_def))

        if dataset_def.custom_properties:
            logger.debug('Set custom properties for layer "%s"...', dataset_def.name)

            set_layer_custom_properties(layer, dataset_def.custom_properties)

        self._project.addMapLayer(layer, False)

    def _get_geometry_type(self, geometry_type: str) -> str:
        geometry_type_set = {
            "Point",
            "LineString",
            "Polygon",
            "MultiPoint",
            "MultiLineString",
            "MultiPolygon",
            "NoGeometry",
        }

        if geometry_type not in geometry_type_set:
            raise NotImplementedError(f"Unsupported geometry type: {geometry_type}")

        return geometry_type

    def _create_vector_layer(self, dataset_def: VectorDatasetDef) -> QgsVectorLayer:
        geometry_type = self._get_geometry_type(dataset_def.geometry_type)
        source = f"{geometry_type}?crs={dataset_def.crs}"

        logger.info(
            'Creating vector layer "%s" with geometry type "%s"...',
            dataset_def.name,
            dataset_def.geometry_type,
        )

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

        driver_ext = driver_name.value.lower()

        if self._consolidate_gpkgs and driver_name == VectorLayerDataprovider.GPKG:
            base_name = f"{normalize_name(self._get_project_title())}.gpkg"
        else:
            base_name = normalized_name + "." + driver_ext

        abs_file_name = self._output_dir.joinpath(base_name)

        if abs_file_name.exists():
            if abs_file_name not in self._created_files:
                logger.warning(
                    'File "%s" already exists, if it contains a layer with the "%s" name, the layer will be overwritten!',
                    abs_file_name,
                    normalized_name,
                )

            options.actionOnExistingFile = (
                QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteLayer
            )
        else:
            options.actionOnExistingFile = (
                QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile
            )

            self._created_files.add(abs_file_name)

        write_result, error_message, new_file, new_layer = (
            QgsVectorFileWriter.writeAsVectorFormatV3(
                layer,
                str(abs_file_name),
                self._project.transformContext(),
                options,
            )
        )

        if write_result != QgsVectorFileWriter.WriterError.NoError:
            raise Qgis2JsonError(
                f"Error writing vector layer: {write_result} {error_message}"
            )

        if new_file != str(abs_file_name) or new_layer != normalized_name:
            raise Qgis2JsonError(
                f'Unexpected vector writer output for layer "{dataset_def.name}": '
                f'expected file "{abs_file_name}" and layer "{normalized_name}", '
                f'got file "{new_file}" and layer "{new_layer}".'
            )

        # TODO @suricactus: this way of loading a layer will work fine for GPKG, but might be problematic for other formats.
        new_layer = QgsVectorLayer(
            f"{abs_file_name}|layername={new_layer}",
            dataset_def.name,
            layer_provider_lib,
        )

        set_layer_virtual_fields(new_layer, dataset_def)
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
            raise UnknownVectorLayerDataproviderError(
                f"Failed to get data provider for layer: {dataset_def.name}"
            )

        fields = create_fields(dataset_def)

        layer_data_provider.addAttributes(fields)
        layer.updateFields()

    def _add_vector_layer_data(
        self, layer: QgsVectorLayer, dataset_def: VectorDatasetDef
    ) -> None:
        layer.startEditing()
        layer_data_provider = layer.dataProvider()

        if not bool(layer_data_provider) or not layer_data_provider.isValid():
            raise UnknownVectorLayerDataproviderError(
                "Failed to get data provider for layer 1: %s", dataset_def.name
            )

        if layer.geometryType() != Qgis.GeometryType.Null:
            raise NotImplementedError(
                "Cannot edit geometry layer: %s has geometry %s",
                dataset_def.name,
                layer.geometryType(),
            )

        layer_data = dataset_def.data
        if not layer_data:
            logger.debug("No feature data to be added to layer %s!", dataset_def.name)

            return

        features = []
        for feature_def in layer_data:
            feature = QgsFeature(layer.fields())

            for field_name, value in feature_def.items():
                feature.setAttribute(field_name, value)

            features.append(feature)

        is_add_features_success, _features = layer_data_provider.addFeatures(features)

        if not is_add_features_success:
            raise Qgis2JsonError(
                f'Failed to add feature data to layer "{dataset_def.name}".'
            )

        layer.updateExtents()

        if not layer.commitChanges():
            raise Qgis2JsonError(
                f'Failed to commit feature data to layer "{dataset_def.name}".'
            )

    def _set_relations(self) -> None:
        relation_manager = self._project.relationManager()

        assert relation_manager is not None

        for relation_def in self.definition.relations:
            relation = create_relation(relation_def)
            relation_manager.addRelation(relation)

        for poly_relation_def in self.definition.polymorphic_relations:
            relation = create_polymorphic_relation(poly_relation_def)
            relation_manager.addPolymorphicRelation(relation)

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
