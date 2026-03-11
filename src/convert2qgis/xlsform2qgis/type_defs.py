from enum import StrEnum
from typing import TypedDict

from convert2qgis.json2qgis.type_defs import CrsDef, FormItemGroupTypes


class GroupStatus(StrEnum):
    NONE = "none"
    BEGIN = "start"
    END = "end"


class LayerStatus(StrEnum):
    NONE = "none"
    BEGIN = "start"
    END = "end"


class XlsformSettings(TypedDict):
    form_title: str
    form_id: str
    default_language: str
    version: str
    instance_name: str


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
    """WKT coordinates of the extent - xmin, ymin, xmax,ymax"""

    author: str
    """Name of the author of the project generated from the XLSForm definition."""
