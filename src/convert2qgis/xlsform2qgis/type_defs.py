from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, TypedDict

from convert2qgis.json2qgis.type_defs import (
    CrsDef,
    FieldDef,
    FormItemDef,
    FormItemGroupTypes,
    GeometryType,
)


class GroupStatus(str, Enum):
    NONE = "none"
    BEGIN = "start"
    END = "end"


class LayerStatus(str, Enum):
    NONE = "none"
    BEGIN = "start"
    END = "end"


class XlsformSettings(TypedDict):
    form_title: str
    form_id: str
    default_language: str
    version: str
    instance_name: str


@dataclass
class ParsedSheetRowResult:
    fields: list[FieldDef] = field(default_factory=list)
    virtual_fields: list[FieldDef] = field(default_factory=list)
    form_items: list[FormItemDef] = field(default_factory=list)
    geometry_type: Optional[GeometryType] = None


class WeakXlsformSettings(TypedDict, total=False):
    form_title: str
    form_id: str
    default_language: str
    version: str
    instance_name: str


class ConverterSettings(TypedDict, total=False):
    xlsform_settings: WeakXlsformSettings
    """XLSForm settings to override those in the "settings" sheet."""

    form_group_type: FormItemGroupTypes
    """How the groups in the XLSForm Survey form should be represented. E.g. groups or tabs."""

    root_form_group_type: FormItemGroupTypes
    """How the root groups in the XLSForm Survey form should be represented. E.g. groups or tabs."""

    basemap_url: str
    """A valid XYZ layer definition. If not provided, a default basemap will be used. If an empty string is provided, no basemap will be used."""

    crs: CrsDef
    """EPSG code of the project crs"""

    extent: str
    """The project extent of the output project as a list of coordinates (xmin, ymin, xmax, ymax) in project CRS."""

    author: str
    """Name of the author of the project generated from the XLSForm definition."""
