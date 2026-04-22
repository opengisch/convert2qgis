import json
import logging
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, cast

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
    get_xlsform_type,
    strip_html,
)
from convert2qgis.xlsform2qgis.expressions.expression import (
    Expression,
    ExpressionContext,
    ParserType,
)
from convert2qgis.xlsform2qgis.expressions.parser import ParseError
from convert2qgis.xlsform2qgis.qgis_utils import set_survey_features, start_app
from convert2qgis.xlsform2qgis.sheet_parser import ParsedSheet, ParsedSheetRow
from convert2qgis.xlsform2qgis.type_defs import (
    ConverterSettings,
    GroupStatus,
    LayerStatus,
    XlsformSettings,
)
from convert2qgis.xlsform2qgis.widgets import WidgetContext, WidgetRegistry

logger = logging.getLogger(__package__)

try:
    from convert2qgis.xlsform2qgis.qgis_utils import QtSignalsHandler

    logger_handler = QtSignalsHandler(level=logging.INFO)
    logger.addHandler(logger_handler)

    logger.debug("The logger will also emit pyQt signals!")
except Exception:
    pass


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


class XlsformConverterError(Exception):
    """Base error class for XLSForm conversion errors."""

    pass


def parse_xlsform_sheets(
    xlsform_filename: PathOrStr,
) -> tuple[ParsedSheet, ParsedSheet, ParsedSheet]:
    """Extract the survey, choices and settings sheets from the given XLSForm file."""
    logger.debug(f"Parsing XLSForm file: {xlsform_filename}")

    xlsform_filename = Path(xlsform_filename)
    if not xlsform_filename.exists():
        raise FileNotFoundError(f"XLSForm file not found: {xlsform_filename}")

    xlsform_filename = Path(xlsform_filename)
    if not xlsform_filename.exists():
        raise FileNotFoundError(f"XLSForm file not found: {xlsform_filename}")

    try:
        survey_sheet = ParsedSheet("survey", xlsform_filename)
        choices_sheet = ParsedSheet("choices", xlsform_filename)
        settings_sheet = ParsedSheet("settings", xlsform_filename)
    except ValueError as err:
        raise XlsformConverterError(
            f'Expected the provided spreadsheet to contain sheets named "survey", "choices" and "settings", but got an error: {err}'
        ) from err

    return (survey_sheet, choices_sheet, settings_sheet)


def convert_xlsform(
    xlsform_filename: PathOrStr,
    *,
    output_dir: PathOrStr | None = None,
    settings: ConverterSettings | None = None,
    skip_failed_expressions: bool = False,
    json_filename: PathOrStr | None = None,
):
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
        )

    raise ValueError("Either `output_dir` or `json_filename` must be provided!")


def convert_xlsform_to_json(
    xlsform_filename: PathOrStr,
    *,
    settings: ConverterSettings | None = None,
    skip_failed_expressions: bool = False,
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
        raise ValueError("Invalid XLSForm file!")

    return converter.to_json()


def convert_xlsform_to_qgis_project(
    xlsform_filename: PathOrStr,
    output_dir: PathOrStr,
    *,
    settings: ConverterSettings | None = None,
    survey_features: QgsFeatureSource | None = None,
    skip_failed_expressions: bool = False,
    json_filename: PathOrStr | None = None,
) -> QgsProject:
    project_json = convert_xlsform_to_json(
        xlsform_filename,
        settings=settings,
        skip_failed_expressions=skip_failed_expressions,
    )

    if json_filename:
        logger.info("Writing intermediate JSON representation to file: {}".format(json_filename))

        json_filename = Path(json_filename)
        json_filename.parent.mkdir(parents=True, exist_ok=True)

        with json_filename.open("w") as json_file:
            json.dump(project_json, json_file, sort_keys=True, indent=2)

    creator = ProjectCreator(project_json)
    project = creator.build(output_dir)

    if survey_features is not None and survey_features.featureCount() >= 1:
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

    _form_group_type: FormItemGroupTypes = "group_box"
    """The form group type to use for non-root groups in the form. By default it is set to `group_box`, but it can be set to `tab` if the user prefers a more tabbed form structure."""

    _root_form_group_type: FormItemGroupTypes
    """Similar to `_form_group_type`, but specifically for the root level form groups, to allow more flexibility in the form structure definition. By default it is set to `tab` to encourage better form organization, but it can be set to `group_box` if the user prefers a flatter form structure."""

    _project_crs: CrsDef
    """The project CRS to be defined on the output project."""

    _project_author: str
    """The project author of the output project."""

    _project_extent: str
    """The project extent of the output project as a list of coordinates (xmin, ymin, xmax, ymax) in project CRS."""

    _layer_ids: list[str]
    """Stack to keep track of the current layer ids while parsing the survey sheet, to be able to assign fields and form items to the correct layer. Whenever a new layer is defined, its id is pushed to the stack, and whenever a layer definition ends, it is popped from the stack."""

    _container_ids: list[str | None]
    """Stack to keep track of the current parent container ids while parsing the survey sheet, to be able to assign form items to the correct parent container. Whenever a new container is defined, its id is pushed to the stack, and whenever a container definition ends, it is popped from the stack. The value `None` is used to represent the root level, where there is no parent container."""

    def __init__(
        self,
        survey_sheet: ParsedSheet,
        choices_sheet: ParsedSheet,
        settings_sheet: ParsedSheet,
        settings: ConverterSettings | None = None,
        skip_failed_expressions: bool = False,
    ) -> None:
        settings = settings or {}

        self.survey_sheet = survey_sheet
        self.choices_sheet = choices_sheet
        self.settings_sheet = settings_sheet

        self._skip_failed_expressions = skip_failed_expressions

        # settings
        self._form_group_type = settings.get("form_group_type") or "group_box"
        self._root_form_group_type = settings.get("root_form_group_type") or "tab"
        self._project_crs = settings.get("crs") or "EPSG:3857"
        self._project_author = settings.get("author") or ""
        self._project_extent = settings.get("extent", "").strip() or ""
        self._xlsform_settings = {
            **self._get_xlsform_settings(),
            **settings.get("xlsform_settings", {}),
        }

        basemap_url = settings.get("basemap_url", None)
        if basemap_url:
            basemap_name = settings.get("basemap_name") or _FALLBACK_BASEMAP_NAME
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

    def is_valid(self) -> bool:
        if not self.survey_sheet.layer.isValid():
            return False

        # Missing the two basic parameters that must be present within the survey layer
        if self.survey_sheet.indices["type"] == -1:
            return False

        if self.survey_sheet.indices["name"] == -1:
            return False

        return True

    @property
    def all_datasets(self) -> list[DatasetDef]:
        return [*self.vector_datasets, *self.raster_datasets]

    def find_vector_dataset(self, layer_id: str) -> VectorDatasetDef | None:
        for dataset_def in self.vector_datasets:
            if dataset_def.layer_id == layer_id:
                return dataset_def

        return None

    def get_form_group_type(self) -> FormItemGroupTypes:
        if len(self._container_ids) == 0 or self._container_ids[-1] is None:
            return self._root_form_group_type

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
        except ParseError as err:
            logger.error(f"Failed to parse expression `{expression_str}` for field `{current_field}`: {err}")

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

        form_item = generate_form_item_def(
            item_id=f"tab_item_{layer_id}",
            type=self.get_form_group_type(),
            label=layer_name,
            parent_id=None,
        )
        self._enter_container(form_item)

    def _exit_dataset(self) -> str:
        layer_id = self._layer_ids.pop()

        self._exit_container()

        return layer_id

    def _current_dataset(self) -> VectorDatasetDef:
        if not self._layer_ids:
            raise ValueError("No layers defined yet!")

        layer_id = self._layer_ids[-1]
        dataset_def = self.find_vector_dataset(layer_id)

        if not dataset_def:
            raise ValueError(f"Current layer with id {layer_id} not found!")

        return dataset_def

    def _add_container(self, container_def: FormItemDef) -> None:
        current_dataset_def = self._current_dataset()
        current_dataset_def.form_config.append(container_def)

    def _enter_container(self, container_def: FormItemDef | None) -> None:
        if container_def:
            self._add_container(container_def)

            self._container_ids.append(container_def.item_id)
        else:
            self._container_ids.append(None)

    def _exit_container(self) -> str | None:
        item_id = self._container_ids.pop()

        return item_id

    def _current_container(self) -> FormItemDef | None:
        if not self._container_ids:
            raise ValueError("No form containers defined yet!")

        if self._container_ids[-1] is None:
            return None

        current_dataset_def = self._current_dataset()

        for form_item_def in reversed(current_dataset_def.form_config):
            if form_item_def.item_id == self._container_ids[-1]:
                return form_item_def

        raise AssertionError(f"Current container with id {self._container_ids[-1]} not found!")

    def _get_label(self, sheet_row: ParsedSheetRow) -> str:
        label = ""
        default_language = self._xlsform_settings["default_language"].lower()
        if default_language:
            label_key = f"label::{default_language}"

            if sheet_row.get(label_key):
                label = strip_html(sheet_row[label_key] or "")

        if not label:
            logger.debug(
                f"Label for default language `{default_language}` not found in row index {sheet_row.idx}, falling back to `label` column!"
            )

            label = strip_html(sheet_row["label"] or "")

        return label

    def _get_field_def_alias(self, sheet_row: ParsedSheetRow) -> AliasDef:
        alias_str = self._get_label(sheet_row)

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
        field_type = XLS_TYPES_MAP.get(xlsform_type, None)

        if not field_type:
            logger.debug(f"Couldn't determine the type for `{field_name}`!")

            return WeakFieldDef()

        self._check_xlsform_type_compatibility(xlsform_type)

        field_def.update(cast(WeakFieldDef, self._get_field_def_alias(sheet_row)))
        field_def.update(self._get_field_constraints_config(sheet_row))

        # you cannot define both `calculation` and `default` at the same time, in such case use only `calculation`
        if sheet_row["calculation"] and sheet_row["default"]:
            logger.warning("Both `calculation` and `default` are set; only calculation will be used")

        # handle default value from either `calculation` or `default` column
        if sheet_row["calculation"]:
            default_value_expression = self.get_expression(sheet_row["calculation"], field_name).to_qgis()

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

    def _get_field_constraints_config(self, sheet_row: ParsedSheetRow) -> dict[str, Any]:
        field_name = str(sheet_row["name"]).strip()
        indices = self.survey_sheet.indices

        constraint_expression = ""
        constraint_expression_description = ""
        constraint_expression_strength: ConstraintStrength = "not_set"

        if sheet_row["constraint"]:
            constraint_str = str(sheet_row["constraint"]).strip()
            constraint_expression = self.get_expression(constraint_str, field_name).to_qgis()

            if constraint_expression:
                constraint_expression_strength = "hard"

            if sheet_row["constraint_message"]:
                constraint_expression_description = str(sheet_row["constraint_message"]).strip()

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
        if xlsform_type in ("barcode",):
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
                    'The metadata "username" and "email" is only available through QFieldCloud; it will return an empty value in QGIS'.format()
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
            "version": datetime.now().isoformat(timespec="minutes"),
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

    def get_display_expression(self, xlsform_expression: str | None) -> str:
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
                    "qfieldsync/maximumImageWidthHeight": 0,
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

        display_expression = self.get_display_expression(self._xlsform_settings["instance_name"])
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
                    "qfieldsync/cloud_action": "offline",
                    "qfieldsync/action": "offline",
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
        max_pixels: int | None = None
        geometry_type_by_layer_id: dict[str, GeometryType] = {}

        for row in self.survey_sheet:
            try:
                # If there are not `parent_ids`, it means we are at the root level
                # the form item's `parent_id` set to `None` represents that.
                layer_id = self._layer_ids[-1]
                dataset_def = self.find_vector_dataset(layer_id)

                assert dataset_def is not None

                if not row["type"]:
                    logger.debug(f"Skipping row with empty `type` at row index {row.idx}!")

                    continue

                row_field_defs, row_form_item_defs, row_geometry_type = self._parse_form_row(row)

                dataset_def.fields.extend(row_field_defs)
                dataset_def.form_config.extend(row_form_item_defs)

                # TODO find a better place for `max_pixels` logic
                if row["type"] == "image":
                    max_pixels = self._get_field_settings_max_pixels(row, max_pixels)

                if row_geometry_type:
                    if layer_id in geometry_type_by_layer_id:
                        logger.warning(
                            f"Multiple geometry types defined for layer `{dataset_def.name}`; using the first one `{row_geometry_type}`"
                        )

                        continue

                    geometry_type_by_layer_id[layer_id] = row_geometry_type

            except Exception as err:
                logger.error(
                    f"Failed to parse row with type `{row['type']}` and name `{row['name']}` at row index {row.idx}: {err}"
                )

                raise

        for layer_id, geometry_type in geometry_type_by_layer_id.items():
            dataset_def = self.find_vector_dataset(layer_id)

            assert dataset_def is not None
            assert geometry_type is not None

            dataset_def.geometry_type = geometry_type

    def add_basemap_layer(self):
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

    def _parse_form_row(self, row: ParsedSheetRow) -> tuple[list[FieldDef], list[FormItemDef], GeometryType | None]:  # noqa: C901
        fields = []
        form_items = []
        geometry_type = None

        widget_type_cb = self.widget_registry.get(row["type"])

        if not widget_type_cb:
            logger.warning(f"Unsupported xlsform type: {row['type']}, skipping!")

            return [], [], None

        # unsupported xlsform column `trigger`
        if row["trigger"]:
            logger.warning("Triggers are not supported yet, ignoring!")

        # we start with some defaults that are common for all field and widget types
        field_default: WeakFieldDef = self._get_field_def(row)
        form_item_default = WeakFormItemDef()

        if row["relevant"]:
            visibility_expr = self.get_expression(row["relevant"], row["name"]).to_qgis()
        else:
            visibility_expr = ""

        if visibility_expr:
            form_item_default.visibility_expression = visibility_expr

        parsed_row = widget_type_cb(WidgetContext(self, row))
        current_container = self._current_container()

        # If the `parent_id` is `None`, it means we are at the root level
        # the form item's `parent_id` set to `None` represents that.
        if current_container is not None:
            parent_id = current_container.item_id
        else:
            parent_id = None

        # Determine the parent id for the current form item.
        # If `group_status` is `GroupStatus.END``, then the last parent id is popped from the stack and no new element is added.
        if parsed_row.group_status == GroupStatus.BEGIN:
            container_item = generate_form_item_def(type=self.get_form_group_type())
            container_item.update(
                {
                    **form_item_default.to_dict(),
                    **parsed_row.form_container,
                    "parent_id": parent_id,
                }
            )
            self._enter_container(container_item)
        # alternatively, we could do call get_form recursively:
        # self.get_form(parsed_row.form_container["item_id"])
        elif parsed_row.group_status == GroupStatus.END:
            self._exit_container()

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

            geometry_type = parsed_row.geometry_type

        if parsed_row.field:
            assert not parsed_row.form_container

            field = generate_field_def()
            field.update(
                {
                    **field_default.to_dict(),
                    **parsed_row.field.to_dict(),
                }
            )
            fields.append(field)
            form_item = generate_form_item_def(type="field")
            form_item.update(
                {
                    "is_label_on_top": True,
                    **form_item_default.to_dict(),
                    **parsed_row.form_field.to_dict(),
                    "field_name": field.name,
                    "parent_id": parent_id,
                }
            )
            form_items.append(form_item)
        elif (
            parsed_row.form_container
            and parsed_row.group_status == GroupStatus.NONE
            and parsed_row.layer_status == LayerStatus.NONE
        ):
            container_item = generate_form_item_def()
            container_item.update(
                {
                    **parsed_row.form_container,
                    "parent_id": parent_id,
                }
            )
            self._add_container(container_item)

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
                    "parent_id": parent_id,
                }
            )
            form_items.append(form_item)

        return fields, form_items, geometry_type

    def _get_choices_columns(self, list_choices: list[ChoicesDef]) -> list[str]:
        # The additional columns are most likely related to a single choice group,
        # so we need to iterate over all rows for the given choice group and collect the columns that are non-empty.
        columns_set: set[str] = set(("name", "label", "list_name"))
        for list_choices_row in list_choices:
            for additional_column in list_choices_row.additional_columns.keys():
                columns_set.add(additional_column)

        columns_ordered = sorted(columns_set)

        return columns_ordered

    def _get_choices_record(
        self,
        columns: list[str],
        raw_choice_record: ChoicesDef | None,
    ) -> ChoicesDef:
        record_data: dict[str, Any] = {
            "additional_columns": {},
        }

        for column in columns:
            value = getattr(raw_choice_record, column, None)

            if column in ("name", "label", "list_name"):
                record_data[column] = value
            else:
                record_data["additional_columns"][column] = value

        return ChoicesDef(**record_data)

    def _get_choices_by_list(self) -> dict[str, list[ChoicesDef]]:
        assert self.choices_sheet

        choices: dict[str, list[ChoicesDef]] = defaultdict(list)

        for idx, row in enumerate(self.choices_sheet, 1):
            last_list_name = None

            if not row["list_name"]:
                logger.debug(f"Skipping row with empty `list_name` in choices at row {idx}!")

                last_list_name = None

                continue

            # the choices from a single list must be consecutive values
            if last_list_name is not None and last_list_name != row["list_name"]:
                assert last_list_name not in choices

            choice = ChoicesDef(
                name=str(row["name"]).strip(),
                label=self._get_label(row),
                list_name=row["list_name"],
            )

            for col_name, col_value in row.items():
                if col_name in ("name", "label", "list_name"):
                    continue

                if not col_name:
                    logger.debug(
                        f"Empty value for `{col_name}` in choices at row {idx}, using empty string as default!"
                    )

                    continue

                choice.additional_columns[col_name] = col_value

            choices[row["list_name"]].append(choice)

        cleaned_choices_by_list: dict[str, list[ChoicesDef]] = {}

        for list_name, raw_choice_records in choices.items():
            columns = self._get_choices_columns(raw_choice_records)

            cleaned_choices = [
                # We always add an empty option
                self._get_choices_record(columns, ChoicesDef(name="", label="", list_name=list_name)),
            ]

            for raw_choice_record in raw_choice_records:
                cleaned_choices.append(self._get_choices_record(columns, raw_choice_record))

            cleaned_choices_by_list[list_name] = cleaned_choices

        return cleaned_choices_by_list

    def _get_choices_datasets(self) -> list[VectorDatasetDef]:
        choices_datasets: list[VectorDatasetDef] = []
        choice_values_by_list_name = self._get_choices_by_list()

        for list_name, list_choices in choice_values_by_list_name.items():
            layer_id = build_choices_layer_id(list_name)
            layer_name = build_choices_layer_name(list_name)

            fields = []
            for col_name in list_choices[0].to_dict().keys():
                if col_name in ("list_name", "additional_columns"):
                    continue

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
                data.append(
                    {
                        key: list_choice.to_dict()[key]
                        for key in list_choice.to_dict().keys()
                        if key not in ("list_name", "additional_columns")
                    }
                )

            choices_datasets.append(
                generate_vector_dataset_def(
                    layer_id=layer_id,
                    name=layer_name,
                    crs="EPSG:4326",
                    fields=fields,
                    is_private=True,
                    custom_properties={
                        "QFieldSync/cloud_action": "no_action",
                        "QFieldSync/action": "copy",
                    },
                    data=data,
                )
            )

        return choices_datasets

    def get_project_extent(self) -> str:
        if self._project_extent:
            return self._project_extent

        return ""

    def _get_field_settings_max_pixels(self, row, previous_max_pixels: int | None) -> int | None:
        # the current image field does not have parameters set, return the previous value
        if not row["parameters"]:
            return previous_max_pixels

        image_max_pixels_matches = re.search(r"max-pixels=\s*([0-9]+)", row["parameters"], flags=re.IGNORECASE)

        # the current image field does not have max-pixels parameter, return the previous value
        if not image_max_pixels_matches:
            return previous_max_pixels

        image_max_pixels = int(image_max_pixels_matches.group(1))

        # the current image field has the same max-pixels parameter as the previous one, return the value
        if image_max_pixels == previous_max_pixels:
            return previous_max_pixels

        if previous_max_pixels is None:
            return image_max_pixels
        else:
            logger.warning(
                "Due to the presence of a mix of image attributes having max-pixels parameter of varying values, the largest max-pixels value will be applied"
            )
            return max(image_max_pixels, previous_max_pixels)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Convert an XLSForm file to a QGIS project via JSON representation")
    parser.add_argument(
        "input_xlsform",
        type=str,
        help="Path to the input XLSForm file",
    )
    parser.add_argument(
        "--output-json",
        type=str,
    )
    parser.add_argument(
        "--output-dir",
        type=str,
    )
    parser.add_argument(
        "--skip-failed-expressions",
        action="store_true",
        help="Whether to skip failed expressions or not; if set to true, the converter will try to convert the expression and if it fails, it will log a warning and use an empty string as the expression value; if set to false, the converter will raise an error and stop the conversion process",
    )

    args = parser.parse_args()

    start_app()

    convert_xlsform(
        args.input_xlsform,
        output_dir=args.output_dir,
        json_filename=args.output_json,
        skip_failed_expressions=args.skip_failed_expressions,
    )


if __name__ == "__main__":
    main()
