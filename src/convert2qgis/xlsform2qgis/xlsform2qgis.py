import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, cast

from qgis.core import QgsFeatureSource, QgsProject

from convert2qgis.json2qgis.generate import (
    generate_field_def,
    generate_form_item_def,
    generate_raster_dataset_def,
    generate_relation_def,
    generate_uuid_field_def,
    generate_vector_dataset_def,
)
from convert2qgis.json2qgis.json2qgis import ProjectCreator
from convert2qgis.json2qgis.type_defs import (
    AliasDef,
    AliasSimpleDef,
    AliasWithExpressionDef,
    ChoicesDef,
    ConstraintStrength,
    CrsDef,
    DatasetDef,
    DatasetGroupDef,
    FieldDef,
    FormItemDef,
    FormItemGroupTypes,
    GeometryType,
    LegendTreeGroupDef,
    LegendTreeLayerDef,
    PathOrStr,
    ProjectDef,
    ProjectMetadataDef,
    RasterDatasetDef,
    RelationDef,
    VectorDatasetDef,
    WeakFieldDef,
    WeakFormItemDef,
)
from convert2qgis.xlsform2qgis.converter_utils import (
    build_choices_layer_id,
    build_choices_layer_name,
    get_unique_label,
    get_xlsform_type,
    strip_html,
)
from convert2qgis.xlsform2qgis.errors import InvalidXlsformFileError
from convert2qgis.xlsform2qgis.expressions.errors import ParseError, TokenizationError
from convert2qgis.xlsform2qgis.expressions.expression import (
    Expression,
    ExpressionContext,
)
from convert2qgis.xlsform2qgis.expressions.parser import ParserType
from convert2qgis.xlsform2qgis.qgis_utils import set_survey_features
from convert2qgis.xlsform2qgis.sheet_parser import ParsedSheet, ParsedSheetRow
from convert2qgis.xlsform2qgis.type_defs import (
    ConverterSettings,
    GroupStatus,
    LayerStatus,
    ParsedSheetRowResult,
    XlsformSettings,
)
from convert2qgis.xlsform2qgis.widgets import WidgetContext, WidgetRegistry

logger = logging.getLogger(__name__)

XLS_TYPES_MAP = {
    "integer": "integer",
    "decimal": "real",
    "range": "real",
    "date": "date",
    "today": "date",
    "time": "time",
    "datetime": "datetime",
    "start": "datetime",
    "end": "datetime",
    "acknowledge": "boolean",
    "text": "string",
    "barcode": "string",
    "image": "string",
    "audio": "string",
    "background-audio": "string",
    "video": "string",
    "file": "string",
    "select_one": "string",
    "select_one_from_file": "string",
    "select_multiple": "string",
    "select_multiple_from_file": "string",
    "rank": "string",
    "calculate": "string",
    "hidden": "string",
}


_FALLBACK_BASEMAP_NAME = "Basemap"
_DEFAULT_BASEMAP_URL = "type=xyz&tilePixelRatio=1&url=https://tile.openstreetmap.org/%7Bz%7D/%7Bx%7D/%7By%7D.png&zmax=19&zmin=0&crs=EPSG3857"
_DEFAULT_BASEMAP_NAME = "OpenStreetMap"


def parse_xlsform_sheets(
    xlsform_filename: PathOrStr,
) -> tuple[ParsedSheet, ParsedSheet, ParsedSheet]:
    """Extract the survey, choices and settings sheets from the given XLSForm file."""
    logger.debug("Parsing XLSForm file: %s", xlsform_filename)

    xlsform_filename = Path(xlsform_filename)
    if not xlsform_filename.exists():
        raise FileNotFoundError(f"XLSForm file not found: {xlsform_filename}")

    survey_sheet = ParsedSheet("survey", xlsform_filename)
    choices_sheet = ParsedSheet("choices", xlsform_filename)
    settings_sheet = ParsedSheet("settings", xlsform_filename)

    return (survey_sheet, choices_sheet, settings_sheet)


def convert_xlsform(
    xlsform_filename: PathOrStr,
    *,
    output_dir: "PathOrStr | None" = None,
    settings: "ConverterSettings | None" = None,
    skip_failed_expressions: bool = False,
    json_filename: "PathOrStr | None" = None,
) -> "QgsProject | dict[str, Any]":
    if output_dir:
        return convert_xlsform_to_qgis_project(
            xlsform_filename,
            output_dir,
            settings=settings,
            skip_failed_expressions=skip_failed_expressions,
            json_filename=json_filename,
        )
    elif json_filename:
        return convert_xlsform_to_json(
            xlsform_filename,
            settings=settings,
            skip_failed_expressions=skip_failed_expressions,
            json_filename=json_filename,
        )

    raise AssertionError("Either `output_dir` or `json_filename` must be provided!")


def write_project_json(project_json: dict[str, Any], json_filename: PathOrStr) -> None:
    logger.info("Writing intermediate JSON representation to file: %s", json_filename)

    json_filename = Path(json_filename)
    json_filename.parent.mkdir(parents=True, exist_ok=True)

    with json_filename.open("w") as json_file:
        json.dump(project_json, json_file, sort_keys=True, indent=2)


def convert_xlsform_to_json(
    xlsform_filename: PathOrStr,
    *,
    settings: "ConverterSettings | None" = None,
    skip_failed_expressions: bool = False,
    json_filename: "PathOrStr | None" = None,
) -> dict[str, Any]:
    survey_sheet, choices_sheet, settings_sheet = parse_xlsform_sheets(xlsform_filename)

    converter = XlsformConverter(
        survey_sheet,
        choices_sheet,
        settings_sheet,
        settings=settings,
        skip_failed_expressions=skip_failed_expressions,
    )

    if not converter.is_valid():
        raise InvalidXlsformFileError("Invalid XLSForm file!")

    project_json = converter.to_json()

    if json_filename:
        write_project_json(project_json, json_filename)

    return project_json


def convert_xlsform_to_qgis_project(  # noqa: PLR0913
    xlsform_filename: PathOrStr,
    output_dir: PathOrStr,
    *,
    settings: "ConverterSettings | None" = None,
    survey_features: "QgsFeatureSource | None" = None,
    skip_failed_expressions: bool = False,
    json_filename: "PathOrStr | None" = None,
) -> QgsProject:
    project_json = convert_xlsform_to_json(
        xlsform_filename,
        settings=settings,
        skip_failed_expressions=skip_failed_expressions,
        json_filename=json_filename,
    )

    creator = ProjectCreator(project_json)
    project = creator.build(output_dir)

    if survey_features is not None and survey_features.featureCount() >= 1:
        logger.info(
            "Prefilling the project with %d survey features from the provided layer...",
            survey_features.featureCount(),
        )

        set_survey_features(project, survey_features)

    return project


class XlsformConverter:
    survey_sheet: ParsedSheet
    choices_sheet: ParsedSheet
    settings_sheet: ParsedSheet
    vector_datasets: list[VectorDatasetDef]
    raster_datasets: list[RasterDatasetDef]
    legend_tree: LegendTreeGroupDef
    relations: list[RelationDef]

    _converter_settings: ConverterSettings
    """Converter settings."""

    _xlsform_settings: XlsformSettings
    """Settings as defined in the `settings` sheet of the XLSForm, with some defaults if not specified."""

    _skip_failed_expressions: bool
    """Return empty string instead of throwing an error when a row expression cannot be converted."""

    _calculate_expressions: dict[str, Expression]
    """Store the expressions for each `type=calculate` row, so they can be passed as `ExpressionContext` when needed."""

    _field_compatibilities: dict[str, bool]
    """Keep track of the compatibility of different XLSForm field types with QGIS and QField, to be able to emit warnings and info messages during the conversion process."""

    _use_groups_as_tabs: bool
    """Whether to add top-level XLSForm groups as root form items instead of nesting them under the fallback Survey container."""

    _form_group_type: FormItemGroupTypes = "group_box"
    """The form group type to use for groups in the form. By default it is set to `group_box`, but it can be set to `tab` if the user prefers a more tabbed form structure."""

    _project_crs: CrsDef
    """The project CRS to be defined on the output project."""

    _project_author: str
    """The project author of the output project."""

    _project_extent: str
    """The project extent of the output project as a list of coordinates (xmin, ymin, xmax, ymax) in project CRS."""

    _use_multipart_geoms: bool
    """Whether XLSForm geometry types should be stored using their multipart equivalent."""

    _layer_ids: list[str]
    """Stack to keep track of the current layer ids while parsing the survey sheet, to be able to assign fields and form items to the correct layer. Whenever a new layer is defined, its id is pushed to the stack, and whenever a layer definition ends, it is popped from the stack."""

    _container_ids: "list[str | None]"
    """Stack to keep track of the current parent container ids while parsing the survey sheet, to be able to assign form items to the correct parent container. Whenever a new container is defined, its id is pushed to the stack, and whenever a container definition ends, it is popped from the stack. The value `None` is used to represent the root level, where there is no parent container."""

    _max_pixels: Optional[int]
    """Keep track of the maximum pixels for image fields, to be able to set it as a project level property if at least one image field is present in the survey."""

    def __init__(
        self,
        survey_sheet: ParsedSheet,
        choices_sheet: ParsedSheet,
        settings_sheet: ParsedSheet,
        settings: "ConverterSettings | None" = None,
        skip_failed_expressions: bool = False,
    ) -> None:
        settings = settings or {}

        self.survey_sheet = survey_sheet
        self.choices_sheet = choices_sheet
        self.settings_sheet = settings_sheet

        self._skip_failed_expressions = skip_failed_expressions

        # settings
        self._form_group_type = settings.get("form_group_type") or "group_box"
        self._use_groups_as_tabs = settings.get("use_groups_as_tabs", True)
        self._project_crs = settings.get("crs") or "EPSG:3857"
        self._project_author = settings.get("author") or ""
        self._project_extent = settings.get("extent", "").strip() or ""
        self._use_multipart_geoms = settings.get("use_multipart_geoms", True)
        self._xlsform_settings = {
            **self._get_xlsform_settings(),
            **cast("XlsformSettings", settings.get("xlsform_settings", {})),
        }

        basemap_url = settings.get("basemap_url", None)
        if basemap_url:
            basemap_name = (
                cast("str | None", settings.get("basemap_name"))
                or _FALLBACK_BASEMAP_NAME
            )
        elif basemap_url == "":
            basemap_url = ""
            basemap_name = ""
        else:
            basemap_url = _DEFAULT_BASEMAP_URL
            basemap_name = _DEFAULT_BASEMAP_NAME

        self._project_basemap_url = basemap_url
        self._project_basemap_name = basemap_name

        # state
        self.vector_datasets = []
        self.raster_datasets = []
        self.legend_tree = LegendTreeGroupDef(
            item_id="legend_root",
            name="",
            children=[],
        )
        self.relations = []
        self._calculate_expressions = {}
        self._layer_ids = []
        self._container_ids = []

        self.widget_registry = WidgetRegistry()

        self._field_compatibilities = {}

        self._max_pixels = None

    def is_valid(self) -> bool:
        if not self.survey_sheet.layer.isValid():
            return False

        # Missing the two basic parameters that must be present within the survey layer
        if self.survey_sheet.indices["type"] == -1:
            return False

        return self.survey_sheet.indices["name"] != -1

    @property
    def all_datasets(self) -> list[DatasetDef]:
        return [*self.vector_datasets, *self.raster_datasets]

    def find_vector_dataset(self, layer_id: str) -> "VectorDatasetDef | None":
        for dataset_def in self.vector_datasets:
            if dataset_def.layer_id == layer_id:
                return dataset_def

        return None

    def get_form_group_type(self) -> FormItemGroupTypes:
        if len(self._container_ids) == 0 or self._container_ids[-1] is None:
            if self._use_groups_as_tabs:
                return "tab"

        return self._form_group_type

    def _get_expression_context(
        self,
        current_field: str,
        parser_type: ParserType = ParserType.EXPRESSION,
    ) -> ExpressionContext:
        return ExpressionContext(
            current_field=current_field,
            calculate_expressions=self._calculate_expressions,
            parser_type=parser_type,
            skip_expression_errors=self._skip_failed_expressions,
            choices_by_list=self._get_choices_by_list(),
            survey_settings=self._xlsform_settings,
        )

    def get_expression(
        self,
        expression_str: str,
        current_field: str,
        parser_type: ParserType = ParserType.EXPRESSION,
        *,
        should_strip_tags: bool = True,
    ) -> Expression:
        try:
            return Expression(
                expression_str,
                self._get_expression_context(current_field, parser_type),
                should_strip_tags=should_strip_tags,
            )
        except (ParseError, TokenizationError) as err:
            logger.error(
                "Failed to parse expression `%s` for field `%s`: %s",
                expression_str,
                current_field,
                err,
            )

            if self._skip_failed_expressions:
                return Expression(
                    "",
                    self._get_expression_context(current_field),
                    should_strip_tags=should_strip_tags,
                )

            raise

    def _enter_vector_dataset(self, dataset_def: VectorDatasetDef) -> None:
        layer_id = dataset_def.layer_id
        layer_name = dataset_def.name

        self.vector_datasets.append(dataset_def)
        self._layer_ids.append(layer_id)

        self._enter_container(None)

        self.legend_tree.children.append(
            LegendTreeLayerDef(
                layer_id=layer_id,
                item_id=f"layer_{layer_id}",
                name=layer_name,
                is_checked=True,
            )
        )

    def _exit_dataset(self) -> str:
        layer_id = self._layer_ids.pop()

        self._exit_container()

        return layer_id

    def _current_dataset(self) -> VectorDatasetDef:
        if not self._layer_ids:
            raise AssertionError("No layers defined yet!")

        layer_id = self._layer_ids[-1]
        dataset_def = self.find_vector_dataset(layer_id)

        if not dataset_def:
            raise AssertionError(f"Current layer with id {layer_id} not found!")

        return dataset_def

    def _find_form_item(
        self, item_id: str, form_items: list[FormItemDef]
    ) -> "FormItemDef | None":
        for form_item_def in form_items:
            if form_item_def.item_id == item_id:
                return form_item_def

            child_form_item = self._find_form_item(item_id, form_item_def.children)
            if child_form_item is not None:
                return child_form_item

        return None

    def _get_or_create_root_fields_container(self) -> FormItemDef:
        current_dataset_def = self._current_dataset()
        layer_id = self._layer_ids[-1]
        item_id = f"tab_item_{layer_id}"
        root_fields_container = self._find_form_item(
            item_id, current_dataset_def.form_config
        )

        if root_fields_container is None:
            root_fields_container = generate_form_item_def(
                item_id=item_id,
                type="tab",
                label=current_dataset_def.name,
            )

            # The root fields container is always inserted at the beginning of the form config.
            current_dataset_def.form_config.insert(0, root_fields_container)

        return root_fields_container

    def _get_or_create_tab_fields_container(self) -> FormItemDef:
        current_dataset_def = self._current_dataset()
        layer_id = self._layer_ids[-1]
        item_id = f"tab_item_{layer_id}_{(len(current_dataset_def.form_config) - 1)}"
        tab_fields_container = self._find_form_item(
            item_id, current_dataset_def.form_config
        )

        if tab_fields_container is None:
            item_id = f"tab_item_{layer_id}_{(len(current_dataset_def.form_config))}"
            tab_fields_container = generate_form_item_def(
                item_id=item_id,
                type="tab",
                label=current_dataset_def.name,
            )

            current_dataset_def.form_config.append(tab_fields_container)

        return tab_fields_container

    def _add_form_item(self, form_item_def: FormItemDef) -> None:
        current_dataset_def = self._current_dataset()
        current_container = self._current_container()

        if not self._use_groups_as_tabs and current_container is None:
            current_container = self._get_or_create_root_fields_container()

        if current_container:
            current_container.children.append(form_item_def)
        else:
            if form_item_def.type in ("field", "relation", "text"):
                if self._use_groups_as_tabs:
                    self._get_or_create_tab_fields_container().children.append(
                        form_item_def
                    )
                else:
                    self._get_or_create_root_fields_container().children.append(
                        form_item_def
                    )
            else:
                current_dataset_def.form_config.append(form_item_def)

    def _add_container(self, container_def: FormItemDef) -> None:
        self._add_form_item(container_def)

    def _enter_container(self, container_def: "FormItemDef | None") -> None:
        if container_def:
            self._add_container(container_def)

            self._container_ids.append(container_def.item_id)
        else:
            self._container_ids.append(None)

    def _exit_container(self) -> "str | None":
        item_id = self._container_ids.pop()

        return item_id

    def _current_container(self) -> "FormItemDef | None":
        if not self._container_ids:
            raise AssertionError("No form containers defined yet!")

        if self._container_ids[-1] is None:
            return None

        current_dataset_def = self._current_dataset()
        current_container = self._find_form_item(
            self._container_ids[-1], current_dataset_def.form_config
        )

        if current_container is None:
            raise AssertionError(
                f"Current container with id {self._container_ids[-1]} not found!"
            )

        return current_container

    def _get_label(self, sheet_row: ParsedSheetRow) -> str:
        label = ""
        default_language = self._xlsform_settings["default_language"].lower()
        if default_language:
            label_key = f"label::{default_language}"

            if sheet_row.get(label_key):
                label = strip_html(sheet_row[label_key] or "")

        if not label:
            logger.debug(
                "Label for default language `%s` not found in row index %d, falling back to `label` column!",
                default_language,
                sheet_row.idx,
            )

            label = strip_html(sheet_row["label"] or "")

        return label.strip()

    def get_row_label(self, sheet_row: ParsedSheetRow) -> str:
        label = self._get_label(sheet_row)

        existing_labels = [f.alias for f in self._current_dataset().fields]
        unique_label = get_unique_label(label, existing_labels)

        if label != unique_label:
            logger.warning(
                "Duplicate label `%s` found in dataset `%s`, renamed to `%s` to ensure uniqueness!",
                label,
                self._current_dataset().name,
                unique_label,
            )

        return unique_label

    def _get_field_def_alias(self, sheet_row: ParsedSheetRow) -> AliasDef:
        alias_str = self.get_row_label(sheet_row)

        if not alias_str:
            return AliasSimpleDef()

        alias_expression = self.get_expression(
            alias_str,
            sheet_row["name"],
            ParserType.TEMPLATE,
            should_strip_tags=True,
        )

        if alias_expression.is_str():
            return AliasSimpleDef(alias=alias_str)

        return AliasWithExpressionDef(
            alias_expression=alias_expression.to_qgis(),
        )

    def _get_field_def(self, sheet_row: ParsedSheetRow) -> WeakFieldDef:
        field_def = WeakFieldDef()
        xlsform_type = get_xlsform_type(sheet_row["type"])
        field_name = str(sheet_row["name"]).strip()
        field_type = XLS_TYPES_MAP.get(xlsform_type)

        if not field_type:
            logger.debug("Couldn't determine the type for `%s`!", field_name)

            return WeakFieldDef()

        self._check_xlsform_type_compatibility(xlsform_type)

        field_def.update(cast("WeakFieldDef", self._get_field_def_alias(sheet_row)))
        field_def.update(self._get_field_constraints_config(sheet_row))

        # you cannot define both `calculation` and `default` at the same time, in such case use only `calculation`
        if sheet_row["calculation"] and sheet_row["default"]:
            logger.warning(
                "Both `calculation` and `default` are set for field `%s`; only calculation will be used.",
                field_name,
            )

        # handle default value from either `calculation` or `default` column
        if sheet_row["calculation"]:
            default_value_expression = self.get_expression(
                sheet_row["calculation"], field_name
            ).to_qgis()

            field_def.update(
                {
                    "default_value": default_value_expression,
                    "set_default_value_on_update": False,
                }
            )
        elif sheet_row["default"]:
            field_def.update(self._get_field_default_config(sheet_row))

        return WeakFieldDef.from_data(
            {
                **field_def.to_dict(),
                "name": field_name,
                "type": field_type,
            }
        )

    def _get_field_default_config(self, sheet_row: ParsedSheetRow) -> dict[str, Any]:
        field_default_config = {}

        if "${last-saved" not in sheet_row["default"]:
            is_digit = sheet_row["default"].replace(".", "", 1).isdigit()

            if is_digit:
                default_value_expression = sheet_row["default"]
            else:
                # TODO @suricactus: handle escaping of quotes inside the string
                default_value_expression = f"'{sheet_row['default']}'"

            field_default_config.update(
                {
                    "default_value": default_value_expression,
                    "set_default_value_on_update": False,
                }
            )
        else:
            # TODO @suricactus: handle last-saved functionality, skipping for now
            pass

        return field_default_config

    def _get_field_constraints_config(
        self, sheet_row: ParsedSheetRow
    ) -> dict[str, Any]:
        field_name = str(sheet_row["name"]).strip()
        indices = self.survey_sheet.indices

        constraint_expression = ""
        constraint_expression_description = ""
        constraint_expression_strength: ConstraintStrength = "not_set"

        if sheet_row["constraint"]:
            constraint_str = str(sheet_row["constraint"]).strip()
            constraint_expression = self.get_expression(
                constraint_str, field_name
            ).to_qgis()

            if constraint_expression:
                constraint_expression_strength = "hard"

            if sheet_row["constraint_message"]:
                constraint_expression_description = str(
                    sheet_row["constraint_message"]
                ).strip()

        is_not_null = False
        is_not_null_strength: ConstraintStrength = "not_set"

        if indices["required"] != -1:
            required_str = str(sheet_row["required"]).strip().lower()

            if required_str == "yes":
                is_not_null = True
                is_not_null_strength = "hard"

        return {
            "constraint_expression": constraint_expression,
            "constraint_expression_description": constraint_expression_description,
            "constraint_expression_strength": constraint_expression_strength,
            "is_not_null": is_not_null,
            "is_not_null_strength": is_not_null_strength,
        }

    def _check_xlsform_type_compatibility(self, xlsform_type: str) -> None:
        if xlsform_type == "barcode":
            if not self._field_compatibilities.get("barcode"):
                self._field_compatibilities["barcode"] = True

                logger.info(
                    "Barcode functionality is only available through QField; it will be a simple text field in QGIS"
                )
        elif xlsform_type in (
            "image",
            "audio",
            "video",
            "background-audio",
            "background-audio",
        ):
            if xlsform_type == "background-audio":
                logger.warning("Unsupported type background-audio, using audio instead")

            if not self._field_compatibilities.get("media"):
                self._field_compatibilities["media"] = True

                logger.info(
                    "Multimedia content can be captured using QField on devices with cameras and microphones; in QGIS, pre-existing files can be selected."
                )

        elif xlsform_type in ("username", "email"):
            if not self._field_compatibilities.get("metadata"):
                self._field_compatibilities["metadata"] = True

                logger.info(
                    'The metadata "username" and "email" is only available through QFieldCloud; it will return an empty value in QGIS'
                )
        else:
            # no compatibility warnings, horray!
            pass

    def _get_xlsform_settings(self) -> XlsformSettings:
        settings_rows = list(self.settings_sheet)
        settings: XlsformSettings = {
            "form_title": "Untitled Survey",
            "form_id": "survey",
            "default_language": "",
            "version": datetime.now(tz=timezone.utc).isoformat(timespec="minutes"),
            "instance_name": '"uuid"',
        }

        if not settings_rows:
            return settings

        # let's assume there is only one row and ignore the rest
        settings_row = settings_rows[0]

        if settings_row.get("form_title"):
            settings["form_title"] = settings_row["form_title"]

        if settings_row.get("form_id"):
            settings["form_id"] = settings_row["form_id"]

        if settings_row.get("default_language"):
            settings["default_language"] = settings_row["default_language"]

        if settings_row.get("version"):
            settings["version"] = settings_row["version"]

        if settings_row.get("instance_name"):
            settings["instance_name"] = settings_row["instance_name"]

        return settings

    def get_display_expression(self, xlsform_expression: "str | None") -> str:
        if not xlsform_expression:
            return ""

        display_expression = self.get_expression(
            xlsform_expression,
            "instance_name",
            ParserType.EXPRESSION,
        ).to_qgis()

        return display_expression

    def to_json(self) -> dict[str, Any]:
        self.convert()

        project_def = ProjectDef(
            project=ProjectMetadataDef(
                custom_properties={
                    "qfieldsync/maximumImageWidthHeight": self._max_pixels or 0,
                    "qfieldsync/initialMapMode": "digitize",
                    "qfieldsync/featureFormWizardModeEnabled": True,
                },
                crs=self._project_crs,
                author=self._project_author,
                title=self._xlsform_settings["form_title"],
                extent=self.get_project_extent(),
            ),
            datasets=[
                DatasetGroupDef(
                    vector_datasets=self.vector_datasets,
                    raster_datasets=self.raster_datasets,
                )
            ],
            legend_tree=self.legend_tree,
            relations=self.relations,
            polymorphic_relations=[],
            version="1.0",
        )

        return project_def.to_dict()

    def convert(self) -> None:
        assert self.survey_sheet
        assert self.settings_sheet
        assert self.choices_sheet

        self.vector_datasets.extend(self._get_choices_datasets())

        display_expression = self.get_display_expression(
            self._xlsform_settings["instance_name"]
        )
        layer_id = "survey_layer"
        layer_name = "Survey"
        self._enter_vector_dataset(
            generate_vector_dataset_def(
                layer_id=layer_id,
                name=layer_name,
                primary_key="uuid",
                crs=self._project_crs,
                fields=[
                    generate_uuid_field_def(),
                ],
                custom_properties={
                    "QFieldSync/cloud_action": "offline",
                    "QFieldSync/action": "offline",
                },
                display_expression=display_expression,
                layer_type="vector",
            )
        )

        self.build_survey_form()

        if self._project_basemap_url:
            self.add_basemap_layer()

    def build_survey_form(self) -> None:
        # use the top most "layer_id" from the stack to find the respective layer definition
        geometry_type_by_layer_id: dict[str, GeometryType] = {}

        for row in self.survey_sheet:
            try:
                # The active container stack determines where generated form items
                # are inserted in the nested form tree.
                layer_id = self._layer_ids[-1]
                dataset_def = self.find_vector_dataset(layer_id)

                assert dataset_def is not None

                if not row["type"]:
                    logger.debug(
                        "Skipping row with empty `type` at row index %d!", row.idx
                    )

                    continue

                result = self._parse_form_row(row)

                dataset_def.fields.extend(result.fields)
                dataset_def.virtual_fields.extend(result.virtual_fields)

                for form_item_def in result.form_items:
                    self._add_form_item(form_item_def)

                # TODO @suricactus: find a better place for `max_pixels` logic
                if row["type"] == "image":
                    self._update_max_pixels(row)

                if result.geometry_type:
                    if layer_id in geometry_type_by_layer_id:
                        logger.warning(
                            "Multiple geometry types defined for layer `%s`; using the first one `%s`",
                            dataset_def.name,
                            geometry_type_by_layer_id[layer_id],
                        )

                        continue

                    geometry_type_by_layer_id[layer_id] = result.geometry_type

            except NotImplementedError as err:
                logger.error(
                    "Functionality not implemented for row with type `%s` and name `%s`: %s",
                    row["type"],
                    row["name"],
                    str(err),
                )
            except Exception:
                logger.error(
                    "Failed to parse row with type `%s` and name `%s` at row index %d!",
                    row["type"],
                    row["name"],
                    row.idx,
                )

                raise

        for layer_id, geometry_type in geometry_type_by_layer_id.items():
            dataset_def = self.find_vector_dataset(layer_id)

            assert dataset_def is not None
            assert geometry_type is not None

            dataset_geometry_type = geometry_type
            if self._use_multipart_geoms:
                multipart_geometry_types: dict[GeometryType, GeometryType] = {
                    "Point": "MultiPoint",
                    "LineString": "MultiLineString",
                    "Polygon": "MultiPolygon",
                }
                dataset_geometry_type = multipart_geometry_types.get(
                    geometry_type, geometry_type
                )

            dataset_def.geometry_type = dataset_geometry_type

    def add_basemap_layer(self) -> None:
        layer_id = "basemap_layer"
        basemap_dataset_def = generate_raster_dataset_def(
            crs="EPSG:3857",
            layer_id=layer_id,
            datasource=self._project_basemap_url,
            name=self._project_basemap_name,
            layer_type="raster",
        )

        self.raster_datasets.append(basemap_dataset_def)
        self.legend_tree.children.append(
            LegendTreeLayerDef(
                layer_id=layer_id,
                item_id=f"layer_{layer_id}",
                name=self._project_basemap_name,
                is_checked=True,
            )
        )

    def _parse_form_row(  # noqa: PLR0912, PLR0915
        self, row: ParsedSheetRow
    ) -> ParsedSheetRowResult:
        result = ParsedSheetRowResult()

        widget_type_cb = self.widget_registry.get(row["type"])

        if not widget_type_cb:
            logger.warning("Unsupported xlsform type: %s, skipping!", row["type"])

            return result

        # unsupported xlsform column `trigger`
        if row["trigger"]:
            logger.warning("Triggers are not supported yet, ignoring!")

        # we start with some defaults that are common for all field and widget types
        field_default: WeakFieldDef = self._get_field_def(row)
        form_item_default = WeakFormItemDef()

        if row["relevant"]:
            visibility_expr = self.get_expression(
                row["relevant"], row["name"]
            ).to_qgis()
        else:
            visibility_expr = ""

        if visibility_expr:
            form_item_default.visibility_expression = visibility_expr

        parsed_row = widget_type_cb(WidgetContext(self, row))

        # If `group_status` is `GroupStatus.END`, the current container is popped
        # from the stack and no new element is added.
        if parsed_row.group_status == GroupStatus.BEGIN:
            container_item = generate_form_item_def(type=self.get_form_group_type())
            container_item.update(
                {
                    **form_item_default.to_dict(),
                    **parsed_row.form_container,
                }
            )
            self._enter_container(container_item)
        # alternatively, we could do call get_form recursively:
        # self.get_form(parsed_row.form_container["item_id"])
        elif parsed_row.group_status == GroupStatus.END:
            self._exit_container()

        if parsed_row.relation:
            assert parsed_row.form_field is not None
            assert parsed_row.form_field.type == "relation"

            self.relations.append(
                generate_relation_def(
                    **parsed_row.relation,
                )
            )

            form_item = generate_form_item_def()
            form_item.update(
                {
                    "visibility_expression": visibility_expr,
                    "is_label_on_top": True,
                    **form_item_default.to_dict(),
                    **parsed_row.form_field.to_dict(),
                }
            )
            self._add_form_item(form_item)

        # Determine the layer id for the current form item.
        # If `layer_status` is `layerStatus.END``, then the last layer id is popped from the stack and no new element is added.
        if parsed_row.layer_status == LayerStatus.BEGIN:
            dataset = generate_vector_dataset_def()
            dataset.update(parsed_row.layer)
            self._enter_vector_dataset(dataset)
        elif parsed_row.layer_status == LayerStatus.END:
            self._exit_dataset()

        if parsed_row.geometry_type:
            assert not parsed_row.layer
            assert not parsed_row.form_field
            assert not parsed_row.form_container
            assert not parsed_row.field

            result.geometry_type = parsed_row.geometry_type

        if parsed_row.field or parsed_row.virtual_field:
            assert not parsed_row.form_container
            assert bool(parsed_row.field) != bool(parsed_row.virtual_field)

            field = generate_field_def()

            parsed_field = parsed_row.field or parsed_row.virtual_field
            field.update(
                {
                    **field_default.to_dict(),
                    **parsed_field.to_dict(),
                }
            )

            self._prune_field_definition(field)

            if parsed_row.field:
                result.fields.append(field)
            elif parsed_row.virtual_field:
                result.virtual_fields.append(field)
            else:
                raise AssertionError("Either `field` or `virtual_field` must be set!")

            form_item = generate_form_item_def(type="field")
            form_item.update(
                {
                    "is_label_on_top": True,
                    **form_item_default.to_dict(),
                    **parsed_row.form_field.to_dict(),
                    "field_name": field.name,
                }
            )
            result.form_items.append(form_item)
        elif (
            parsed_row.form_container
            and parsed_row.group_status == GroupStatus.NONE
            and parsed_row.layer_status == LayerStatus.NONE
        ):
            container_item = generate_form_item_def()
            container_item.update(
                {
                    **parsed_row.form_container,
                }
            )
            self._add_container(container_item)

        return result

    def _prune_field_definition(self, field_def: FieldDef) -> None:
        # NOTE Hidden fields should not be required, have a constraint expression or be unique,
        # as they are not visible in the form and the user cannot interact with them.
        if field_def.widget_type == "Hidden":
            if field_def.is_not_null_strength == "hard":
                logger.debug(
                    "Field `%s` has not null constraint strength set to `hard` but has a `Hidden` widget; this will prevent saving the form, therefore the constraint strength will be downgraded to `soft`!",
                    field_def.name,
                )

                field_def.is_not_null_strength = "soft"

            if field_def.constraint_expression_strength == "hard":
                logger.debug(
                    "Field `%s` has constraint expression strength set to `hard` but has a `Hidden` widget; this is not a valid combination and the constraint expression will be downgraded to `soft`!",
                    field_def.name,
                )

                field_def.constraint_expression_strength = "soft"

            if field_def.is_unique_strength == "hard":
                logger.debug(
                    "Field `%s` has unique constraint strength set to `hard` but has a `Hidden` widget; this is not a valid combination and the unique constraint will be downgraded to `soft`!",
                    field_def.name,
                )

                field_def.is_unique_strength = "soft"

    def _get_choices_columns(self, list_choices: list[ChoicesDef]) -> list[str]:
        # The additional columns are most likely related to a single choice group,
        # so we need to iterate over all rows for the given choice group and collect the columns that are non-empty.
        columns_set: set[str] = {"name", "label", "list_name"}
        for list_choices_row in list_choices:
            for additional_column in list_choices_row.additional_columns:
                if list_choices_row.additional_columns[additional_column] is not None:
                    columns_set.add(additional_column)

        columns_ordered = sorted(columns_set)

        return columns_ordered

    def _get_choices_record(
        self,
        columns: list[str],
        raw_choice_record: "ChoicesDef | None",
    ) -> ChoicesDef:
        record_data: dict[str, Any] = {
            "additional_columns": {},
        }

        for column in columns:
            if column in ("name", "label", "list_name"):
                value = getattr(raw_choice_record, column, None)
                record_data[column] = value
            else:
                if raw_choice_record is None:
                    value = None
                else:
                    value = raw_choice_record.additional_columns.get(column, None)

                record_data["additional_columns"][column] = value

        return ChoicesDef(**record_data)

    def _get_choices_by_list(self) -> dict[str, list[ChoicesDef]]:
        assert self.choices_sheet

        choices: dict[str, list[ChoicesDef]] = defaultdict(list)

        last_list_name = None

        for idx, row in enumerate(self.choices_sheet, 1):
            if not row["list_name"]:
                logger.debug(
                    "Skipping row with empty `list_name` in choices at row %d!", idx
                )

                last_list_name = None

                continue

            # the choices from a single list must be consecutive values
            if last_list_name is not None and last_list_name != row["list_name"]:
                assert row["list_name"] not in choices

            label = self._get_label(row)
            existing_labels = [c.label for c in choices[row["list_name"]]]
            unique_label = get_unique_label(label, existing_labels)

            if label != unique_label:
                logger.warning(
                    "Duplicate label `%s` found in choices `%s`, renamed to `%s` to ensure uniqueness!",
                    label,
                    row["list_name"],
                    unique_label,
                )

            last_list_name = row["list_name"]
            choice = ChoicesDef(
                name=str(row["name"]).strip(),
                label=unique_label,
                list_name=row["list_name"],
            )

            for col_name, col_value in row.items():
                if col_name in ("name", "label", "list_name"):
                    continue

                if not col_name:
                    logger.debug(
                        "Empty value for `%s` in choices at row %d, using empty string as default!",
                        col_name,
                        idx,
                    )

                    continue

                choice.additional_columns[col_name] = col_value

            choices[row["list_name"]].append(choice)

        cleaned_choices_by_list: dict[str, list[ChoicesDef]] = {}

        for list_name, raw_choice_records in choices.items():
            columns = self._get_choices_columns(raw_choice_records)

            cleaned_choices = [
                # We always add an empty option
                self._get_choices_record(
                    columns, ChoicesDef(name="", label="", list_name=list_name)
                ),
            ]

            for raw_choice_record in raw_choice_records:
                cleaned_choices.append(
                    self._get_choices_record(columns, raw_choice_record)
                )

            cleaned_choices_by_list[list_name] = cleaned_choices

        return cleaned_choices_by_list

    def _get_choices_datasets(self) -> list[VectorDatasetDef]:
        choices_datasets: list[VectorDatasetDef] = []
        choice_values_by_list_name = self._get_choices_by_list()

        for list_name, list_choices in choice_values_by_list_name.items():
            layer_id = build_choices_layer_id(list_name)
            layer_name = build_choices_layer_name(list_name)

            fields = []
            for col_name in list_choices[0].to_dict():
                if col_name in ("list_name", "additional_columns"):
                    continue

                fields.append(
                    generate_field_def(
                        name=col_name,
                        type="string",
                        widget_type="TextEdit",
                    ),
                )
            for col_name in list_choices[0].additional_columns:
                fields.append(
                    generate_field_def(
                        name=col_name,
                        type="string",
                        widget_type="TextEdit",
                    ),
                )

            data = []
            for list_choice in list_choices:
                # Drop the `list_name` and `additional_columns` keys from the feature attributes
                record = {
                    key: list_choice.to_dict()[key]
                    for key in list_choice.to_dict()
                    if key not in ("list_name", "additional_columns")
                }
                record.update(list_choice.additional_columns)

                data.append(record)

            choices_datasets.append(
                generate_vector_dataset_def(
                    layer_id=layer_id,
                    name=layer_name,
                    crs="",
                    fields=fields,
                    is_private=True,
                    custom_properties={
                        "QFieldSync/cloud_action": "no_action",
                        "QFieldSync/action": "copy",
                    },
                    data=data,
                    is_identifiable=False,
                    is_searchable=False,
                    is_removable=False,
                )
            )

        return choices_datasets

    def get_project_extent(self) -> str:
        if self._project_extent:
            return self._project_extent

        return ""

    def _update_max_pixels(self, row: ParsedSheetRow) -> None:
        # the current image field does not have parameters set, return the previous value
        if not row["parameters"]:
            return

        image_max_pixels_matches = re.search(
            r"max-pixels=\s*([0-9]+)", row["parameters"], flags=re.IGNORECASE
        )

        # the current image field does not have max-pixels parameter, return the previous value
        if not image_max_pixels_matches:
            return

        image_max_pixels = int(image_max_pixels_matches.group(1))

        # the current image field has the same max-pixels parameter as the previous one, return the value
        if image_max_pixels == self._max_pixels:
            return

        if self._max_pixels is None:
            self._max_pixels = image_max_pixels
            return

        logger.warning(
            "Due to the presence of a mix of image attributes having max-pixels parameter of varying values, the largest max-pixels value will be applied"
        )
        self._max_pixels = max(image_max_pixels, self._max_pixels)
