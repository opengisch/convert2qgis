import pytest

from json2qgis.utils import (
    get_layer_edit_form,
    normalize_name,
    get_constraint_strength,
    get_attribute_form_container_type,
    get_layer_flags,
    create_field,
    create_fields,
    set_field_default_value,
    set_field_constraints,
    set_field_widget,
)

from qgis.PyQt.QtCore import QMetaType
from qgis.core import (
    QgsFieldConstraints,
    Qgis,
    QgsField,
    QgsMapLayer,
    QgsAttributeEditorContainer,
    QgsAttributeEditorField,
)


@pytest.fixture
def sample_field():
    return QgsField("sample_field", QMetaType.Type.QString, len=255)


@pytest.fixture
def sample_field_def():
    return {
        "id": "sample_field",
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
        "default_value": None,
        "set_default_value_on_update": False,
        "alias": "Sample Field Alias",
        "widget_type": "text",
        "widget_config": {},
    }


@pytest.fixture
def sample_layer_def(sample_field_def):
    integer_field = {
        **sample_field_def,
        "id": "field_integer",
        "name": "Field integer",
        "type": "integer",
        "length": 0,
        "precision": 0,
        "comment": "This is field integer",
    }
    real_field = {
        **sample_field_def,
        "id": "field_real",
        "name": "Field real",
        "type": "real",
        "length": 0,
        "precision": 0,
        "comment": "This is field real",
    }
    bool_field = {
        **sample_field_def,
        "id": "field_bool",
        "name": "Field bool",
        "type": "boolean",
        "length": 0,
        "precision": 0,
        "comment": "This is field bool",
    }
    string_field = {
        **sample_field_def,
        "id": "field_string",
        "name": "Field string",
        "type": "string",
        "length": 0,
        "precision": 0,
        "comment": "This is field string",
    }
    date_field = {
        **sample_field_def,
        "id": "field_date",
        "name": "Field date",
        "type": "date",
        "length": 0,
        "precision": 0,
        "comment": "This is field date",
    }
    datetime_field = {
        **sample_field_def,
        "id": "field_datetime",
        "name": "Field datetime",
        "type": "datetime",
        "length": 0,
        "precision": 0,
        "comment": "This is field datetime",
    }

    return {
        "id": "sample_layer",
        "name": "Sample Layer",
        "type": "vector",
        "data_provider": "gpkg",
        "is_identifiable": False,
        "is_removable": False,
        "is_searchable": False,
        "is_private": False,
        "fields": [
            integer_field,
            real_field,
            bool_field,
            string_field,
            date_field,
            datetime_field,
        ],
        "form_config": {
            "items": [
                {
                    "column_count": 3,
                    "id": "main_tab",
                    "name": "Main",
                    "type": "tab",
                },
                {
                    "background_color": "",
                    "column_count": 2,
                    "id": "basic_info_group",
                    "is_collapsed": True,
                    "name": "Basic Info",
                    "parent_id": "main_tab",
                    "type": "group_box",
                    "visibility_expression": "1 > 0",
                },
                {
                    "id": "caffdaed-fbec-4bf1-a21e-ba84360184e9",
                    "name": "uuid",
                    "parent_id": "main_tab",
                    "type": "field",
                },
                {
                    "id": "61c6b488-9726-4f1b-b6a7-ca3b7c61293b",
                    "name": "name",
                    "parent_id": "basic_info_group",
                    "type": "field",
                },
                {
                    "id": "79002a29-036a-4b1c-baef-49ab49f88a7c",
                    "name": "elevation",
                    "parent_id": "basic_info_group",
                    "type": "field",
                },
                {
                    "id": "c9c7aadc-ff12-4cb0-92a7-f13e0705705a",
                    "name": "variant_type",
                    "parent_id": "basic_info_group",
                    "type": "field",
                },
                {
                    "id": "c5855c64-ef0d-4330-af90-a357a1848016",
                    "name": "created_at",
                    "parent_id": "basic_info_group",
                    "type": "field",
                },
                {
                    "id": "45416464-85cd-43f1-bfa9-b96c15cc76a0",
                    "name": "updated_at",
                    "parent_id": "basic_info_group",
                    "type": "field",
                },
                {
                    "id": "attachment_tab",
                    "name": "Attachment",
                    "type": "tab",
                },
                {
                    "id": "5b93e54f-0f40-4524-aee2-78c6810d7d8a",
                    "name": "attachment",
                    "parent_id": "attachment_tab",
                    "type": "field",
                },
            ]
        },
    }


@pytest.fixture
def pissi(sample_field_def):
    return sample_field_def["widget_type"]


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
        assert (
            strength == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthNotSet
        )

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
        assert (
            not constraints.constraints()
            & QgsFieldConstraints.Constraint.ConstraintNotNull
        )
        assert (
            not constraints.constraints()
            & QgsFieldConstraints.Constraint.ConstraintUnique
        )
        assert (
            not constraints.constraints()
            & QgsFieldConstraints.Constraint.ConstraintExpression
        )

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
        assert (
            constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintNotNull
        )
        assert (
            constraints.constraintStrength(
                QgsFieldConstraints.Constraint.ConstraintNotNull
            )
            == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthSoft
        )

        assert (
            not constraints.constraints()
            & QgsFieldConstraints.Constraint.ConstraintUnique
        )
        assert (
            not constraints.constraints()
            & QgsFieldConstraints.Constraint.ConstraintExpression
        )

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
        assert (
            constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintUnique
        )
        assert (
            constraints.constraintStrength(
                QgsFieldConstraints.Constraint.ConstraintUnique
            )
            == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard
        )

        assert (
            not constraints.constraints()
            & QgsFieldConstraints.Constraint.ConstraintNotNull
        )
        assert (
            not constraints.constraints()
            & QgsFieldConstraints.Constraint.ConstraintExpression
        )

    def test_set_field_constraints_with_expression(
        self, sample_field, sample_field_def
    ):
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
        assert (
            constraints.constraints()
            & QgsFieldConstraints.Constraint.ConstraintExpression
        )
        assert (
            constraints.constraintStrength(
                QgsFieldConstraints.Constraint.ConstraintExpression
            )
            == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard
        )
        assert constraints.constraintDescription() == "Random constraint message"

        assert (
            not constraints.constraints()
            & QgsFieldConstraints.Constraint.ConstraintNotNull
        )
        assert (
            not constraints.constraints()
            & QgsFieldConstraints.Constraint.ConstraintUnique
        )

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
        assert (
            constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintNotNull
        )
        assert (
            constraints.constraintStrength(
                QgsFieldConstraints.Constraint.ConstraintNotNull
            )
            == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthSoft
        )

        # Check Unique constraint
        assert (
            constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintUnique
        )
        assert (
            constraints.constraintStrength(
                QgsFieldConstraints.Constraint.ConstraintUnique
            )
            == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard
        )

        # Check Expression constraint
        assert (
            constraints.constraints()
            & QgsFieldConstraints.Constraint.ConstraintExpression
        )
        assert (
            constraints.constraintStrength(
                QgsFieldConstraints.Constraint.ConstraintExpression
            )
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
                    "min": 10,
                    "max": 20,
                    "step": 2,
                    "precision": 3,
                    "suffix": " m",
                    "style": "slider",
                    "allow_null": False,
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
                    "is_document_viewer_enabled": True,
                    "document_viewer_height": 100,
                    "document_viewer_width": 100,
                    "use_file_widget": True,
                    "show_file_widget_button": True,
                    "file_widget_filter": "*.png",
                    "use_relative_storage": True,
                    "storage_auth_config_id": "abc",
                    "storage_mode": 0,
                    "storage_type": None,
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

    def test_get_layer_flags_to_false(self, sample_layer_def):
        """Test getting layer flags from LayerDef."""

        sample_layer_def.update(
            {
                "is_identifiable": False,
                "is_removable": False,
                "is_searchable": False,
                "is_private": False,
            }
        )

        flags = QgsMapLayer.LayerFlags()

        flags = get_layer_flags(flags, sample_layer_def)  # type: ignore

        assert not flags & QgsMapLayer.LayerFlag.Identifiable  # type: ignore
        assert not flags & QgsMapLayer.LayerFlag.Removable  # type: ignore
        assert not flags & QgsMapLayer.LayerFlag.Searchable  # type: ignore
        assert not flags & QgsMapLayer.LayerFlag.Private  # type: ignore

    def test_get_layer_flags_to_true(self, sample_layer_def):
        """Test getting layer flags from LayerDef."""

        sample_layer_def.update(
            {
                "is_identifiable": True,
                "is_removable": True,
                "is_searchable": True,
                "is_private": True,
            }
        )

        flags = QgsMapLayer.LayerFlags()

        flags = get_layer_flags(flags, sample_layer_def)  # type: ignore

        assert flags & QgsMapLayer.LayerFlag.Identifiable  # type: ignore
        assert flags & QgsMapLayer.LayerFlag.Removable  # type: ignore
        assert flags & QgsMapLayer.LayerFlag.Searchable  # type: ignore
        assert flags & QgsMapLayer.LayerFlag.Private  # type: ignore

    def test_set_layer_field_configurations(self, sample_layer_def):
        """Test setting layer field configurations."""

        fields = create_fields(sample_layer_def)

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

    def test_get_layer_edit_form(self, sample_layer_def):
        """Test getting layer edit form configuration."""

        fields = create_fields(sample_layer_def)
        form_config = get_layer_edit_form(fields, sample_layer_def)

        assert form_config.layout() == Qgis.AttributeFormLayout.DragAndDrop
        assert len(form_config.tabs()) == 2

        tabs = form_config.tabs()

        assert tabs[0].name() == "Main"
        assert tabs[1].name() == "Attachment"

        assert isinstance(tabs[0], QgsAttributeEditorContainer)
        assert len(tabs[0].children()) == 2
        assert isinstance(tabs[1], QgsAttributeEditorContainer)
        assert len(tabs[1].children()) == 1

        basic_info_group = tabs[0].children()[0]

        assert isinstance(basic_info_group, QgsAttributeEditorContainer)
        assert basic_info_group.name() == "Basic Info"
        assert basic_info_group.type() == Qgis.AttributeEditorContainerType.GroupBox
        assert basic_info_group.columnCount() == 2
        assert basic_info_group.visibilityExpression().data().expression() == "1 > 0"
        assert len(basic_info_group.children()) == 5

        assert isinstance(basic_info_group.children()[0], QgsAttributeEditorField)
        assert basic_info_group.children()[0].name() == "name"
        assert isinstance(basic_info_group.children()[1], QgsAttributeEditorField)
        assert basic_info_group.children()[1].name() == "elevation"
        assert isinstance(basic_info_group.children()[2], QgsAttributeEditorField)
        assert basic_info_group.children()[2].name() == "variant_type"
        assert isinstance(basic_info_group.children()[3], QgsAttributeEditorField)
        assert basic_info_group.children()[3].name() == "created_at"
        assert isinstance(basic_info_group.children()[4], QgsAttributeEditorField)
        assert basic_info_group.children()[4].name() == "updated_at"

        assert isinstance(tabs[0].children()[1], QgsAttributeEditorField)
        assert tabs[0].children()[1].name() == "uuid"
