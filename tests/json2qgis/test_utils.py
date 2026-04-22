import pytest
from qgis.core import (
    Qgis,
    QgsAttributeEditorContainer,
    QgsAttributeEditorField,
    QgsField,
    QgsFieldConstraints,
    QgsMapLayer,
    QgsProject,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QMetaType

from convert2qgis.json2qgis.utils import (
    check_output,
    create_field,
    create_fields,
    create_polymorphic_relation,
    create_relation,
    get_attribute_form_container_type,
    get_constraint_strength,
    get_layer_edit_form,
    get_layer_flags,
    normalize_name,
    set_field_constraints,
    set_field_default_value,
    set_field_widget,
    set_layer_fields,
    set_layer_tree,
    set_project_custom_properties,
)


@pytest.fixture
def sample_field():
    return QgsField("sample_field", QMetaType.Type.QString, len=255)


@pytest.fixture
@check_output("definitions/Field")
def sample_field_def():
    return {
        "name": "Sample Field",
        "type": "string",
        "length": 0,
        "precision": 0,
        "comment": "This is a sample field",
        "is_not_null": False,
        "is_not_null_strength": "hard",
        "constraint_expression": "",
        "constraint_expression_description": "",
        "constraint_expression_strength": "not_set",
        "is_unique": False,
        "is_unique_strength": "not_set",
        "default_value": "",
        "set_default_value_on_update": False,
        "alias": "Sample Field Alias",
        "widget_type": "TextEdit",
        "widget_config": {},
    }


@pytest.fixture
@check_output("definitions/VectorDataset")
def sample_vector_layer_def(sample_field_def):
    integer_field = {
        **sample_field_def,
        "name": "Field integer",
        "type": "integer",
        "length": 0,
        "precision": 0,
        "comment": "This is field integer",
        "alias": "Field integer alias",
        "widget_type": "Range",
        "widget_config": {
            "min": 10,
            "max": 20,
            "step": 2,
            "precision": 0,
            "suffix": " m",
            "style": "spinbox",
            "allow_null": True,
        },
        "is_not_null": True,
        "is_not_null_strength": "hard",
        "is_unique": True,
        "is_unique_strength": "soft",
    }
    real_field = {
        **sample_field_def,
        "name": "Field real",
        "type": "real",
        "length": 0,
        "precision": 0,
        "comment": "This is field real",
        "alias": "Field real alias",
        "default_value": "3.14",
        "widget_type": "Range",
        "widget_config": {
            "min": 10.1,
            "max": 20.1,
            "step": 0.1,
            "precision": 1,
            "suffix": " cm",
            "style": "dial",
            "allow_null": False,
        },
        "is_not_null": True,
        "is_not_null_strength": "hard",
        "constraint_expression": "value > 0",
        "constraint_expression_strength": "hard",
        "constraint_expression_description": "Real must be > 0",
    }
    bool_field = {
        **sample_field_def,
        "name": "Field bool",
        "type": "boolean",
        "length": 0,
        "precision": 0,
        "comment": "This is field bool",
        "alias": "Field bool alias",
        "widget_type": "CheckBox",
        "widget_config": {},
        "is_not_null": True,
        "is_not_null_strength": "hard",
    }
    string_field = {
        **sample_field_def,
        "name": "Field string",
        "type": "string",
        "length": 0,
        "precision": 0,
        "comment": "This is field string",
        "alias": "Field string alias",
        "widget_type": "TextEdit",
        "widget_config": {
            "is_multiline": True,
            "use_html": True,
        },
        "is_not_null": True,
        "is_not_null_strength": "hard",
    }
    date_field = {
        **sample_field_def,
        "name": "Field date",
        "type": "date",
        "length": 0,
        "precision": 0,
        "comment": "This is field date",
        "alias": "Field date alias",
        "widget_type": "DateTime",
        "widget_config": {
            "allow_null": True,
            "calendar_popup": True,
            "display_format": "yyyy-MM-dd",
            "field_format": "yyyy-MM-dd",
            "field_format_overwrite": True,
            "field_iso_format": True,
        },
        "is_not_null": True,
        "is_not_null_strength": "hard",
    }
    datetime_field = {
        **sample_field_def,
        "name": "Field datetime",
        "type": "datetime",
        "length": 0,
        "precision": 0,
        "comment": "This is field datetime",
        "alias": "Field datetime alias",
        "widget_type": "DateTime",
        "widget_config": {
            "allow_null": True,
            "calendar_popup": True,
            "display_format": "yyyy-MM-dd HH:mm:ss",
            "field_format": "yyyy-MM-dd HH:mm:ss",
            "field_format_overwrite": True,
            "field_iso_format": True,
        },
        "is_not_null": True,
        "is_not_null_strength": "hard",
    }

    return {
        "layer_id": "sample_layer",
        "name": "Sample Layer",
        "layer_type": "vector",
        "datasource_format": "memory",
        "is_identifiable": False,
        "is_removable": False,
        "is_searchable": False,
        "is_private": False,
        "crs": "EPSG:4326",
        "geometry_type": "NoGeometry",
        "foreign_keys": [],
        "indices": [],
        "primary_key": "",
        "fields": [
            integer_field,
            real_field,
            bool_field,
            string_field,
            date_field,
            datetime_field,
        ],
        "form_config": [
            {
                "column_count": 3,
                "item_id": "main_tab",
                "parent_id": None,
                "label": "Main",
                "type": "tab",
            },
            {
                "background_color": "",
                "column_count": 2,
                "item_id": "basic_info_group",
                "is_collapsed": True,
                "label": "Basic Info",
                "parent_id": "main_tab",
                "type": "group_box",
                "visibility_expression": "1 > 0",
            },
            {
                "item_id": "caffdaed-fbec-4bf1-a21e-ba84360184e9",
                "field_name": "Field integer",
                "parent_id": "main_tab",
                "type": "field",
            },
            {
                "item_id": "61c6b488-9726-4f1b-b6a7-ca3b7c61293b",
                "field_name": "Field real",
                "parent_id": "basic_info_group",
                "type": "field",
            },
            {
                "item_id": "79002a29-036a-4b1c-baef-49ab49f88a7c",
                "field_name": "Field bool",
                "parent_id": "basic_info_group",
                "type": "field",
            },
            {
                "item_id": "c9c7aadc-ff12-4cb0-92a7-f13e0705705a",
                "field_name": "Field string",
                "parent_id": "basic_info_group",
                "type": "field",
            },
            {
                "item_id": "c5855c64-ef0d-4330-af90-a357a1848016",
                "field_name": "Field datetime",
                "parent_id": "basic_info_group",
                "type": "field",
            },
            {
                "item_id": "attachment_tab",
                "label": "Attachment",
                "type": "tab",
                "parent_id": None,
            },
            {
                "item_id": "5b93e54f-0f40-4524-aee2-78c6810d7d8a",
                "field_name": "Field string",
                "parent_id": "attachment_tab",
                "type": "field",
            },
            {
                "item_id": "2f25c1e4-19f0-4760-9725-0896a8127915",
                "label": "Hello *World*",
                "parent_id": "attachment_tab",
                "type": "text",
                "is_markdown": True,
            },
        ],
    }


@pytest.fixture
@check_output("definitions/Json2qgisSchema")
def sample_project_def(sample_vector_layer_def):
    return {
        "version": "1.0.0",
        "project": {
            "author": "Test Author",
            "title": "Sample Project",
        },
        "datasets": [
            {
                "vector_datasets": [sample_vector_layer_def],
                "raster_datasets": [],
            }
        ],
        "legend_tree": {
            "item_id": "legend_root",
            "is_checked": True,
            "name": "",
            "legend_item_type": "group",
            "children": [
                {
                    "item_id": "my_group_parent",
                    "is_checked": True,
                    "name": "My group parent",
                    "legend_item_type": "group",
                    "children": [
                        {
                            "item_id": "my_group_child",
                            "is_checked": True,
                            "name": "My group child",
                            "legend_item_type": "group",
                            "children": [
                                {
                                    "item_id": "my_child",
                                    "is_checked": True,
                                    "layer_id": "d942d84e-bcbf-430b-bf5d-9b39caeabf71",
                                    "name": "My test layer",
                                    "legend_item_type": "layer",
                                },
                                {
                                    "item_id": "my_group_child_two",
                                    "is_checked": False,
                                    "is_mutually_exclusive": True,
                                    "name": "My test subgroup",
                                    "legend_item_type": "group",
                                    "children": [],
                                },
                            ],
                        }
                    ],
                },
                {
                    "item_id": "my_second_parent",
                    "is_checked": True,
                    "is_mutually_exclusive": True,
                    "name": "My second parent",
                    "legend_item_type": "group",
                    "children": [],
                },
            ],
        },
        "relations": [],
        "polymorphic_relations": [],
    }


@pytest.fixture
@check_output("definitions/Relation")
def sample_relation_def():
    return {
        "relation_id": "f0eb51d8-77df-4b2f-8f54-826464742ee5",
        "name": "relation",
        "from_layer_id": "layer_a",
        "to_layer_id": "layer_b",
        "field_pairs": [
            {
                "from_field": "layer_a_field",
                "to_field": "layer_b_field",
            }
        ],
        "strength": "composition",
    }


@pytest.fixture
@check_output("definitions/PolymorphicRelation")
def sample_polymorphic_relation_def():
    return {
        "relation_id": "a1b2c3d4-e5f6-7890-abcd-ef0123456789",
        "name": "polymorphic_relation",
        "from_layer_id": "documents",
        "to_layer_field": "layer_id",
        "to_layer_ids": ["birds", "mammals"],
        "to_layer_expression": "@layer_id",
        "strength": "composition",
        "field_pairs": [
            {
                "from_field": "uuid",
                "to_field": "document_uuid",
            },
        ],
    }


@pytest.fixture
def project() -> QgsProject:
    project = QgsProject.instance()

    assert project

    return project


class TestUtils:
    def test_normalize_name_ascii(self):
        """Test normalize_name with ASCII characters."""
        result = normalize_name("Simple Name")
        assert result == "simple_name"

    def test_normalize_name_cyrillic(self):
        """Test normalize_name with Cyrillic characters."""
        result = normalize_name("Примерно име")
        assert result == "primerno_ime"

    def test_normalize_name_non_ascii(self):
        """Test normalize_name with non-ASCII characters."""
        result = normalize_name("Schöne Café")
        assert result == "schone_cafe"

    def test_normalize_name_mixed(self):
        """Test normalize_name with mixed characters."""
        result = normalize_name("Test_Тест_123")
        assert result == "test_test_123"

    def test_get_constraint_strength_hard(self):
        """Test get_constraint_strength with 'hard'."""
        strength = get_constraint_strength("hard")
        assert strength == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard

    def test_get_constraint_strength_soft(self):
        """Test get_constraint_strength with 'soft'."""
        strength = get_constraint_strength("soft")
        assert strength == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthSoft

    def test_get_constraint_strength_not_set(self):
        """Test get_constraint_strength with 'not_set'."""
        strength = get_constraint_strength("not_set")
        assert strength == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthNotSet

    def test_get_constraint_strength_unknown(self):
        """Test get_constraint_strength with unknown value."""
        with pytest.raises(NotImplementedError):
            get_constraint_strength("unknown")

    def test_get_attribute_form_container_type_group_box(self):
        """Test get_attribute_form_container_type with 'group_box'."""
        container_type = get_attribute_form_container_type("group_box")
        assert container_type == Qgis.AttributeEditorContainerType.GroupBox

    def test_get_attribute_form_container_type_tab(self):
        """Test get_attribute_form_container_type with 'tab'."""
        container_type = get_attribute_form_container_type("tab")
        assert container_type == Qgis.AttributeEditorContainerType.Tab

    def test_get_attribute_form_container_type_row(self):
        """Test get_attribute_form_container_type with 'row'."""
        container_type = get_attribute_form_container_type("row")
        assert container_type == Qgis.AttributeEditorContainerType.Row

    def test_get_attribute_form_container_type_unsupported(self):
        """Test get_attribute_form_container_type with unsupported type."""
        with pytest.raises(NotImplementedError):
            get_attribute_form_container_type("unsupported")

    def test_create_field_def_as_string(self, sample_field_def):
        """Test creation of a FieldDef TypedDict."""
        sample_field_def.update(
            {
                "name": "Field String",
                "type": "string",
                "length": 255,
                "precision": 0,
                "comment": "This is a test string field",
            }
        )

        field = create_field(sample_field_def)

        assert field.name() == "Field String"
        assert field.type() == QMetaType.Type.QString
        assert field.length() == 255
        assert field.precision() == 0
        assert field.comment() == "This is a test string field"

    def test_create_field_def_as_integer(self, sample_field_def):
        """Test creation of a FieldDef TypedDict."""
        sample_field_def.update(
            {
                "name": "Field Integer",
                "type": "integer",
                "length": 3,
                "precision": 0,
                "comment": "This is a test integer field",
            }
        )

        field = create_field(sample_field_def)

        assert field.name() == "Field Integer"
        assert field.type() == QMetaType.Type.Int
        assert field.length() == 3
        assert field.precision() == 0
        assert field.comment() == "This is a test integer field"

    def test_create_field_def_as_real(self, sample_field_def):
        """Test creation of a FieldDef TypedDict."""
        sample_field_def.update(
            {
                "id": "field_real",
                "name": "Field Real",
                "type": "real",
                "length": 3,
                "precision": 0,
                "comment": "This is a test real field",
            }
        )

        field = create_field(sample_field_def)

        assert field.name() == "Field Real"
        assert field.type() == QMetaType.Type.Double
        assert field.length() == 3
        assert field.precision() == 0
        assert field.comment() == "This is a test real field"

    def test_set_field_default_value_no_default(self, sample_field, sample_field_def):
        """Test setting default value for a field."""
        sample_field_def.update(
            {
                "default_value": None,
                "set_default_value_on_update": False,
            }
        )

        set_field_default_value(sample_field, sample_field_def)

        assert sample_field.defaultValueDefinition().isValid() is False

    def test_set_field_default_value_with_default(self, sample_field, sample_field_def):
        """Test setting default value for a field."""
        sample_field_def.update(
            {
                "default_value": "'default value'",
                "set_default_value_on_update": True,
            }
        )

        set_field_default_value(sample_field, sample_field_def)

        default_value = sample_field.defaultValueDefinition()

        assert default_value.isValid()
        assert default_value.expression() == "'default value'"
        assert default_value.applyOnUpdate() is True

    def test_set_field_constraints_no_constraints(self, sample_field, sample_field_def):
        """Test setting constraints for a field with no constraints."""
        sample_field_def.update(
            {
                "is_not_null": False,
                "is_unique": False,
                "constraint_expression": "",
            }
        )

        set_field_constraints(sample_field, sample_field_def)

        constraints = sample_field.constraints()

        # Check that no constraints are set
        assert not constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintNotNull
        assert not constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintUnique
        assert not constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintExpression

    def test_set_field_constraints_with_not_null(self, sample_field, sample_field_def):
        """Test setting constraints for a field."""
        sample_field_def.update(
            {
                "is_not_null": True,
                "is_not_null_strength": "soft",
            }
        )

        set_field_constraints(sample_field, sample_field_def)

        constraints = sample_field.constraints()

        # Check Not Null constraint
        assert constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintNotNull
        assert (
            constraints.constraintStrength(QgsFieldConstraints.Constraint.ConstraintNotNull)
            == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthSoft
        )

        assert not constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintUnique
        assert not constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintExpression

    def test_set_field_constraints_with_unique(self, sample_field, sample_field_def):
        """Test setting constraints for a field."""
        sample_field_def.update(
            {
                "is_unique": True,
                "is_unique_strength": "hard",
            }
        )

        set_field_constraints(sample_field, sample_field_def)

        constraints = sample_field.constraints()

        # Check Not Null constraint
        assert constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintUnique
        assert (
            constraints.constraintStrength(QgsFieldConstraints.Constraint.ConstraintUnique)
            == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard
        )

        assert not constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintNotNull
        assert not constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintExpression

    def test_set_field_constraints_with_expression(self, sample_field, sample_field_def):
        """Test setting constraints for a field."""
        sample_field_def.update(
            {
                "constraint_expression": "random() > 0.5",
                "constraint_expression_strength": "hard",
                "constraint_expression_description": "Random constraint message",
            }
        )

        set_field_constraints(sample_field, sample_field_def)

        constraints = sample_field.constraints()

        # Check Not Null constraint
        assert constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintExpression
        assert (
            constraints.constraintStrength(QgsFieldConstraints.Constraint.ConstraintExpression)
            == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard
        )
        assert constraints.constraintDescription() == "Random constraint message"

        assert not constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintNotNull
        assert not constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintUnique

    def test_set_field_constraints_all(self, sample_field, sample_field_def):
        """Test setting all constraints for a field."""
        sample_field_def.update(
            {
                "is_not_null": True,
                "is_not_null_strength": "soft",
                "is_unique": True,
                "is_unique_strength": "hard",
                "constraint_expression": "random() > 0.5",
                "constraint_expression_strength": "hard",
                "constraint_expression_description": "Random constraint message",
            }
        )

        set_field_constraints(sample_field, sample_field_def)

        constraints = sample_field.constraints()

        # Check Not Null constraint
        assert constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintNotNull
        assert (
            constraints.constraintStrength(QgsFieldConstraints.Constraint.ConstraintNotNull)
            == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthSoft
        )

        # Check Unique constraint
        assert constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintUnique
        assert (
            constraints.constraintStrength(QgsFieldConstraints.Constraint.ConstraintUnique)
            == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard
        )

        # Check Expression constraint
        assert constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintExpression
        assert (
            constraints.constraintStrength(QgsFieldConstraints.Constraint.ConstraintExpression)
            == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard
        )
        assert constraints.constraintDescription() == "Random constraint message"

    def test_set_field_widget_hidden(self, sample_field, sample_field_def):
        """Test setting widget for a hidden field."""
        sample_field_def.update(
            {
                "widget_type": "Hidden",
                "widget_config": {},
            }
        )

        set_field_widget(sample_field, sample_field_def)

        widget_setup = sample_field.editorWidgetSetup()

        assert widget_setup.type() == "Hidden"
        assert widget_setup.config() == {}

    def test_set_field_widget_color(self, sample_field, sample_field_def):
        """Test setting widget for a color field."""
        sample_field_def.update(
            {
                "widget_type": "Color",
                "widget_config": {},
            }
        )

        set_field_widget(sample_field, sample_field_def)

        widget_setup = sample_field.editorWidgetSetup()

        assert widget_setup.type() == "Color"
        assert widget_setup.config() == {}

    def test_set_field_widget_text(self, sample_field, sample_field_def):
        """Test setting widget for a text field."""
        sample_field_def.update(
            {
                "widget_type": "TextEdit",
                "widget_config": {
                    "is_multiline": True,
                    "use_html": True,
                },
            }
        )

        set_field_widget(sample_field, sample_field_def)

        widget_setup = sample_field.editorWidgetSetup()

        assert widget_setup.type() == "TextEdit"
        assert widget_setup.config().get("IsMultiline") is True
        assert widget_setup.config().get("UseHtml") is True

    def test_set_field_widget_range(self, sample_field, sample_field_def):
        """Test setting widget for a range field."""
        sample_field_def.update(
            {
                "widget_type": "Range",
                "widget_config": {
                    "Min": 10,
                    "Max": 20,
                    "Step": 2,
                    "Precision": 3,
                    "Suffix": " m",
                    "Style": "slider",
                    "AllowNull": False,
                },
            }
        )

        set_field_widget(sample_field, sample_field_def)

        widget_setup = sample_field.editorWidgetSetup()

        assert widget_setup.type() == "Range"
        assert widget_setup.config().get("Min") == 10
        assert widget_setup.config().get("Max") == 20
        assert widget_setup.config().get("Step") == 2
        assert widget_setup.config().get("Precision") == 3
        assert widget_setup.config().get("Suffix") == " m"
        assert widget_setup.config().get("Style") == "slider"
        assert widget_setup.config().get("AllowNull") is False

    def test_set_field_widget_checkbox(self, sample_field, sample_field_def):
        """Test setting widget for a checkbox field."""
        sample_field_def.update(
            {
                "widget_type": "CheckBox",
                "widget_config": {
                    "allow_null": True,
                    "checked_state": "Hello",
                    "unchecked_state": "Bye",
                    "text_display_method": 1,
                },
            }
        )

        set_field_widget(sample_field, sample_field_def)

        widget_setup = sample_field.editorWidgetSetup()

        assert widget_setup.type() == "CheckBox"
        assert widget_setup.config().get("AllowNullState") is True
        assert widget_setup.config().get("CheckedState") == "Hello"
        assert widget_setup.config().get("UncheckedState") == "Bye"
        assert widget_setup.config().get("TextDisplayMethod") == 1

    def test_set_field_widget_datetime(self, sample_field, sample_field_def):
        """Test setting widget for a range field."""
        sample_field_def.update(
            {
                "widget_type": "DateTime",
                "widget_config": {
                    "allow_null": False,
                    "calendar_popup": True,
                    "display_format": "yyyy-MM-dd TTT HH:mm:ss",
                    "field_format": "yyyy-MM-dd TTT HH:mm:ss",
                    "field_format_overwrite": True,
                    "field_iso_format": True,
                },
            }
        )

        set_field_widget(sample_field, sample_field_def)

        widget_setup = sample_field.editorWidgetSetup()

        assert widget_setup.type() == "DateTime"
        assert widget_setup.config().get("allow_null") is False
        assert widget_setup.config().get("calendar_popup") is True
        assert widget_setup.config().get("display_format") == "yyyy-MM-dd TTT HH:mm:ss"
        assert widget_setup.config().get("field_format") == "yyyy-MM-dd TTT HH:mm:ss"
        assert widget_setup.config().get("field_format_overwrite") is True
        assert widget_setup.config().get("field_iso_format") is True

    def test_set_field_widget_externalresource(self, sample_field, sample_field_def):
        """Test setting widget for a externalresource field."""
        sample_field_def.update(
            {
                "widget_type": "ExternalResource",
                "widget_config": {
                    "DocumentViewer": True,
                    "DocumentViewerHeight": 100,
                    "DocumentViewerWidth": 100,
                    "FileWidget": True,
                    "FileWidgetButton": True,
                    "FileWidgetFilter": "*.png",
                    "RelativeStorage": True,
                    "StorageAuthConfigId": "abc",
                    "StorageMode": 0,
                    "StorageType": None,
                },
            }
        )

        set_field_widget(sample_field, sample_field_def)

        widget_setup = sample_field.editorWidgetSetup()

        assert widget_setup.type() == "ExternalResource"
        assert widget_setup.config().get("DocumentViewer") is True
        assert widget_setup.config().get("DocumentViewerHeight") == 100
        assert widget_setup.config().get("DocumentViewerWidth") == 100
        assert widget_setup.config().get("FileWidget") is True
        assert widget_setup.config().get("FileWidgetButton") is True
        assert widget_setup.config().get("FileWidgetFilter") == "*.png"
        assert widget_setup.config().get("RelativeStorage") is True
        assert widget_setup.config().get("StorageAuthConfigId") == "abc"
        assert widget_setup.config().get("StorageMode") == 0
        assert widget_setup.config().get("StorageType") is None

    def test_set_field_widget_valuemap(self, sample_field, sample_field_def):
        """Test setting widget for a valuemap field."""
        sample_field_def.update(
            {
                "widget_type": "ValueMap",
                "widget_config": {
                    "map": {
                        "Hello": "World",
                    }
                },
            }
        )

        set_field_widget(sample_field, sample_field_def)

        widget_setup = sample_field.editorWidgetSetup()

        assert widget_setup.type() == "ValueMap"
        assert widget_setup.config().get("map") == {
            "Hello": "World",
        }

    def test_get_layer_flags_to_false(self, sample_vector_layer_def):
        """Test getting layer flags from VectorDatasetDef."""
        sample_vector_layer_def.update(
            {
                "is_identifiable": False,
                "is_removable": False,
                "is_searchable": False,
                "is_private": False,
            }
        )

        flags = QgsMapLayer.LayerFlags()

        flags = get_layer_flags(flags, sample_vector_layer_def)  # type: ignore

        assert not flags & QgsMapLayer.LayerFlag.Identifiable  # type: ignore
        assert not flags & QgsMapLayer.LayerFlag.Removable  # type: ignore
        assert not flags & QgsMapLayer.LayerFlag.Searchable  # type: ignore
        assert not flags & QgsMapLayer.LayerFlag.Private  # type: ignore

    def test_get_layer_flags_to_true(self, sample_vector_layer_def):
        """Test getting layer flags from VectorDatasetDef."""
        sample_vector_layer_def.update(
            {
                "is_identifiable": True,
                "is_removable": True,
                "is_searchable": True,
                "is_private": True,
            }
        )

        flags = QgsMapLayer.LayerFlags()

        flags = get_layer_flags(flags, sample_vector_layer_def)  # type: ignore

        assert flags & QgsMapLayer.LayerFlag.Identifiable  # type: ignore
        assert flags & QgsMapLayer.LayerFlag.Removable  # type: ignore
        assert flags & QgsMapLayer.LayerFlag.Searchable  # type: ignore
        assert flags & QgsMapLayer.LayerFlag.Private  # type: ignore

    def test_set_layer_field_configurations(self, sample_vector_layer_def):
        """Test setting layer field configurations."""
        fields = create_fields(sample_vector_layer_def)

        assert fields.count() == 6

        field_string = fields.field(0)

        assert field_string.name() == "Field integer"
        assert field_string.type() == QMetaType.Type.Int
        assert field_string.length() == 0
        assert field_string.precision() == 0
        assert field_string.comment() == "This is field integer"

        field_real = fields.field(1)

        assert field_real.name() == "Field real"
        assert field_real.type() == QMetaType.Type.Double
        assert field_real.length() == 0
        assert field_real.precision() == 0
        assert field_real.comment() == "This is field real"

        field_bool = fields.field(2)

        assert field_bool.name() == "Field bool"
        assert field_bool.type() == QMetaType.Type.Bool
        assert field_bool.length() == 0
        assert field_bool.precision() == 0
        assert field_bool.comment() == "This is field bool"

        field_string = fields.field(3)

        assert field_string.name() == "Field string"
        assert field_string.type() == QMetaType.Type.QString
        assert field_string.length() == 0
        assert field_string.precision() == 0
        assert field_string.comment() == "This is field string"

        field_date = fields.field(4)

        assert field_date.name() == "Field date"
        assert field_date.type() == QMetaType.Type.QDate
        assert field_date.length() == 0
        assert field_date.precision() == 0
        assert field_date.comment() == "This is field date"

        field_datetime = fields.field(5)

        assert field_datetime.name() == "Field datetime"
        assert field_datetime.type() == QMetaType.Type.QDateTime
        assert field_datetime.length() == 0
        assert field_datetime.precision() == 0
        assert field_datetime.comment() == "This is field datetime"

    def test_get_layer_edit_form(self, sample_vector_layer_def):
        """Test getting layer edit form configuration."""
        fields = create_fields(sample_vector_layer_def)
        form_config = get_layer_edit_form(fields, sample_vector_layer_def)

        assert form_config.layout() == Qgis.AttributeFormLayout.DragAndDrop
        assert len(form_config.tabs()) == 2

        tabs = form_config.tabs()

        assert len(tabs) == 2
        assert tabs[0].name() == "Main"
        assert tabs[1].name() == "Attachment"

        assert isinstance(tabs[0], QgsAttributeEditorContainer)
        assert len(tabs[0].children()) == 2
        assert isinstance(tabs[1], QgsAttributeEditorContainer)
        assert len(tabs[1].children()) == 2

        basic_info_group = tabs[0].children()[0]

        assert isinstance(basic_info_group, QgsAttributeEditorContainer)
        assert basic_info_group.name() == "Basic Info"
        assert basic_info_group.type() == Qgis.AttributeEditorContainerType.GroupBox
        assert basic_info_group.columnCount() == 2
        assert basic_info_group.visibilityExpression().data().expression() == "1 > 0"
        assert len(basic_info_group.children()) == 4

        assert isinstance(basic_info_group.children()[0], QgsAttributeEditorField)
        assert basic_info_group.children()[0].name() == "Field real"
        assert isinstance(basic_info_group.children()[1], QgsAttributeEditorField)
        assert basic_info_group.children()[1].name() == "Field bool"
        assert isinstance(basic_info_group.children()[2], QgsAttributeEditorField)
        assert basic_info_group.children()[2].name() == "Field string"
        assert isinstance(basic_info_group.children()[3], QgsAttributeEditorField)
        assert basic_info_group.children()[3].name() == "Field datetime"

        assert isinstance(tabs[0].children()[1], QgsAttributeEditorField)
        assert tabs[0].children()[1].name() == "Field integer"

        assert isinstance(tabs[0].children()[0], QgsAttributeEditorContainer)
        assert tabs[1].children()[0].name() == "Field string"
        # NOTE in theory we should be able to check for `isinstance(tabs[1].children()[1].type(), QgsAttributeEditorTextElement)`,
        # but unfortunately we get the abstract class `QgsAttributeEditorElement` as a type and we need to check the type value instead
        assert tabs[1].children()[1].type() == Qgis.AttributeEditorType.TextElement
        assert tabs[1].children()[1].name() == "<p>Hello <em>World</em></p>"

    def test_set_layer_fields(self, sample_vector_layer_def):
        """Test setting layer fields from VectorDatasetDef."""
        fields = create_fields(sample_vector_layer_def)

        layer = QgsVectorLayer("Point?crs=EPSG:4326", "test_layer", "memory")
        data_provider = layer.dataProvider()

        assert data_provider is not None

        data_provider.addAttributes(fields.toList())
        layer.updateFields()

        assert layer.fields().count() == 6

        set_layer_fields(layer, sample_vector_layer_def)

        fields = layer.fields()

        assert fields.count() == 6

        field_string = fields.field(0)
        editor_widget = layer.editorWidgetSetup(0)
        field_int_constraints = layer.fieldConstraintsAndStrength(0)

        assert field_string.name() == "Field integer"
        assert field_string.type() == QMetaType.Type.Int
        assert field_string.length() == 0
        assert field_string.precision() == 0
        assert field_string.comment() == "This is field integer"
        assert layer.attributeAlias(0) == "Field integer alias"
        assert layer.defaultValueDefinition(0).isValid() is False
        assert editor_widget.type() == "Range"
        assert editor_widget.config().get("min") == 10
        assert editor_widget.config().get("max") == 20
        assert editor_widget.config().get("step") == 2
        assert editor_widget.config().get("precision") == 0
        assert editor_widget.config().get("suffix") == " m"
        assert editor_widget.config().get("style") == "spinbox"
        assert editor_widget.config().get("allow_null") is True
        assert (
            field_int_constraints[QgsFieldConstraints.Constraint.ConstraintNotNull]
            == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard
        )
        assert (
            field_int_constraints[QgsFieldConstraints.Constraint.ConstraintUnique]
            == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthSoft
        )
        assert QgsFieldConstraints.Constraint.ConstraintExpression not in field_int_constraints

        field_real = fields.field(1)
        editor_widget = layer.editorWidgetSetup(1)
        field_real_constraints = layer.fieldConstraintsAndStrength(1)

        assert field_real.name() == "Field real"
        assert field_real.type() == QMetaType.Type.Double
        assert field_real.length() == 0
        assert field_real.precision() == 0
        assert field_real.comment() == "This is field real"
        assert layer.attributeAlias(1) == "Field real alias"
        assert layer.defaultValueDefinition(1).isValid() is True
        assert layer.defaultValueDefinition(1).expression() == "3.14"
        assert editor_widget.type() == "Range"
        assert editor_widget.config().get("min") == 10.1
        assert editor_widget.config().get("max") == 20.1
        assert editor_widget.config().get("step") == 0.1
        assert editor_widget.config().get("precision") == 1
        assert editor_widget.config().get("suffix") == " cm"
        assert editor_widget.config().get("style") == "dial"
        assert editor_widget.config().get("allow_null") is False
        assert (
            field_real_constraints[QgsFieldConstraints.Constraint.ConstraintNotNull]
            == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard
        )

        assert QgsFieldConstraints.Constraint.ConstraintUnique not in field_real_constraints
        assert (
            field_real_constraints[QgsFieldConstraints.Constraint.ConstraintExpression]
            == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard
        )
        assert layer.constraintExpression(1) == "value > 0"
        assert layer.constraintDescription(1) == "Real must be > 0"

        field_bool = fields.field(2)
        editor_widget = layer.editorWidgetSetup(2)
        field_bool_constraints = layer.fieldConstraintsAndStrength(2)

        assert field_bool.name() == "Field bool"
        assert field_bool.type() == QMetaType.Type.Bool
        assert field_bool.length() == 0
        assert field_bool.precision() == 0
        assert field_bool.comment() == "This is field bool"
        assert layer.attributeAlias(2) == "Field bool alias"
        assert layer.defaultValueDefinition(2).isValid() is False
        assert editor_widget.type() == "CheckBox"
        assert (
            field_bool_constraints[QgsFieldConstraints.Constraint.ConstraintNotNull]
            == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard
        )
        assert QgsFieldConstraints.Constraint.ConstraintUnique not in field_bool_constraints
        assert QgsFieldConstraints.Constraint.ConstraintExpression not in field_bool_constraints

        field_string = fields.field(3)
        editor_widget = layer.editorWidgetSetup(3)
        field_string_constraints = layer.fieldConstraintsAndStrength(3)

        assert field_string.name() == "Field string"
        assert field_string.type() == QMetaType.Type.QString
        assert field_string.length() == 0
        assert field_string.precision() == 0
        assert field_string.comment() == "This is field string"
        assert layer.attributeAlias(3) == "Field string alias"
        assert layer.defaultValueDefinition(3).isValid() is False
        assert editor_widget.type() == "TextEdit"
        assert editor_widget.config().get("IsMultiline") is True
        assert editor_widget.config().get("UseHtml") is True
        assert (
            field_string_constraints[QgsFieldConstraints.Constraint.ConstraintNotNull]
            == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard
        )
        assert QgsFieldConstraints.Constraint.ConstraintUnique not in field_string_constraints
        assert QgsFieldConstraints.Constraint.ConstraintExpression not in field_string_constraints

        field_date = fields.field(4)
        editor_widget = layer.editorWidgetSetup(4)
        field_date_constraints = layer.fieldConstraintsAndStrength(4)

        assert field_date.name() == "Field date"
        assert field_date.type() == QMetaType.Type.QDate
        assert field_date.length() == 0
        assert field_date.precision() == 0
        assert field_date.comment() == "This is field date"
        assert layer.attributeAlias(4) == "Field date alias"
        assert layer.defaultValueDefinition(4).isValid() is False
        assert editor_widget.type() == "DateTime"
        assert editor_widget.config().get("allow_null") is True
        assert editor_widget.config().get("calendar_popup") is True
        assert editor_widget.config().get("display_format") == "yyyy-MM-dd"
        assert editor_widget.config().get("field_format") == "yyyy-MM-dd"
        assert editor_widget.config().get("field_format_overwrite") is True
        assert editor_widget.config().get("field_iso_format") is True
        assert (
            field_date_constraints[QgsFieldConstraints.Constraint.ConstraintNotNull]
            == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard
        )
        assert QgsFieldConstraints.Constraint.ConstraintUnique not in field_date_constraints
        assert QgsFieldConstraints.Constraint.ConstraintExpression not in field_date_constraints

        field_datetime = fields.field(5)
        editor_widget = layer.editorWidgetSetup(5)
        field_datetime_constraints = layer.fieldConstraintsAndStrength(5)

        assert field_datetime.name() == "Field datetime"
        assert field_datetime.type() == QMetaType.Type.QDateTime
        assert field_datetime.length() == 0
        assert field_datetime.precision() == 0
        assert field_datetime.comment() == "This is field datetime"
        assert layer.attributeAlias(5) == "Field datetime alias"
        assert layer.defaultValueDefinition(5).isValid() is False
        assert editor_widget.type() == "DateTime"
        assert editor_widget.config().get("allow_null") is True
        assert editor_widget.config().get("calendar_popup") is True
        assert editor_widget.config().get("display_format") == "yyyy-MM-dd HH:mm:ss"
        assert editor_widget.config().get("field_format") == "yyyy-MM-dd HH:mm:ss"
        assert editor_widget.config().get("field_format_overwrite") is True
        assert editor_widget.config().get("field_iso_format") is True
        assert (
            field_datetime_constraints[QgsFieldConstraints.Constraint.ConstraintNotNull]
            == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard
        )
        assert QgsFieldConstraints.Constraint.ConstraintUnique not in field_datetime_constraints
        assert QgsFieldConstraints.Constraint.ConstraintExpression not in field_datetime_constraints

    def test_set_layer_tree(self, sample_project_def):
        """Test setting layer tree from ProjectDef."""
        project = QgsProject.instance()
        test_layer = QgsVectorLayer("Point?crs=EPSG:4326", "My test layer", "memory")
        test_layer.setId("d942d84e-bcbf-430b-bf5d-9b39caeabf71")

        assert project is not None

        project.addMapLayer(test_layer, False)

        set_layer_tree(project, sample_project_def)

        root = project.layerTreeRoot()

        assert root is not None
        assert len(root.children()) == 2

        group_parent = root.findGroup("My group parent")

        assert group_parent is not None
        assert group_parent.isVisible() is True
        assert group_parent.isMutuallyExclusive() is False
        assert group_parent.name() == "My group parent"
        assert group_parent == root.children()[0]
        assert len(group_parent.children()) == 1

        group_child = group_parent.findGroup("My group child")

        assert group_child is not None
        assert group_child.isVisible() is True
        assert group_child.isMutuallyExclusive() is False
        assert group_child.name() == "My group child"
        assert group_child == group_parent.children()[0]
        assert len(group_child.children()) == 2

        subgroup_child_one = group_child.findGroup("My test subgroup")

        assert subgroup_child_one is not None
        assert subgroup_child_one.isVisible() is False
        assert subgroup_child_one.isMutuallyExclusive() is True
        assert subgroup_child_one.name() == "My test subgroup"
        assert subgroup_child_one == group_child.children()[1]
        assert len(subgroup_child_one.children()) == 0

        test_layer = group_child.children()[0]

        assert test_layer is not None
        assert test_layer.isVisible() is True
        assert test_layer.name() == "My test layer"
        assert test_layer == group_child.findLayer("d942d84e-bcbf-430b-bf5d-9b39caeabf71")

    def test_set_project_custom_properties(self, project):
        """Test setting project custom properties."""
        project.clear()

        set_project_custom_properties(
            project,
            {
                "bool_scope/bool_key": True,
                "int_scope/int_key": 42,
                "float_scope/float_key": 3.14,
                "string_scope/string_key": "value",
                "fallback_scope/none_key": None,
            },
        )

        assert project.readBoolEntry("bool_scope", "bool_key", False) == (True, True)
        assert project.readNumEntry("int_scope", "int_key", 0) == (42, True)
        assert project.readDoubleEntry("float_scope", "float_key", 0.0) == (3.14, True)
        assert project.readEntry("string_scope", "string_key", "") == ("value", True)
        assert project.readEntry("fallback_scope", "none_key", "") == ("None", True)

    def test_set_project_custom_properties_invalid_key(self, project):
        """Test setting project custom properties with an invalid key."""
        project.clear()

        with pytest.raises(Exception, match='Invalid custom property "missing_scope"'):
            set_project_custom_properties(project, {"missing_scope": "value"})

    def test_create_relation(self, project, sample_relation_def):
        """Test creating relation."""
        referencing_layer = QgsVectorLayer(
            "Point?field=layer_a_field:integer&crs=EPSG:4326",
            "layer_a",
            "memory",
        )
        referencing_layer.setId("layer_a")
        referenced_layer = QgsVectorLayer(
            "Point?field=layer_b_field:integer&crs=EPSG:4326",
            "layer_b",
            "memory",
        )
        referenced_layer.setId("layer_b")

        project.addMapLayers([referencing_layer, referenced_layer])

        rel = create_relation(sample_relation_def)
        rel_manager = project.relationManager()

        assert rel_manager is not None

        rel_manager.addRelation(rel)

        assert rel.name() == "relation"
        assert rel.referencingLayer() == referencing_layer
        assert rel.referencedLayer() == referenced_layer
        assert rel.fieldPairs() == {"layer_a_field": "layer_b_field"}
        assert rel.strength() == Qgis.RelationshipStrength.Composition
        assert rel.isValid()

    def test_create_polymorphic_relation(self, project: QgsProject, sample_polymorphic_relation_def):
        """Test creating polymorphic relation."""
        referencing_layer = QgsVectorLayer(
            "Point?field=layer_id:string&field=uuid:string&crs=EPSG:4326",
            "documents",
            "memory",
        )
        referencing_layer.setId("documents")
        referenced_layer_birds = QgsVectorLayer(
            "Point?field=document_uuid:string&crs=EPSG:4326",
            "birds",
            "memory",
        )
        referenced_layer_birds.setId("birds")
        referenced_layer_mammals = QgsVectorLayer(
            "Point?field=document_uuid:string&crs=EPSG:4326",
            "mammals",
            "memory",
        )
        referenced_layer_mammals.setId("mammals")

        project.addMapLayers(
            [
                referencing_layer,
                referenced_layer_birds,
                referenced_layer_mammals,
            ]
        )

        rel = create_polymorphic_relation(sample_polymorphic_relation_def)
        rel_manager = project.relationManager()

        assert rel_manager is not None

        rel_manager.addPolymorphicRelation(rel)

        assert rel.name() == "polymorphic_relation"
        assert rel.referencingLayer() == referencing_layer
        assert rel.referencedLayerField() == "layer_id"
        assert rel.referencedLayerIds() == ["birds", "mammals"]
        assert rel.referencedLayerExpression() == "@layer_id"
        assert rel.fieldPairs() == {"uuid": "document_uuid"}
        assert rel.strength() == Qgis.RelationshipStrength.Composition
        assert rel.isValid()
