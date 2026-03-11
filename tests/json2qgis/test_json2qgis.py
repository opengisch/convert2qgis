# @pytest.fixture
# def project_creator(definition):
#     """Create a ProjectCreator instance with given definition."""
#     with patch("json2qgis.json2qgis.QgsProject") as mock_qgs_project:
#         mock_instance = MagicMock()
#         mock_qgs_project.return_value.instance.return_value = mock_instance
#         creator = ProjectCreator(definition)
#         creator._project = mock_instance
#         return creator


# class TestProjectCreator:
#     def test_create_field(self, project_creator, field_def):
#         """Helper to create a field using ProjectCreator."""
#         field = project_creator._create_field(field_def)

#         assert field.name() == field_def["name"]
#         assert field.type() == QgsField.String
#         assert field.length() == field_def["length"]
#         assert field.comment() == field_def["comment"]


# @pytest.fixture
# def minimal_project_def():
#     """Minimal valid project definition."""
#     return {
#         "version": "1.0",
#         "title": "Test Project",
#         "author": "Test Author",
#         "layers": [],
#         "layer_tree": {"children": []},
#     }


# @pytest.fixture
# def vector_layer_def():
#     """Sample vector layer definition."""
#     return {
#         "layer_id": "test_layer_1",
#         "name": "Test Layer",
#         "geometry_type": "Point",
#         "type": LayerType.VECTOR,
#         "crs": "EPSG:4326",
#         "datasource_format": "gpkg",
#         "fields": [
#             {
#                 "id": "field_1",
#                 "name": "test_field",
#                 "type": "str",
#                 "length": 50,
#                 "precision": 0,
#                 "comment": "Test field",
#                 "is_not_null": False,
#                 "is_not_null_strength": "not_set",
#                 "constraint_expression": "",
#                 "constraint_expression_description": "",
#                 "constraint_expression_strength": "not_set",
#                 "is_unique": False,
#                 "unique_strength": "not_set",
#                 "default_value": None,
#                 "set_default_value_on_update": False,
#                 "alias": "Test Field Alias",
#                 "widget_type": "TextEdit",
#                 "widget_config": {},
#             }
#         ],
#         "form_config": {"items": []},
#         "is_read_only": False,
#         "is_identifiable": True,
#         "is_private": False,
#         "is_searchable": True,
#         "is_removable": True,
#     }


# @pytest.fixture
# def project_creator(minimal_project_def):
#     """Create a ProjectCreator instance with minimal definition."""
#     with patch("json2qgis.json2qgis.QgsProject") as mock_qgs_project:
#         mock_instance = MagicMock()
#         mock_qgs_project.return_value.instance.return_value = mock_instance
#         creator = ProjectCreator(minimal_project_def)
#         creator._project = mock_instance
#         return creator


# class TestProjectCreator:
#     """Tests for ProjectCreator class."""

# def test_initialization(self, minimal_project_def):
#     """Test ProjectCreator initialization."""
#     with patch("json2qgis.json2qgis.QgsProject") as mock_qgs_project:
#         mock_instance = MagicMock()
#         mock_qgs_project.return_value.instance.return_value = mock_instance

#         creator = ProjectCreator(minimal_project_def)

#         assert creator.definition == minimal_project_def
#         assert creator._project is not None

# def test_normalize_name_ascii(self, project_creator):
#     """Test _normalize_name with ASCII characters."""
#     result = project_creator._normalize_name("Test Layer")
#     assert result == "Test Layer"

# def test_normalize_name_cyrillic(self, project_creator):
#     """Test _normalize_name with Cyrillic characters."""
#     result = project_creator._normalize_name("Тестовый слой")
#     assert result == "Testovyi sloi"

# def test_normalize_name_unicode(self, project_creator):
#     """Test _normalize_name with various Unicode characters."""
#     result = project_creator._normalize_name("Schöne Café")
#     assert result == "Schone Cafe"

# def test_normalize_name_mixed(self, project_creator):
#     """Test _normalize_name with mixed characters."""
#     result = project_creator._normalize_name("Test_Тест_123")
#     assert result == "Test_Test_123"


#     def test_create_field_string_type(self, project_creator):
#         """Test _create_field with string type."""
#         field_def = {
#             "id": "field_1",
#             "name": "test_string",
#             "type": "str",
#             "length": 100,
#             "precision": 0,
#             "comment": "Test string field",
#             "is_not_null": False,
#             "is_not_null_strength": "not_set",
#             "constraint_expression": "",
#             "constraint_expression_description": "",
#             "constraint_expression_strength": "not_set",
#             "is_unique": False,
#             "unique_strength": "not_set",
#             "default_value": None,
#             "set_default_value_on_update": False,
#             "alias": "",
#             "widget_type": "TextEdit",
#             "widget_config": {},
#         }

#         field = project_creator._create_field(field_def)

#         assert field.name() == "test_string"
#         assert field.length() == 100
#         assert field.comment() == "Test string field"

#     def test_create_field_int_type(self, project_creator):
#         """Test _create_field with integer type."""
#         field_def = {
#             "id": "field_2",
#             "name": "test_int",
#             "type": "int",
#             "length": 0,
#             "precision": 0,
#             "comment": "Test integer field",
#             "is_not_null": True,
#             "is_not_null_strength": "hard",
#             "constraint_expression": "",
#             "constraint_expression_description": "",
#             "constraint_expression_strength": "not_set",
#             "is_unique": False,
#             "unique_strength": "not_set",
#             "default_value": None,
#             "set_default_value_on_update": False,
#             "alias": "",
#             "widget_type": "Range",
#             "widget_config": {},
#         }

#         field = project_creator._create_field(field_def)

#         assert field.name() == "test_int"
#         assert field.type() == QMetaType.Int

#     def test_create_field_float_type(self, project_creator):
#         """Test _create_field with float type."""
#         field_def = {
#             "id": "field_3",
#             "name": "test_float",
#             "type": "float",
#             "length": 0,
#             "precision": 2,
#             "comment": "Test float field",
#             "is_not_null": False,
#             "is_not_null_strength": "not_set",
#             "constraint_expression": "",
#             "constraint_expression_description": "",
#             "constraint_expression_strength": "not_set",
#             "is_unique": False,
#             "unique_strength": "not_set",
#             "default_value": None,
#             "set_default_value_on_update": False,
#             "alias": "",
#             "widget_type": "Range",
#             "widget_config": {},
#         }

#         field = project_creator._create_field(field_def)

#         assert field.name() == "test_float"
#         assert field.precision() == 2

#     def test_create_field_date_type(self, project_creator):
#         """Test _create_field with date type."""
#         field_def = {
#             "id": "field_4",
#             "name": "test_date",
#             "type": "date",
#             "length": 0,
#             "precision": 0,
#             "comment": "Test date field",
#             "is_not_null": False,
#             "is_not_null_strength": "not_set",
#             "constraint_expression": "",
#             "constraint_expression_description": "",
#             "constraint_expression_strength": "not_set",
#             "is_unique": False,
#             "unique_strength": "not_set",
#             "default_value": None,
#             "set_default_value_on_update": False,
#             "alias": "",
#             "widget_type": "DateTime",
#             "widget_config": {},
#         }

#         field = project_creator._create_field(field_def)

#         assert field.name() == "test_date"
#         assert field.type() == QMetaType.QDate

#     def test_create_field_unknown_type(self, project_creator):
#         """Test _create_field with unknown type raises exception."""
#         field_def = {
#             "id": "field_5",
#             "name": "test_unknown",
#             "type": "unknown_type",
#             "length": 0,
#             "precision": 0,
#             "comment": "",
#             "is_not_null": False,
#             "is_not_null_strength": "not_set",
#             "constraint_expression": "",
#             "constraint_expression_description": "",
#             "constraint_expression_strength": "not_set",
#             "is_unique": False,
#             "unique_strength": "not_set",
#             "default_value": None,
#             "set_default_value_on_update": False,
#             "alias": "",
#             "widget_type": "TextEdit",
#             "widget_config": {},
#         }

#         with pytest.raises(UnknownQgisTypeError):
#             project_creator._create_field(field_def)

#     def test_set_layer_flags(self, project_creator, vector_layer_def):
#         """Test _set_layer_flags sets correct flags."""
#         mock_layer = MagicMock()
#         mock_layer.flags.return_value = 0

#         project_creator._set_layer_flags(mock_layer, vector_layer_def)

#         mock_layer.setFlags.assert_called_once()

#     def test_create_layer_unknown_type(self, project_creator):
#         """Test _create_layer with unknown layer type raises exception."""
#         layer_def = {
#             "layer_id": "unknown_layer",
#             "name": "Unknown Layer",
#             "type": "unknown_type",
#             "crs": "EPSG:4326",
#             "datasource_format": "gpkg",
#             "fields": [],
#             "form_config": {"items": []},
#             "is_read_only": False,
#             "is_identifiable": False,
#             "is_private": False,
#             "is_searchable": False,
#             "is_removable": False,
#         }

#         with pytest.raises(NotImplementedError):
#             project_creator._create_layer(layer_def)

#     def test_create_layer_invalid_crs(self, project_creator):
#         """Test _create_layer with invalid CRS raises exception."""
#         layer_def = {
#             "layer_id": "test_layer",
#             "name": "Test Layer",
#             "geometry_type": "Point",
#             "type": LayerType.VECTOR,
#             "crs": "INVALID:CRS",
#             "datasource_format": "gpkg",
#             "fields": [],
#             "form_config": {"items": []},
#             "is_read_only": False,
#             "is_identifiable": False,
#             "is_private": False,
#             "is_searchable": False,
#             "is_removable": False,
#         }

#         with patch.object(project_creator, "_create_vector_layer", return_value=MagicMock()):
#             with pytest.raises(UnknownCrsSystem):
#                 project_creator._create_layer(layer_def)

#     def test_get_constraint_strength_hard(self, project_creator):
#         """Test _get_constraint_strength with hard constraint."""
#         from qgis.core import QgsFieldConstraints

#         result = project_creator._get_constraint_strength("hard")
#         assert result == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard

#     def test_get_constraint_strength_soft(self, project_creator):
#         """Test _get_constraint_strength with soft constraint."""
#         from qgis.core import QgsFieldConstraints

#         result = project_creator._get_constraint_strength("soft")
#         assert result == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthSoft

#     def test_get_constraint_strength_not_set(self, project_creator):
#         """Test _get_constraint_strength with not_set constraint."""
#         from qgis.core import QgsFieldConstraints

#         result = project_creator._get_constraint_strength("not_set")
#         assert result == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthNotSet


# class TestLayerType:
#     """Tests for LayerType enum."""

#     def test_vector_type(self):
#         """Test VECTOR layer type."""
#         assert LayerType.VECTOR == "vector"

#     def test_raster_type(self):
#         """Test RASTER layer type."""
#         assert LayerType.RASTER == "raster"

#     def test_mesh_type(self):
#         """Test MESH layer type."""
#         assert LayerType.MESH == "mesh"

#     def test_vector_tile_type(self):
#         """Test VECTOR_TILE layer type."""
#         assert LayerType.VECTOR_TILE == "vector_tile"

#     def test_point_cloud_type(self):
#         """Test POINT_CLOUD layer type."""
#         assert LayerType.POINT_CLOUD == "point_cloud"


# class TestVectorLayerDataprovider:
#     """Tests for VectorLayerDataprovider enum."""

#     def test_gpkg_provider(self):
#         """Test GPKG data provider."""
#         assert VectorLayerDataprovider.GPKG == "gpkg"


# class TestExceptions:
#     """Tests for custom exceptions."""

#     def test_qgis2json_error(self):
#         """Test Qgis2JsonError exception."""
#         from convert2qgis.json2qgis.json2qgis import Qgis2JsonError

#         with pytest.raises(Qgis2JsonError):
#             raise Qgis2JsonError("Test error")

#     def test_unknown_qgis_type_error(self):
#         """Test UnknownQgisTypeError exception."""
#         with pytest.raises(UnknownQgisTypeError):
#             raise UnknownQgisTypeError("Unknown type")

#     def test_unknown_crs_system(self):
#         """Test UnknownCrsSystem exception."""
#         with pytest.raises(UnknownCrsSystem):
#             raise UnknownCrsSystem("Invalid CRS")

#     def test_missing_parent_error(self):
#         """Test MissingParentError exception."""
#         with pytest.raises(MissingParentError):
#             raise MissingParentError("Parent not found")

#     def test_unknown_vector_layer_dataprovider_error(self):
#         """Test UnknownVectorLayerDataproviderError exception."""
#         with pytest.raises(UnknownVectorLayerDataproviderError):
#             raise UnknownVectorLayerDataproviderError("Unknown provider")
