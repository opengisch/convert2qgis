import json
from pathlib import Path

import pytest

from convert2qgis.json2qgis.utils import get_schema_validator


def test_sample_json_matches_schema() -> None:
    pytest.importorskip("fastjsonschema")
    sample_path = Path(__file__).parents[2].joinpath("samples/sample.json")

    get_schema_validator()(json.loads(sample_path.read_text()))
