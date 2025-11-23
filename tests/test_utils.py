import pytest

from json2qgis.utils import (
    normalize_name,
    get_constraint_strength,
    get_attribute_form_container_type,
    create_field,
    set_field_default_value,
)
from json2qgis.types import (
    FieldDef,
)

from qgis.PyQt.QtCore import QMetaType
from qgis.core import QgsFieldConstraints, Qgis, QgsField


@pytest.fixture
def sample_field():
    return QgsField("sample_field", QMetaType.Type.QString, len=255)


@pytest.fixture
def sample_field_def():
    return {
        "id": "sample_field",
        "name": "Sample Field",
        "type": "string",
        "length": 255,
        "precision": 0,
        "comment": "This is a sample field",
        "is_not_null": True,
        "is_not_null_strength": "hard",
        "constraint_expression": "",
        "constraint_expression_description": "",
        "constraint_expression_strength": "not_set",
        "is_unique": False,
        "unique_strength": "not_set",
        "default_value": None,
        "set_default_value_on_update": False,
        "alias": "Sample Field Alias",
        "widget_type": "text",
        "widget_config": {},
    }


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

    def test_create_field_def_as_string(self):
        """Test creation of a FieldDef TypedDict."""
        field_def: FieldDef = {
            "id": "field_string",
            "name": "Field String",
            "type": "string",
            "length": 255,
            "precision": 0,
            "comment": "This is a test string field",
            "is_not_null": True,
            "is_not_null_strength": "hard",
            "constraint_expression": "",
            "constraint_expression_description": "",
            "constraint_expression_strength": "not_set",
            "is_unique": False,
            "unique_strength": "not_set",
            "default_value": None,
            "set_default_value_on_update": False,
            "alias": "Field One",
            "widget_type": "text",
            "widget_config": {},
        }

        field = create_field(field_def)

        assert field.name() == "Field String"
        assert field.type() == QMetaType.Type.QString
        assert field.length() == 255
        assert field.precision() == 0
        assert field.comment() == "This is a test string field"

    def test_create_field_def_as_integer(self):
        """Test creation of a FieldDef TypedDict."""
        field_def: FieldDef = {
            "id": "field_integer",
            "name": "Field Integer",
            "type": "integer",
            "length": 3,
            "precision": 0,
            "comment": "This is a test integer field",
            "is_not_null": True,
            "is_not_null_strength": "hard",
            "constraint_expression": "",
            "constraint_expression_description": "",
            "constraint_expression_strength": "not_set",
            "is_unique": False,
            "unique_strength": "not_set",
            "default_value": None,
            "set_default_value_on_update": False,
            "alias": "Field One",
            "widget_type": "text",
            "widget_config": {},
        }

        field = create_field(field_def)

        assert field.name() == "Field Integer"
        assert field.type() == QMetaType.Type.Int
        assert field.length() == 3
        assert field.precision() == 0
        assert field.comment() == "This is a test integer field"

    def test_create_field_def_as_real(self):
        """Test creation of a FieldDef TypedDict."""
        field_def: FieldDef = {
            "id": "field_real",
            "name": "Field Real",
            "type": "real",
            "length": 3,
            "precision": 0,
            "comment": "This is a test real field",
            "is_not_null": True,
            "is_not_null_strength": "hard",
            "constraint_expression": "",
            "constraint_expression_description": "",
            "constraint_expression_strength": "not_set",
            "is_unique": False,
            "unique_strength": "not_set",
            "default_value": None,
            "set_default_value_on_update": False,
            "alias": "Field One",
            "widget_type": "text",
            "widget_config": {},
        }

        field = create_field(field_def)

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

    # def test_set_field_constraints_with_constraints(sample_field, sample_field_def):
    #     """Test setting constraints for a field."""

    #     sample_field_def.update(
    #         {
    #             "is_not_null": True,
    #             "is_not_null_strength": "hard",
    #             "is_unique": True,
    #             "unique_strength": "soft",
    #             "constraint_expression": "\"sample_field\" > 0",
    #             "constraint_expression_description": "Value must be greater than 0",
    #             "constraint_expression_strength": "hard",
    #         }
    #     )
    #     sample_field = cast(QgsField, sample_field)

    #     set_field_constraints(sample_field, sample_field_def)

    #     constraints = sample_field.constraints()

    #     # Check Not Null constraint
    #     assert constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintNotNull
    #     assert (
    #         constraints.constraintStrength(
    #             QgsFieldConstraints.Constraint.ConstraintNotNull
    #         )
    #         == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard
    #     )

    #     # Check Unique constraint
    #     assert constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintUnique
    #     assert (
    #         constraints.constraintStrength(
    #             QgsFieldConstraints.Constraint.ConstraintUnique
    #         )
    #         == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthSoft
    #     )

    #     # Check Expression constraint
    #     assert constraints.constraints() & QgsFieldConstraints.Constraint.ConstraintExpression
    #     assert (
    #         constraints.constraintStrength(
    #             QgsFieldConstraints.Constraint.ConstraintExpression
    #         )
    #         == QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard
    #     )
