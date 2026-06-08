import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import pytest
from qgis.core import (
    QgsAttributeEditorContainer,
    QgsAttributeEditorField,
    QgsVectorLayer,
)

from convert2qgis.json2qgis.generate import (
    generate_field_def,
    generate_form_item_def,
    generate_uuid_field_def,
    generate_vector_dataset_def,
)
from convert2qgis.json2qgis.utils import (
    create_fields,
    get_layer_edit_form,
    set_layer_virtual_fields,
)
from convert2qgis.xlsform2qgis import xlsform2qgis as xlsform2qgis_module
from convert2qgis.xlsform2qgis.errors import XlsformSheetParserError
from convert2qgis.xlsform2qgis.expressions.functions import SUPPORTED_FUNCTIONS
from convert2qgis.xlsform2qgis.qgis_utils import set_survey_features
from convert2qgis.xlsform2qgis.sheet_parser import ParsedSheetRow
from convert2qgis.xlsform2qgis.xlsform2qgis import (
    XlsformConverter,
    parse_xlsform_sheets,
)

if TYPE_CHECKING:
    from convert2qgis.json2qgis.type_defs import VectorDatasetDef


def format_selected_expr(field_name: str, value: str) -> str:
    expression: str = SUPPORTED_FUNCTIONS["selected"].expression  # type: ignore

    return expression.format("selected", f'"{field_name}"', f"'{value}'")


def to_parsed_sheet_rows(rows: list[dict[str, "str | None"]]) -> list[ParsedSheetRow]:
    return [ParsedSheetRow(**row, idx=i) for i, row in enumerate(rows)]


def generate_survey_row(**kwargs) -> dict[str, "str | None"]:
    return {
        "type": "",
        "name": "",
        "label": "",
        "calculation": "",
        "relevant": "",
        "choice_filter": "",
        "parameters": "",
        "constraint": "",
        "constraint_message": "",
        "required": "",
        "default": "",
        "is_read_only": "",
        "trigger": "",
        "appearance": "",
        **kwargs,
    }


@pytest.fixture
def converter():
    survey_sheet = MagicMock()
    choices_sheet = MagicMock()
    settings_sheet = MagicMock()

    return XlsformConverter(
        survey_sheet,
        choices_sheet,
        settings_sheet,
        settings={
            "basemap_url": "",
            "form_group_type": "group_box",
        },
    )


class TestConverter:
    def test_convert_xlsform_writes_json_without_output_dir(
        self, tmp_path, monkeypatch
    ):
        project_json = {
            "version": "1.0",
            "project": {"title": "Survey"},
            "datasets": [],
            "legend_tree": {},
            "relations": [],
            "polymorphic_relations": [],
        }
        json_filename = tmp_path / "nested" / "survey.json"

        monkeypatch.setattr(
            xlsform2qgis_module,
            "parse_xlsform_sheets",
            lambda *_args, **_kwargs: (MagicMock(), MagicMock(), MagicMock()),
        )
        converter = MagicMock()
        converter.is_valid.return_value = True
        converter.to_json.return_value = project_json
        monkeypatch.setattr(
            xlsform2qgis_module, "XlsformConverter", lambda *_args, **_kwargs: converter
        )

        result = xlsform2qgis_module.convert_xlsform(
            "survey.xlsx",
            json_filename=json_filename,
        )

        assert result == project_json
        assert json.loads(json_filename.read_text()) == project_json

    def test_set_survey_features_skips_multipoint_source_for_point_layer(self, caplog):
        project = MagicMock()
        survey_layer = QgsVectorLayer("Point?crs=EPSG:4326", "survey_layer", "memory")
        source_layer = QgsVectorLayer("MultiPoint?crs=EPSG:4326", "source", "memory")
        project.mapLayer.return_value = survey_layer
        caplog.set_level(logging.WARNING, logger="convert2qgis.xlsform2qgis.qgis_utils")

        extent = set_survey_features(project, source_layer)

        assert extent is None
        assert survey_layer.featureCount() == 0
        assert [
            record.message
            for record in caplog.records
            if "different geometry type" in record.message
        ] == [
            "The provided features have a different geometry type than the survey layer within the generated project when trying to set geometries, skipping this step."
        ]

    def test_to_json_sets_largest_image_max_pixels_project_property(
        self, converter, caplog
    ):
        caplog.set_level(logging.WARNING)
        converter.survey_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                generate_survey_row(
                    type="image",
                    name="photo_001",
                    parameters="max-pixels=1024",
                ),
                generate_survey_row(
                    type="image",
                    name="photo_002",
                    parameters="max-pixels=2048",
                ),
            ]
        )

        project_json = converter.to_json()

        assert (
            project_json["project"]["custom_properties"][
                "qfieldsync/maximumImageWidthHeight"
            ]
            == 2048
        )
        assert [
            record.message
            for record in caplog.records
            if "max-pixels parameter of varying values" in record.message
        ] == [
            "Due to the presence of a mix of image attributes having max-pixels parameter of varying values, the largest max-pixels value will be applied"
        ]

    def test_get_choices_by_list(self, converter: XlsformConverter):
        converter.choices_sheet.__iter__.return_value = to_parsed_sheet_rows(  # type: ignore
            [
                {
                    "list_name": "list_001",
                    "name": "value_001_001",
                    "label": "label_001_001",
                },
                {
                    "list_name": "list_001",
                    "name": "value_001_002",
                    "label": "label_001_002",
                },
                {
                    "list_name": "list_002",
                    "name": "value_002_001",
                    "label": "label_002_001",
                },
            ]
        )

        choices_by_list = converter._get_choices_by_list()

        assert choices_by_list == {
            "list_001": [
                {
                    "name": "",
                    "label": "",
                    "list_name": "list_001",
                },
                {
                    "name": "value_001_001",
                    "label": "label_001_001",
                    "list_name": "list_001",
                },
                {
                    "name": "value_001_002",
                    "label": "label_001_002",
                    "list_name": "list_001",
                },
            ],
            "list_002": [
                {
                    "name": "",
                    "label": "",
                    "list_name": "list_002",
                },
                {
                    "name": "value_002_001",
                    "label": "label_002_001",
                    "list_name": "list_002",
                },
            ],
        }

    def test_get_choices_by_list_uniquifies_duplicate_labels(
        self, converter: XlsformConverter
    ):
        converter.choices_sheet.__iter__.return_value = to_parsed_sheet_rows(  # type: ignore
            [
                {
                    "list_name": "list_001",
                    "name": "value_001_001",
                    "label": "Same Label",
                },
                {
                    "list_name": "list_001",
                    "name": "value_001_002",
                    "label": "Same Label",
                },
                {
                    "list_name": "list_001",
                    "name": "value_001_003",
                    "label": "Same Label",
                },
            ]
        )

        choices_by_list = converter._get_choices_by_list()

        assert [choice.label for choice in choices_by_list["list_001"]] == [
            "",
            "Same Label",
            "Same Label (2)",
            "Same Label (3)",
        ]

    def test_get_choices_datasets(self, converter):
        converter.choices_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                {
                    "list_name": "list_001",
                    "name": "value_001_001",
                    "label": "label_001_001",
                },
                {
                    "list_name": "list_001",
                    "name": "value_001_002",
                    "label": "label_001_002",
                },
                {
                    "list_name": "list_002",
                    "name": "value_002_001",
                    "label": "label_002_001",
                },
            ]
        )

        choices_by_list = converter._get_choices_by_list()
        choices_datasets = converter._get_choices_datasets()
        choices_data_by_list = {
            list_name: [
                {
                    key: value
                    for key, value in choice.to_dict().items()
                    if key not in ("list_name", "additional_columns")
                }
                for choice in choices
            ]
            for list_name, choices in choices_by_list.items()
        }

        assert choices_datasets == [
            generate_vector_dataset_def(
                name="list_list_001",
                layer_id=choices_datasets[0].layer_id,
                geometry_type="NoGeometry",
                crs="",
                custom_properties={
                    "QFieldSync/action": "copy",
                    "QFieldSync/cloud_action": "no_action",
                },
                is_private=True,
                is_identifiable=False,
                is_searchable=False,
                is_removable=False,
                data=choices_data_by_list.get("list_001", []),
                fields=[
                    generate_field_def(
                        field_id=choices_datasets[0].fields[0].field_id,
                        name="name",
                        type="string",
                        widget_type="TextEdit",
                    ),
                    generate_field_def(
                        field_id=choices_datasets[0].fields[1].field_id,
                        name="label",
                        type="string",
                        widget_type="TextEdit",
                    ),
                ],
            ),
            generate_vector_dataset_def(
                name="list_list_002",
                layer_id=choices_datasets[1].layer_id,
                geometry_type="NoGeometry",
                crs="",
                custom_properties={
                    "QFieldSync/action": "copy",
                    "QFieldSync/cloud_action": "no_action",
                },
                is_private=True,
                is_identifiable=False,
                is_searchable=False,
                is_removable=False,
                data=choices_data_by_list.get("list_002", []),
                fields=[
                    generate_field_def(
                        field_id=choices_datasets[1].fields[0].field_id,
                        name="name",
                        type="string",
                        widget_type="TextEdit",
                    ),
                    generate_field_def(
                        field_id=choices_datasets[1].fields[1].field_id,
                        name="label",
                        type="string",
                        widget_type="TextEdit",
                    ),
                ],
            ),
        ]

    def test_get_choices_datasets_flattens_additional_columns(self, converter):
        converter.choices_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                {
                    "list_name": "list_001",
                    "name": "value_001_001",
                    "label": "label_001_001",
                    "external_id": "external_001_001",
                },
                {
                    "list_name": "list_001",
                    "name": "value_001_002",
                    "label": "label_001_002",
                    "external_id": "external_001_002",
                },
            ]
        )

        [choices_dataset] = converter._get_choices_datasets()

        assert [field.name for field in choices_dataset.fields] == [
            "name",
            "label",
            "external_id",
        ]
        assert choices_dataset.data == [
            {
                "name": "",
                "label": "",
                "external_id": None,
            },
            {
                "name": "value_001_001",
                "label": "label_001_001",
                "external_id": "external_001_001",
            },
            {
                "name": "value_001_002",
                "label": "label_001_002",
                "external_id": "external_001_002",
            },
        ]
        assert all("external_id" in record for record in choices_dataset.data)
        assert all("list_name" not in record for record in choices_dataset.data)
        assert all(
            "additional_columns" not in record for record in choices_dataset.data
        )

    def test_get_choices_datasets_skips_empty_additional_columns(self, converter):
        converter.choices_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                {
                    "list_name": "list_001",
                    "name": "value_001_001",
                    "label": "label_001_001",
                    "external_id": None,
                },
                {
                    "list_name": "list_001",
                    "name": "value_001_002",
                    "label": "label_001_002",
                    "external_id": None,
                },
            ]
        )

        [choices_dataset] = converter._get_choices_datasets()

        assert [field.name for field in choices_dataset.fields] == [
            "name",
            "label",
        ]
        assert choices_dataset.data == [
            {
                "name": "",
                "label": "",
            },
            {
                "name": "value_001_001",
                "label": "label_001_001",
            },
            {
                "name": "value_001_002",
                "label": "label_001_002",
            },
        ]
        assert all("external_id" not in record for record in choices_dataset.data)

    def test_xlsform_form_group_type_default(self):
        survey_sheet = MagicMock()
        choices_sheet = MagicMock()
        settings_sheet = MagicMock()

        converter = XlsformConverter(survey_sheet, choices_sheet, settings_sheet)

        assert converter._form_group_type == "group_box"

        # empty stack means the next container is a root form item
        assert converter.get_form_group_type() == "tab"

        # None marks the current dataset root
        converter._container_ids.append(None)
        assert converter.get_form_group_type() == "tab"

        # an item id marks a nested form container
        converter._container_ids.append("item_container_id_here")
        assert converter.get_form_group_type() == "group_box"

    def test_xlsform_form_group_type_configured(self):
        survey_sheet = MagicMock()
        choices_sheet = MagicMock()
        settings_sheet = MagicMock()

        converter = XlsformConverter(
            survey_sheet,
            choices_sheet,
            settings_sheet,
            settings={
                "form_group_type": "tab",
            },
        )

        assert converter._form_group_type == "tab"

        # empty stack means the next container is a root form item
        assert converter.get_form_group_type() == "tab"

        # None marks the current dataset root
        converter._container_ids.append(None)
        assert converter.get_form_group_type() == "tab"

        # an item id marks a nested form container
        converter._container_ids.append("item_container_id_here")

        assert converter.get_form_group_type() == "tab"

    def test_xlsform_form_group_type_without_tab_grouping(self):
        survey_sheet = MagicMock()
        choices_sheet = MagicMock()
        settings_sheet = MagicMock()

        converter = XlsformConverter(
            survey_sheet,
            choices_sheet,
            settings_sheet,
            settings={
                "form_group_type": "group_box",
                "use_groups_as_tabs": False,
            },
        )

        assert converter._form_group_type == "group_box"
        assert converter.get_form_group_type() == "group_box"

        # simulate there is a new group in the survey sheet
        converter._container_ids.append("item_container_id_here")

        assert converter.get_form_group_type() == "group_box"

    def test_xlsform_select_type_details_reject_spaces(self, converter):
        converter.survey_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                generate_survey_row(
                    type="select_one invalid list",
                    name="choice_field",
                    label="Choice field",
                )
            ]
        )

        with pytest.raises(
            XlsformSheetParserError,
            match='The type details of field "choice_field" of type "select_one": invalid list',
        ):
            converter.convert()

    @pytest.mark.parametrize(
        ("type_suffix", "warning_suffix"),
        [
            ("or_other", "or_other"),
            ("or other", "or other"),
        ],
    )
    def test_xlsform_select_or_other_suffix_uses_base_choice_list(
        self, converter, caplog, type_suffix, warning_suffix
    ):
        caplog.set_level(logging.WARNING, logger="convert2qgis.xlsform2qgis.widgets")
        converter.choices_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                {
                    "list_name": "list_001",
                    "name": "value_001",
                    "label": "Value 001",
                },
            ]
        )
        converter.survey_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                generate_survey_row(
                    type=f"select_one list_001 {type_suffix}",
                    name="choice_field",
                    label="Choice field",
                )
            ]
        )

        converter.convert()

        choices_layer = converter.vector_datasets[0]
        survey_layer = converter.vector_datasets[1]

        assert survey_layer.fields[1].widget_config["Layer"] == choices_layer.layer_id
        assert survey_layer.fields[1].widget_config["LayerName"] == "list_001"
        assert [
            record.message
            for record in caplog.records
            if "not supported yet" in record.message
        ] == [
            f'The "{warning_suffix}" suffix is not supported yet for fields of type "select_one": select_one list_001 {type_suffix}'
        ]

    def test_xlsform_with_text_field(self, converter):
        converter.survey_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                generate_survey_row(
                    type="text",
                    name="field_001",
                    label="Field 001",
                )
            ]
        )

        converter.convert()

        assert len(converter.vector_datasets) == 1

        survey_layer = converter.vector_datasets[0]

        assert len(survey_layer.fields) == 2
        assert survey_layer.fields[0] == generate_uuid_field_def(
            field_id=survey_layer.fields[0].field_id,
        )
        assert survey_layer.fields[1] == generate_field_def(
            field_id=survey_layer.fields[1].field_id,
            type="string",
            name="field_001",
            alias="Field 001",
            widget_type="TextEdit",
        )

        assert len(survey_layer.form_config) == 1

        survey_form_tab = survey_layer.form_config[0].item_id

        assert survey_layer.form_config[0] == generate_form_item_def(
            item_id=survey_form_tab,
            label="Survey",
            type="tab",
            children=[
                generate_form_item_def(
                    item_id=survey_layer.form_config[0].children[0].item_id,
                    field_name="field_001",
                    type="field",
                    is_label_on_top=True,
                )
            ],
        )

    def test_xlsform_with_time_field(self, converter):
        converter.survey_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                generate_survey_row(
                    type="time",
                    name="appointment_time",
                    label="Appointment time",
                )
            ]
        )

        converter.convert()

        assert len(converter.vector_datasets) == 1

        survey_layer = converter.vector_datasets[0]

        assert len(survey_layer.fields) == 2
        assert survey_layer.fields[0] == generate_uuid_field_def(
            field_id=survey_layer.fields[0].field_id,
        )
        assert survey_layer.fields[1] == generate_field_def(
            field_id=survey_layer.fields[1].field_id,
            type="time",
            name="appointment_time",
            alias="Appointment time",
            widget_type="DateTime",
            widget_config={
                "field_format_overwrite": True,
                "display_format": "HH:mm:ss",
                "field_format": "HH:mm:ss",
                "allow_null": True,
                "calendar_popup": True,
            },
        )

        assert len(survey_layer.form_config) == 1
        assert survey_layer.form_config[0] == generate_form_item_def(
            item_id=survey_layer.form_config[0].item_id,
            label="Survey",
            type="tab",
            children=[
                generate_form_item_def(
                    item_id=survey_layer.form_config[0].children[0].item_id,
                    field_name="appointment_time",
                    type="field",
                    is_label_on_top=True,
                )
            ],
        )

    def test_xlsform_label(self, converter):
        converter.survey_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                generate_survey_row(
                    type="text",
                    name="field_001",
                ),
                generate_survey_row(
                    type="text",
                    name="field_002",
                    label="Field 002",
                ),
                generate_survey_row(
                    **{
                        "type": "text",
                        "name": "field_003",
                        "label": "Field 003",
                        "label::english": "Field English 003",
                        "label::french": "Field French 003",
                    }
                ),
            ]
        )
        converter.settings_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [{"default_language": "English"}]
        )

        converter._xlsform_settings = converter._get_xlsform_settings()
        converter._languages = "English"
        converter.convert()

        assert len(converter.vector_datasets) == 1

        survey_layer = converter.vector_datasets[0]

        assert len(survey_layer.fields) == 4

        assert survey_layer.fields[0] == generate_uuid_field_def(
            field_id=survey_layer.fields[0].field_id,
        )
        assert survey_layer.fields[1] == generate_field_def(
            field_id=survey_layer.fields[1].field_id,
            type="string",
            name="field_001",
            widget_type="TextEdit",
        )
        assert survey_layer.fields[2] == generate_field_def(
            field_id=survey_layer.fields[2].field_id,
            type="string",
            name="field_002",
            alias="Field 002",
            widget_type="TextEdit",
        )
        assert survey_layer.fields[3] == generate_field_def(
            field_id=survey_layer.fields[3].field_id,
            type="string",
            name="field_003",
            alias="Field English 003",
            widget_type="TextEdit",
        )

    def test_xlsform_multilingual_label(self, converter):
        converter.survey_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                generate_survey_row(
                    type="text",
                    name="field_001",
                ),
                generate_survey_row(
                    type="text",
                    name="field_002",
                    label="Field 002",
                ),
                generate_survey_row(
                    **{
                        "type": "text",
                        "name": "field_003",
                        "label": "Field 003",
                        "label::english": "Field English 003",
                        "label::french": "Field French 003",
                    }
                ),
            ]
        )
        converter.settings_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [{"default_language": "English"}]
        )

        converter._xlsform_settings = converter._get_xlsform_settings()
        converter._languages = "French,English"
        converter.convert()

        assert len(converter.vector_datasets) == 1

        survey_layer = converter.vector_datasets[0]

        assert len(survey_layer.fields) == 4

        assert survey_layer.fields[0] == generate_uuid_field_def(
            field_id=survey_layer.fields[0].field_id,
        )
        assert survey_layer.fields[1] == generate_field_def(
            field_id=survey_layer.fields[1].field_id,
            type="string",
            name="field_001",
            widget_type="TextEdit",
        )
        assert survey_layer.fields[2] == generate_field_def(
            field_id=survey_layer.fields[2].field_id,
            type="string",
            name="field_002",
            alias="Field 002",
            widget_type="TextEdit",
        )
        assert survey_layer.fields[3] == generate_field_def(
            field_id=survey_layer.fields[3].field_id,
            type="string",
            name="field_003",
            alias="Field French 003 | Field English 003",
            widget_type="TextEdit",
        )

    def test_xlsform_duplicate_labels_are_uniquified(self, converter):
        converter.survey_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                generate_survey_row(
                    type="text",
                    name="field_001",
                    label="Field",
                ),
                generate_survey_row(
                    type="text",
                    name="field_002",
                    label="Field",
                ),
                generate_survey_row(
                    type="calculate",
                    name="field_003",
                    label="Field",
                    calculation="1 + 2",
                ),
            ]
        )

        converter.convert()

        assert len(converter.vector_datasets) == 1

        survey_layer = converter.vector_datasets[0]

        assert [field.alias for field in survey_layer.fields] == [
            "UUID",
            "Field",
            "Field (2)",
            "Field (3)",
        ]
        assert survey_layer.fields[3].name == "field_003"
        assert survey_layer.fields[3].widget_type == "TextEdit"
        assert survey_layer.virtual_fields == []

    def test_xlsform_duplicate_labels_can_keep_original_labels(self, caplog):
        survey_sheet = MagicMock()
        choices_sheet = MagicMock()
        settings_sheet = MagicMock()
        converter = XlsformConverter(
            survey_sheet,
            choices_sheet,
            settings_sheet,
            settings={
                "basemap_url": "",
                "show_unique_label": False,
            },
        )
        caplog.set_level(logging.DEBUG, logger="convert2qgis.xlsform2qgis.xlsform2qgis")
        converter.survey_sheet.__iter__.return_value = to_parsed_sheet_rows(  # type: ignore[attr-defined]
            [
                generate_survey_row(
                    type="text",
                    name="field_001",
                    label="Field",
                ),
                generate_survey_row(
                    type="text",
                    name="field_002",
                    label="Field",
                ),
                generate_survey_row(
                    type="calculate",
                    name="field_003",
                    label="Field",
                    calculation="1 + 2",
                ),
            ]
        )

        converter.convert()

        assert len(converter.vector_datasets) == 1

        survey_layer = converter.vector_datasets[0]

        assert [field.alias for field in survey_layer.fields] == [
            "UUID",
            "Field",
            "Field",
            "Field",
        ]
        assert survey_layer.fields[3].name == "field_003"
        assert survey_layer.fields[3].widget_type == "TextEdit"
        assert survey_layer.virtual_fields == []
        assert [
            record.message
            for record in caplog.records
            if "Duplicate label" in record.message
        ] == [
            "Duplicate label `Field` found in dataset `Survey`!",
            "Duplicate label `Field` found in dataset `Survey`!",
            "Duplicate label `Field` found in dataset `Survey`!",
        ]

    def test_xlsform_calculate_rows_are_fields(self, converter):
        converter.survey_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                generate_survey_row(
                    type="calculate",
                    name="total_pop",
                    label="Total population",
                    calculation="1 + 2",
                ),
                generate_survey_row(
                    type="calculate",
                    name="internal_total",
                    calculation="${total_pop} + 1",
                ),
            ]
        )

        converter.convert()

        assert len(converter.vector_datasets) == 1

        survey_layer = converter.vector_datasets[0]

        assert [field.name for field in survey_layer.fields] == [
            "uuid",
            "total_pop",
            "internal_total",
        ]
        assert survey_layer.virtual_fields == []
        assert survey_layer.fields[1] == generate_field_def(
            field_id=survey_layer.fields[1].field_id,
            type="string",
            name="total_pop",
            alias="Total population",
            widget_type="TextEdit",
            default_value="1 + 2",
            set_default_value_on_update=True,
        )
        assert survey_layer.fields[2] == generate_field_def(
            field_id=survey_layer.fields[2].field_id,
            type="string",
            name="internal_total",
            widget_type="Hidden",
            default_value='"total_pop" + 1',
            set_default_value_on_update=True,
        )
        assert len(survey_layer.form_config) == 1
        assert survey_layer.form_config[0] == generate_form_item_def(
            item_id=survey_layer.form_config[0].item_id,
            label="Survey",
            type="tab",
            children=[
                generate_form_item_def(
                    item_id=survey_layer.form_config[0].children[0].item_id,
                    field_name="total_pop",
                    type="field",
                    is_read_only=True,
                    is_label_on_top=True,
                ),
                generate_form_item_def(
                    item_id=survey_layer.form_config[0].children[1].item_id,
                    field_name="internal_total",
                    type="field",
                    show_label=False,
                    is_read_only=True,
                    is_label_on_top=True,
                ),
            ],
        )

    def test_prune_field_definition_downgrades_hidden_hard_constraints(
        self, converter, caplog
    ):
        caplog.set_level(logging.DEBUG, logger="convert2qgis.xlsform2qgis.xlsform2qgis")
        field = generate_field_def(
            name="hidden_field",
            widget_type="Hidden",
            is_not_null_strength="hard",
            constraint_expression_strength="hard",
            is_unique_strength="hard",
        )

        converter._prune_field_definition(field)

        assert field.is_not_null_strength == "soft"
        assert field.constraint_expression_strength == "soft"
        assert field.is_unique_strength == "soft"
        assert [
            record.message
            for record in caplog.records
            if "hidden_field" in record.message
        ] == [
            "Field `hidden_field` has not null constraint strength set to `hard` but has a `Hidden` widget; this will prevent saving the form, therefore the constraint strength will be downgraded to `soft`!",
            "Field `hidden_field` has constraint expression strength set to `hard` but has a `Hidden` widget; this is not a valid combination and the constraint expression will be downgraded to `soft`!",
            "Field `hidden_field` has unique constraint strength set to `hard` but has a `Hidden` widget; this is not a valid combination and the unique constraint will be downgraded to `soft`!",
        ]

    def test_prune_field_definition_keeps_visible_field_constraints(
        self, converter, caplog
    ):
        caplog.set_level(logging.WARNING)
        field = generate_field_def(
            name="visible_field",
            widget_type="TextEdit",
            is_not_null_strength="hard",
            constraint_expression_strength="hard",
            is_unique_strength="hard",
        )

        converter._prune_field_definition(field)

        assert field.is_not_null_strength == "hard"
        assert field.constraint_expression_strength == "hard"
        assert field.is_unique_strength == "hard"
        assert [
            record.message
            for record in caplog.records
            if "visible_field" in record.message
        ] == []

    def test_prune_field_definition_keeps_hidden_not_set_constraints(
        self, converter, caplog
    ):
        caplog.set_level(logging.WARNING)
        field = generate_field_def(
            name="hidden_field",
            widget_type="Hidden",
            is_not_null_strength="not_set",
            constraint_expression_strength="not_set",
            is_unique_strength="not_set",
        )

        converter._prune_field_definition(field)

        assert field.is_not_null_strength == "not_set"
        assert field.constraint_expression_strength == "not_set"
        assert field.is_unique_strength == "not_set"
        assert [
            record.message
            for record in caplog.records
            if "hidden_field" in record.message
        ] == []

    def test_prune_field_definition_keeps_hidden_soft_constraints(
        self, converter, caplog
    ):
        caplog.set_level(logging.WARNING)
        field = generate_field_def(
            name="hidden_field",
            widget_type="Hidden",
            is_not_null_strength="soft",
            constraint_expression_strength="soft",
            is_unique_strength="soft",
        )

        converter._prune_field_definition(field)

        assert field.is_not_null_strength == "soft"
        assert field.constraint_expression_strength == "soft"
        assert field.is_unique_strength == "soft"
        assert [
            record.message
            for record in caplog.records
            if "hidden_field" in record.message
        ] == []

    def test_xlsform_conditional_hidden_field_does_not_get_wrapper(self, converter):
        converter.survey_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                generate_survey_row(
                    type="text",
                    name="controller",
                    label="Controller",
                ),
                generate_survey_row(
                    type="text",
                    name="visible_field",
                    label="Visible field",
                    relevant="${controller} = 'yes'",
                ),
                generate_survey_row(
                    type="calculate",
                    name="hidden_field",
                    calculation="1 + 1",
                    relevant="${controller} = 'yes'",
                ),
            ]
        )

        converter.convert()

        survey_layer = converter.vector_datasets[0]
        layer = QgsVectorLayer("Point?crs=EPSG:4326", "survey", "memory")
        data_provider = layer.dataProvider()

        assert data_provider is not None

        data_provider.addAttributes(create_fields(survey_layer).toList())
        layer.updateFields()
        set_layer_virtual_fields(layer, survey_layer)

        form_config = get_layer_edit_form(layer.fields(), survey_layer)
        root_container = form_config.tabs()[0]
        controller_item = root_container.children()[0]
        visible_wrapper = root_container.children()[1]
        hidden_item = root_container.children()[2]

        assert isinstance(controller_item, QgsAttributeEditorField)
        assert controller_item.name() == "controller"

        assert isinstance(visible_wrapper, QgsAttributeEditorContainer)
        assert visible_wrapper.name() == "`visible_field` conditional wrapper"
        assert (
            visible_wrapper.visibilityExpression().data().expression()
            == "\"controller\" = 'yes'"
        )
        assert len(visible_wrapper.children()) == 1
        assert isinstance(visible_wrapper.children()[0], QgsAttributeEditorField)
        assert visible_wrapper.children()[0].name() == "visible_field"

        assert isinstance(hidden_item, QgsAttributeEditorField)
        assert hidden_item.name() == "hidden_field"

    def test_xlsform_with_group(self, converter):
        converter.survey_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                generate_survey_row(
                    type="begin group",
                    name="group_001",
                    label="Group 001",
                ),
                generate_survey_row(
                    type="text",
                    name="field_001",
                    label="Field 001",
                ),
                generate_survey_row(
                    type="end group",
                ),
            ]
        )

        converter.convert()

        assert len(converter.vector_datasets) == 1

        survey_layer = converter.vector_datasets[0]

        assert len(survey_layer.fields) == 2
        assert survey_layer.fields[0] == generate_uuid_field_def(
            field_id=survey_layer.fields[0].field_id,
        )
        assert survey_layer.fields[1] == generate_field_def(
            field_id=survey_layer.fields[1].field_id,
            type="string",
            name="field_001",
            alias="Field 001",
            widget_type="TextEdit",
        )

        assert len(survey_layer.form_config) == 1

        assert survey_layer.form_config[0] == generate_form_item_def(
            item_id="item_container_0",
            label="Group 001",
            type="tab",
            children=[
                generate_form_item_def(
                    item_id=survey_layer.form_config[0].children[0].item_id,
                    field_name="field_001",
                    type="field",
                    is_label_on_top=True,
                )
            ],
        )

    def test_xlsform_with_group_nesting(self, converter):
        converter.survey_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                generate_survey_row(
                    type="begin group",
                    name="group_001",
                    label="Group 001",
                ),
                generate_survey_row(
                    type="begin group",
                    name="group_001_001",
                    label="Group 001_001",
                ),
                generate_survey_row(
                    type="text",
                    name="field_001_001",
                    label="Field 001_001",
                ),
                generate_survey_row(
                    type="end group",
                ),
                generate_survey_row(
                    type="end group",
                ),
            ]
        )

        converter.convert()

        assert len(converter.vector_datasets) == 1

        survey_layer = converter.vector_datasets[0]

        assert len(survey_layer.fields) == 2
        assert survey_layer.fields[0] == generate_uuid_field_def(
            field_id=survey_layer.fields[0].field_id,
        )
        assert survey_layer.fields[1] == generate_field_def(
            field_id=survey_layer.fields[1].field_id,
            type="string",
            name="field_001_001",
            alias="Field 001_001",
            widget_type="TextEdit",
        )

        assert len(survey_layer.form_config) == 1

        assert survey_layer.form_config[0] == generate_form_item_def(
            item_id="item_container_0",
            label="Group 001",
            type="tab",
            children=[
                generate_form_item_def(
                    item_id="item_container_1",
                    label="Group 001_001",
                    type="group_box",
                    children=[
                        generate_form_item_def(
                            item_id=survey_layer.form_config[0]
                            .children[0]
                            .children[0]
                            .item_id,
                            field_name="field_001_001",
                            type="field",
                            is_label_on_top=True,
                        )
                    ],
                )
            ],
        )

    def test_xlsform_with_root_fields_and_group_uses_groupless_begin_and_end(
        self, converter
    ):
        converter.survey_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                generate_survey_row(
                    type="text",
                    name="field_001",
                    label="Field 001",
                ),
                generate_survey_row(
                    type="begin group",
                    name="group_001",
                    label="Group 001",
                ),
                generate_survey_row(
                    type="text",
                    name="field_002",
                    label="Field 002",
                ),
                generate_survey_row(
                    type="end group",
                ),
                generate_survey_row(
                    type="text",
                    name="field_003",
                    label="Field 003",
                ),
            ]
        )

        converter.convert()

        assert len(converter.vector_datasets) == 1

        survey_layer = converter.vector_datasets[0]

        assert len(survey_layer.form_config) == 3
        assert survey_layer.form_config[0] == generate_form_item_def(
            item_id="tab_item_survey_layer_0",
            label="Survey",
            type="tab",
            children=[
                generate_form_item_def(
                    item_id=survey_layer.form_config[0].children[0].item_id,
                    field_name="field_001",
                    type="field",
                    is_label_on_top=True,
                ),
            ],
        )
        assert survey_layer.form_config[1] == generate_form_item_def(
            item_id="item_container_1",
            label="Group 001",
            type="tab",
            children=[
                generate_form_item_def(
                    item_id=survey_layer.form_config[1].children[0].item_id,
                    field_name="field_002",
                    type="field",
                    is_label_on_top=True,
                )
            ],
        )
        assert survey_layer.form_config[2] == generate_form_item_def(
            item_id="tab_item_survey_layer_2",
            label="Survey",
            type="tab",
            children=[
                generate_form_item_def(
                    item_id=survey_layer.form_config[2].children[0].item_id,
                    field_name="field_003",
                    type="field",
                    is_label_on_top=True,
                ),
            ],
        )

    def test_xlsform_with_root_fields_and_group_uses_groupless_end(self, converter):
        converter.survey_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                generate_survey_row(
                    type="begin group",
                    name="group_001",
                    label="Group 001",
                ),
                generate_survey_row(
                    type="text",
                    name="field_001",
                    label="Field 001",
                ),
                generate_survey_row(
                    type="end group",
                ),
                generate_survey_row(
                    type="text",
                    name="field_002",
                    label="Field 002",
                ),
                generate_survey_row(
                    type="text",
                    name="field_003",
                    label="Field 003",
                ),
            ]
        )

        converter.convert()

        assert len(converter.vector_datasets) == 1

        survey_layer = converter.vector_datasets[0]

        assert len(survey_layer.form_config) == 2
        assert survey_layer.form_config[0] == generate_form_item_def(
            item_id="item_container_0",
            label="Group 001",
            type="tab",
            children=[
                generate_form_item_def(
                    item_id=survey_layer.form_config[0].children[0].item_id,
                    field_name="field_001",
                    type="field",
                    is_label_on_top=True,
                ),
            ],
        )
        assert survey_layer.form_config[1] == generate_form_item_def(
            item_id="tab_item_survey_layer_1",
            label="Survey",
            type="tab",
            children=[
                generate_form_item_def(
                    item_id=survey_layer.form_config[1].children[0].item_id,
                    field_name="field_002",
                    type="field",
                    is_label_on_top=True,
                ),
                generate_form_item_def(
                    item_id=survey_layer.form_config[1].children[1].item_id,
                    field_name="field_003",
                    type="field",
                    is_label_on_top=True,
                ),
            ],
        )

    def test_xlsform_with_root_fields_and_group_uses_groupless_begin(self, converter):
        converter.survey_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                generate_survey_row(
                    type="text",
                    name="field_001",
                    label="Field 001",
                ),
                generate_survey_row(
                    type="text",
                    name="field_002",
                    label="Field 002",
                ),
                generate_survey_row(
                    type="begin group",
                    name="group_001",
                    label="Group 001",
                ),
                generate_survey_row(
                    type="text",
                    name="field_003",
                    label="Field 003",
                ),
                generate_survey_row(
                    type="end group",
                ),
            ]
        )

        converter.convert()

        assert len(converter.vector_datasets) == 1

        survey_layer = converter.vector_datasets[0]

        assert len(survey_layer.form_config) == 2
        assert survey_layer.form_config[0] == generate_form_item_def(
            item_id="tab_item_survey_layer_0",
            label="Survey",
            type="tab",
            children=[
                generate_form_item_def(
                    item_id=survey_layer.form_config[0].children[0].item_id,
                    field_name="field_001",
                    type="field",
                    is_label_on_top=True,
                ),
                generate_form_item_def(
                    item_id=survey_layer.form_config[0].children[1].item_id,
                    field_name="field_002",
                    type="field",
                    is_label_on_top=True,
                ),
            ],
        )
        assert survey_layer.form_config[1] == generate_form_item_def(
            item_id="item_container_2",
            label="Group 001",
            type="tab",
            children=[
                generate_form_item_def(
                    item_id=survey_layer.form_config[1].children[0].item_id,
                    field_name="field_003",
                    type="field",
                    is_label_on_top=True,
                ),
            ],
        )

    def test_xlsform_without_tab_grouping_wraps_root_groups_in_survey_tab(self):
        survey_sheet = MagicMock()
        choices_sheet = MagicMock()
        settings_sheet = MagicMock()
        converter = XlsformConverter(
            survey_sheet,
            choices_sheet,
            settings_sheet,
            settings={
                "basemap_url": "",
                "form_group_type": "group_box",
                "use_groups_as_tabs": False,
            },
        )
        converter.survey_sheet.__iter__.return_value = to_parsed_sheet_rows(  # type: ignore[attr-defined]
            [
                generate_survey_row(
                    type="begin group",
                    name="group_001",
                    label="Group 001",
                ),
                generate_survey_row(
                    type="text",
                    name="field_001",
                    label="Field 001",
                ),
                generate_survey_row(
                    type="end group",
                ),
            ]
        )

        converter.convert()

        assert len(converter.vector_datasets) == 1

        survey_layer = converter.vector_datasets[0]

        assert len(survey_layer.form_config) == 1
        assert survey_layer.form_config[0] == generate_form_item_def(
            item_id="tab_item_survey_layer",
            label="Survey",
            type="tab",
            children=[
                generate_form_item_def(
                    item_id="item_container_0",
                    label="Group 001",
                    type="group_box",
                    children=[
                        generate_form_item_def(
                            item_id=survey_layer.form_config[0]
                            .children[0]
                            .children[0]
                            .item_id,
                            field_name="field_001",
                            type="field",
                            is_label_on_top=True,
                        )
                    ],
                )
            ],
        )

    def test_xlsform_with_repeat(self, converter):
        converter.survey_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                generate_survey_row(
                    type="begin repeat",
                    name="group_001",
                    label="Group 001",
                ),
                generate_survey_row(
                    type="begin group",
                    name="group_001_001",
                    label="Group 001_001",
                ),
                generate_survey_row(
                    type="text",
                    name="field_001",
                    label="Field 001",
                ),
                generate_survey_row(
                    type="end group",
                ),
                generate_survey_row(
                    type="end repeat",
                ),
                generate_survey_row(
                    type="integer",
                    name="field_002",
                    label="Field 002",
                ),
            ]
        )

        converter.convert()

        assert len(converter.vector_datasets) == 2

        survey_layer, repeat_layer_1 = converter.vector_datasets

        assert survey_layer.layer_id == "survey_layer"
        assert len(survey_layer.fields) == 2
        assert survey_layer.fields[0].name == "uuid"
        assert survey_layer.fields[1].name == "field_002"
        assert len(repeat_layer_1.fields) == 3
        assert repeat_layer_1.fields[0].name == "uuid"
        assert repeat_layer_1.fields[1].name == "uuid_parent"
        assert repeat_layer_1.fields[2].name == "field_001"

    def test_xlsform_with_repeat_places_relation_on_parent_form(self, converter):
        converter.survey_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                generate_survey_row(
                    type="begin repeat",
                    name="group_001",
                    label="Group 001",
                ),
                generate_survey_row(
                    type="begin group",
                    name="group_001_001",
                    label="Group 001_001",
                ),
                generate_survey_row(
                    type="text",
                    name="field_001",
                    label="Field 001",
                ),
                generate_survey_row(
                    type="end group",
                ),
                generate_survey_row(
                    type="end repeat",
                ),
                generate_survey_row(
                    type="integer",
                    name="field_002",
                    label="Field 002",
                ),
            ]
        )

        converter.convert()

        assert len(converter.vector_datasets) == 2

        survey_layer, repeat_layer = converter.vector_datasets

        assert len(survey_layer.form_config) == 1
        survey_form = survey_layer.form_config[0]
        assert survey_form.type == "tab"
        assert survey_form.field_name is None
        assert survey_form.label == "Survey"
        assert len(survey_form.children) == 2
        assert survey_form.children[0].type == "relation"
        assert survey_form.children[0].field_name == "relation_0"
        assert survey_form.children[0].children == []
        assert survey_form.children[1].type == "field"
        assert survey_form.children[1].field_name == "field_002"
        assert survey_form.children[1].children == []

        assert len(repeat_layer.form_config) == 1
        repeat_form = repeat_layer.form_config[0]
        assert repeat_form.type == "tab"
        assert repeat_form.field_name is None
        assert repeat_form.label == "Group 001_001"
        assert len(repeat_form.children) == 1
        assert repeat_form.children[0].type == "field"
        assert repeat_form.children[0].field_name == "field_001"
        assert repeat_form.children[0].children == []

    @pytest.mark.parametrize(
        ("use_multipart_geoms", "xlsform_type", "expected_geometry"),
        [
            (False, "geopoint", "Point"),
            (False, "start-geopoint", "Point"),
            (False, "start-geotrace", "LineString"),
            (False, "geotrace", "LineString"),
            (False, "geoshape", "Polygon"),
            (False, "start-geoshape", "Polygon"),
            (True, "geopoint", "MultiPoint"),
            (True, "start-geopoint", "MultiPoint"),
            (True, "start-geotrace", "MultiLineString"),
            (True, "geotrace", "MultiLineString"),
            (True, "geoshape", "MultiPolygon"),
            (True, "start-geoshape", "MultiPolygon"),
        ],
    )
    def test_xlsform_geometry(
        self, use_multipart_geoms, xlsform_type, expected_geometry
    ):
        survey_sheet = MagicMock()
        choices_sheet = MagicMock()
        settings_sheet = MagicMock()
        survey_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                generate_survey_row(
                    type=xlsform_type,
                    name=f"{xlsform_type}_001",
                ),
            ]
        )
        converter = XlsformConverter(
            survey_sheet,
            choices_sheet,
            settings_sheet,
            settings={
                "basemap_url": "",
                "use_multipart_geoms": use_multipart_geoms,
            },
        )

        converter.convert()

        assert len(converter.vector_datasets) == 1

        survey_layer = converter.vector_datasets[0]

        assert survey_layer.geometry_type == expected_geometry

    def test_xlsform_display_expression(self, converter):
        converter.settings_sheet.__iter__.return_value = to_parsed_sheet_rows(
            [
                {"instance_name": r"concat(${lname}, '-', ${fname}, '-', uuid())"},
            ]
        )

        converter._xlsform_settings = converter._get_xlsform_settings()
        converter.convert()

        assert converter._xlsform_settings
        assert (
            converter._xlsform_settings["instance_name"]
            == r"concat(${lname}, '-', ${fname}, '-', uuid())"
        )
        assert (
            converter.get_display_expression(
                converter._xlsform_settings["instance_name"]
            )
            == "concat(\"lname\", '-', \"fname\", '-', uuid(format:='WithoutBraces'))"
        )

    def test_xlsform_survey_rating_file(self):
        survey_sheet, choices_sheet, settings_sheet = parse_xlsform_sheets(
            str(Path(__file__).parent / "data/service_rating.xlsx")
        )

        converter = XlsformConverter(
            survey_sheet,
            choices_sheet,
            settings_sheet,
            settings={
                "basemap_url": "",
            },
        )

        converter.convert()

        assert len(converter.all_datasets) == 6

        sorted_datasets = sorted(converter.all_datasets, key=lambda ml: ml.name)

        survey_layer, *_ = sorted_datasets
        survey_layer = cast("VectorDatasetDef", survey_layer)

        assert len(survey_layer.fields) == 21
        assert survey_layer.virtual_fields == []
        assert survey_layer.fields[0] == generate_uuid_field_def(
            field_id=survey_layer.fields[0].field_id,
        )
        assert survey_layer.fields[1] == generate_field_def(
            field_id=survey_layer.fields[1].field_id,
            type="string",
            name="recommend",
            alias="Would you recommend our services ?",
            widget_type="ValueRelation",
            widget_config={
                "AllowMulti": False,
                "AllowNull": False,
                "FilterExpression": "",
                "Key": "name",
                "Layer": "list_yes_no_b633d2a01c3d5811904acc3f5a80ed94",
                "LayerName": "yes_no",
                "Value": "label",
            },
            is_not_null=True,
            is_not_null_strength="hard",
        )
        assert survey_layer.fields[2] == generate_field_def(
            field_id=survey_layer.fields[2].field_id,
            type="string",
            name="services",
            alias="Which services are you using ?",
            widget_type="ValueRelation",
            widget_config={
                "AllowMulti": True,
                "AllowNull": False,
                "FilterExpression": " \"name\" != '' ",
                "Key": "name",
                "Layer": "list_services_684d896f63e5780190e5a96a49c650c8",
                "LayerName": "services",
                "Value": "label",
            },
            is_not_null=True,
            is_not_null_strength="hard",
        )
        assert survey_layer.fields[3] == generate_field_def(
            field_id=survey_layer.fields[3].field_id,
            type="string",
            name="info_portal_rating",
            alias="Medication information portal",
            widget_type="ValueRelation",
            widget_config={
                "AllowMulti": False,
                "AllowNull": False,
                "FilterExpression": "",
                "Key": "name",
                "Layer": "list_rating_9598f92ff9287ad12c25e5c19f102efe",
                "LayerName": "rating",
                "Value": "label",
            },
            is_not_null=False,
            is_not_null_strength="not_set",
        )
        assert survey_layer.fields[4] == generate_field_def(
            field_id=survey_layer.fields[4].field_id,
            type="string",
            name="clinical_trials_rating",
            alias="Clinical trials information",
            widget_type="ValueRelation",
            widget_config={
                "AllowMulti": False,
                "AllowNull": False,
                "FilterExpression": "",
                "Key": "name",
                "Layer": "list_rating_9598f92ff9287ad12c25e5c19f102efe",
                "LayerName": "rating",
                "Value": "label",
            },
            is_not_null=False,
            is_not_null_strength="not_set",
        )
        assert survey_layer.fields[5] == generate_field_def(
            field_id=survey_layer.fields[5].field_id,
            type="string",
            name="support_program_rating",
            alias="Patient support program portal",
            widget_type="ValueRelation",
            widget_config={
                "AllowMulti": False,
                "AllowNull": False,
                "FilterExpression": "",
                "Key": "name",
                "Layer": "list_rating_9598f92ff9287ad12c25e5c19f102efe",
                "LayerName": "rating",
                "Value": "label",
            },
            is_not_null=False,
            is_not_null_strength="not_set",
        )
        assert survey_layer.fields[6] == generate_field_def(
            field_id=survey_layer.fields[6].field_id,
            type="string",
            name="ordering_rating",
            alias="E-sampling or ordering platform",
            widget_type="ValueRelation",
            widget_config={
                "AllowMulti": False,
                "AllowNull": False,
                "FilterExpression": "",
                "Key": "name",
                "Layer": "list_rating_9598f92ff9287ad12c25e5c19f102efe",
                "LayerName": "rating",
                "Value": "label",
            },
            is_not_null=False,
            is_not_null_strength="not_set",
        )
        assert survey_layer.fields[7] == generate_field_def(
            field_id=survey_layer.fields[7].field_id,
            type="string",
            name="rep_scheduling_rating",
            alias="Medical representative scheduling",
            widget_type="ValueRelation",
            widget_config={
                "AllowMulti": False,
                "AllowNull": False,
                "FilterExpression": "",
                "Key": "name",
                "Layer": "list_rating_9598f92ff9287ad12c25e5c19f102efe",
                "LayerName": "rating",
                "Value": "label",
            },
            is_not_null=False,
            is_not_null_strength="not_set",
        )
        assert survey_layer.fields[8] == generate_field_def(
            field_id=survey_layer.fields[8].field_id,
            type="string",
            name="cme_rating",
            alias="Continuing Medical Education (CME) platform",
            widget_type="ValueRelation",
            widget_config={
                "AllowMulti": False,
                "AllowNull": False,
                "FilterExpression": "",
                "Key": "name",
                "Layer": "list_rating_9598f92ff9287ad12c25e5c19f102efe",
                "LayerName": "rating",
                "Value": "label",
            },
            is_not_null=False,
            is_not_null_strength="not_set",
        )
        assert survey_layer.fields[9] == generate_field_def(
            field_id=survey_layer.fields[9].field_id,
            type="string",
            name="feature_improve",
            alias="What additional digital tools or features would improve your experience?",
            widget_type="TextEdit",
            widget_config={
                "IsMultiline": True,
            },
        )
        assert survey_layer.fields[10] == generate_field_def(
            field_id=survey_layer.fields[10].field_id,
            type="integer",
            name="part_employees",
            alias="Part-time",
            widget_type="Range",
            constraint_expression='"part_employees" > 0',
            constraint_expression_description="Must have more than 1 employee",
            constraint_expression_strength="hard",
        )
        assert survey_layer.fields[11] == generate_field_def(
            field_id=survey_layer.fields[11].field_id,
            type="integer",
            name="full_employees",
            alias="Full time",
            widget_type="Range",
            constraint_expression='"full_employees" > 0',
            constraint_expression_description="Must have more than 1 employee",
            constraint_expression_strength="hard",
        )
        assert survey_layer.fields[12] == generate_field_def(
            field_id=survey_layer.fields[12].field_id,
            type="string",
            name="employee_total",
            alias="",
            widget_type="Hidden",
            default_value='"part_employees" + "full_employees"',
            set_default_value_on_update=True,
        )
        assert survey_layer.fields[13] == generate_field_def(
            field_id=survey_layer.fields[13].field_id,
            type="boolean",
            name="employee_summary",
            alias="",
            alias_expression="'Your company is employing  a total of ' || \"employee_total\" || ' correct ?'",
            widget_type="CheckBox",
            default_value="",
            set_default_value_on_update=False,
        )
        assert survey_layer.fields[14] == generate_field_def(
            field_id=survey_layer.fields[14].field_id,
            type="string",
            name="salutation",
            alias="Salutation",
            widget_type="ValueRelation",
            widget_config={
                "AllowMulti": False,
                "AllowNull": False,
                "FilterExpression": "",
                "Key": "name",
                "Layer": "list_salutation_fa4846dd0d2c8cdfffb7ae8e9b3bcb36",
                "LayerName": "salutation",
                "Value": "label",
            },
            default_value="",
            set_default_value_on_update=False,
        )
        assert survey_layer.fields[15] == generate_field_def(
            field_id=survey_layer.fields[15].field_id,
            type="string",
            name="name",
            alias="Name",
            widget_type="TextEdit",
        )
        assert survey_layer.fields[16] == generate_field_def(
            field_id=survey_layer.fields[16].field_id,
            type="string",
            name="address",
            alias="Address",
            widget_type="TextEdit",
        )
        assert survey_layer.fields[17] == generate_field_def(
            field_id=survey_layer.fields[17].field_id,
            type="string",
            name="zip_code",
            alias="Zip code",
            widget_type="TextEdit",
            constraint_expression="regexp_match(\"zip_code\", '^\\\\d{5}(-\\\\d{4})?$')",
            constraint_expression_description="",
            constraint_expression_strength="hard",
        )
        assert survey_layer.fields[18] == generate_field_def(
            field_id=survey_layer.fields[18].field_id,
            type="string",
            name="city",
            alias="City",
            widget_type="TextEdit",
        )
        assert survey_layer.fields[19] == generate_field_def(
            field_id=survey_layer.fields[19].field_id,
            type="string",
            name="state",
            alias="State",
            widget_type="TextEdit",
        )
        assert survey_layer.fields[20] == generate_field_def(
            field_id=survey_layer.fields[20].field_id,
            type="string",
            name="comment",
            alias="Would you like to leave a last comment ?",
            widget_type="TextEdit",
            widget_config={
                "IsMultiline": True,
            },
        )

        assert len(survey_layer.form_config) == 4

        assert survey_layer.form_config[0] == generate_form_item_def(
            item_id="item_container_0",
            label="Introduction page",
            type="tab",
            children=[
                generate_form_item_def(
                    item_id="item_container_1",
                    label="Welcome to our new survey. Please answer a couple of  questions.",
                    type="text",
                    is_markdown=False,
                ),
                generate_form_item_def(
                    item_id=survey_layer.form_config[0].children[1].item_id,
                    field_name="recommend",
                    type="field",
                ),
                generate_form_item_def(
                    item_id=survey_layer.form_config[0].children[2].item_id,
                    field_name="services",
                    type="field",
                    visibility_expression=format_selected_expr("recommend", "yes"),
                ),
            ],
        )
        assert survey_layer.form_config[1] == generate_form_item_def(
            item_id="item_container_6",
            label="Statisfaction evaluation page",
            type="tab",
            visibility_expression=format_selected_expr("recommend", "yes"),
            children=[
                generate_form_item_def(
                    item_id="item_container_7",
                    label="Services rating matrix",
                    type="group_box",
                    children=[
                        generate_form_item_def(
                            item_id=survey_layer.form_config[1]
                            .children[0]
                            .children[0]
                            .item_id,
                            field_name="info_portal_rating",
                            type="field",
                        ),
                        generate_form_item_def(
                            item_id=survey_layer.form_config[1]
                            .children[0]
                            .children[1]
                            .item_id,
                            field_name="clinical_trials_rating",
                            type="field",
                        ),
                        generate_form_item_def(
                            item_id=survey_layer.form_config[1]
                            .children[0]
                            .children[2]
                            .item_id,
                            field_name="support_program_rating",
                            type="field",
                            visibility_expression=format_selected_expr(
                                "services", "support_program"
                            ),
                        ),
                        generate_form_item_def(
                            item_id=survey_layer.form_config[1]
                            .children[0]
                            .children[3]
                            .item_id,
                            field_name="ordering_rating",
                            type="field",
                            visibility_expression=format_selected_expr(
                                "services", "ordering"
                            ),
                        ),
                        generate_form_item_def(
                            item_id=survey_layer.form_config[1]
                            .children[0]
                            .children[4]
                            .item_id,
                            field_name="rep_scheduling_rating",
                            type="field",
                        ),
                        generate_form_item_def(
                            item_id=survey_layer.form_config[1]
                            .children[0]
                            .children[5]
                            .item_id,
                            field_name="cme_rating",
                            type="field",
                        ),
                    ],
                ),
                generate_form_item_def(
                    item_id=survey_layer.form_config[1].children[1].item_id,
                    field_name="feature_improve",
                    type="field",
                ),
            ],
        )
        assert survey_layer.form_config[2] == generate_form_item_def(
            item_id="item_container_17",
            label="Company details page",
            type="tab",
            children=[
                generate_form_item_def(
                    item_id="item_container_18",
                    label="How many employees work in your company ?",
                    type="group_box",
                    children=[
                        generate_form_item_def(
                            item_id=survey_layer.form_config[2]
                            .children[0]
                            .children[0]
                            .item_id,
                            field_name="part_employees",
                            type="field",
                        ),
                        generate_form_item_def(
                            item_id=survey_layer.form_config[2]
                            .children[0]
                            .children[1]
                            .item_id,
                            field_name="full_employees",
                            type="field",
                        ),
                    ],
                ),
                generate_form_item_def(
                    item_id=survey_layer.form_config[2].children[1].item_id,
                    field_name="employee_total",
                    type="field",
                    is_read_only=True,
                    show_label=False,
                ),
                generate_form_item_def(
                    item_id=survey_layer.form_config[2].children[2].item_id,
                    field_name="employee_summary",
                    type="field",
                    visibility_expression='"part_employees" > 1 and "full_employees" > 1',
                ),
            ],
        )
        assert survey_layer.form_config[3] == generate_form_item_def(
            item_id="item_container_25",
            label="Contact details page",
            type="tab",
            children=[
                generate_form_item_def(
                    item_id="item_container_26",
                    label="Please leave your contact details",
                    type="group_box",
                    children=[
                        generate_form_item_def(
                            item_id=survey_layer.form_config[3]
                            .children[0]
                            .children[0]
                            .item_id,
                            field_name="salutation",
                            type="field",
                        ),
                        generate_form_item_def(
                            item_id=survey_layer.form_config[3]
                            .children[0]
                            .children[1]
                            .item_id,
                            field_name="name",
                            type="field",
                        ),
                        generate_form_item_def(
                            item_id=survey_layer.form_config[3]
                            .children[0]
                            .children[2]
                            .item_id,
                            field_name="address",
                            type="field",
                        ),
                        generate_form_item_def(
                            item_id=survey_layer.form_config[3]
                            .children[0]
                            .children[3]
                            .item_id,
                            field_name="zip_code",
                            type="field",
                        ),
                        generate_form_item_def(
                            item_id=survey_layer.form_config[3]
                            .children[0]
                            .children[4]
                            .item_id,
                            field_name="city",
                            type="field",
                        ),
                        generate_form_item_def(
                            item_id=survey_layer.form_config[3]
                            .children[0]
                            .children[5]
                            .item_id,
                            field_name="state",
                            type="field",
                        ),
                    ],
                ),
                generate_form_item_def(
                    item_id=survey_layer.form_config[3].children[1].item_id,
                    field_name="comment",
                    type="field",
                ),
            ],
        )

    def test_xlsform_missing_choices_file(self):
        survey_sheet, choices_sheet, settings_sheet = parse_xlsform_sheets(
            str(Path(__file__).parent / "data/missing_choices.xlsx")
        )

        converter = XlsformConverter(
            survey_sheet,
            choices_sheet,
            settings_sheet,
            settings={
                "basemap_url": "",
            },
        )

        converter.convert()

        assert len(converter.all_datasets) == 1

        sorted_datasets = sorted(converter.all_datasets, key=lambda ml: ml.name)

        survey_layer, *_ = sorted_datasets
        survey_layer = cast("VectorDatasetDef", survey_layer)

        assert len(survey_layer.fields) == 3
        assert survey_layer.virtual_fields == []
        assert survey_layer.fields[0] == generate_uuid_field_def(
            field_id=survey_layer.fields[0].field_id,
        )
        assert survey_layer.fields[1] == generate_field_def(
            field_id=survey_layer.fields[1].field_id,
            type="string",
            name="comment",
            alias="A comment",
            widget_type="TextEdit",
            widget_config={},
            is_not_null=False,
        )
        assert survey_layer.fields[2] == generate_field_def(
            field_id=survey_layer.fields[2].field_id,
            type="string",
            name="missing_choices",
            alias="A missing choices list turned into a text",
            widget_type="TextEdit",
            widget_config={},
            is_not_null=False,
        )
