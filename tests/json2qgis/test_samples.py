import json
from importlib.resources import files

import pytest

from convert2qgis.json2qgis.utils import get_schema_validator


def test_sample_json_matches_schema() -> None:
    pytest.importorskip("fastjsonschema")
    sample_path = files("convert2qgis").joinpath("samples/json2qgis/sample.json")

    get_schema_validator()(json.loads(sample_path.read_text()))
