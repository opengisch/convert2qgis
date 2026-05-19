# convert2qgis

`convert2qgis` is a Python library for creating QGIS projects from structured input.
It contains two main modules.
`xlsform2qgis` converts XLSForm surveys into QGIS project definitions and project files.
`json2qgis` converts a schema-defined JSON project definition into a QGIS project file.
This library is the heart within the [XLSFormConverter](https://github.com/opengisch/XLSFormConverter) QGIS plugin.


## xlsform2qgis

`xlsform2qgis` reads an XLSForm workbook and parses the survey, choices, and settings sheets.
It converts the parsed XLSForm into the internal JSON project definition used by this repository.
It maps XLSForm field types, widgets, labels, constraints, calculations, groups, repeats, expressions, and relations into QGIS layers, fields, edit forms, and project metadata.
The converter can write the intermediate JSON definition and can also build the final QGIS project directly.

```shell
uv run xlsform2qgis samples/xlsforms/service_rating.xlsx --output-dir ./output/service_rating
```

Use `--output-json` to also keep the generated JSON definition.

```shell
uv run xlsform2qgis samples/xlsforms/service_rating.xlsx --output-json ./output/service_rating.json --output-dir ./output/service_rating
```


## json2qgis

`json2qgis` is the lower-level project builder.
It validates and normalizes a JSON project definition.
It creates QGIS layers, fields, virtual fields, form layouts, layer tree entries, relations, project metadata, custom properties, and CRS settings.
It writes the resulting `.qgz` project.
The JSON structure is validated against the bundled schema in `src/convert2qgis/json2qgis/schema/`.

```shell
uv run json2qgis ./samples/sample.json --output-dir ./output/project
```


## Development

This project is intended to run inside an environment where the QGIS Python bindings are available.
Create the virtual environment with system site packages so Python can import QGIS.

```shell
uv venv --system-site-packages
```

Install development dependencies with `uv`.

```shell
uv sync --all-extras --dev
```

Install pre-commit hooks.

```shell
uv run pre-commit install
```


## Tests

Run the full test suite.

```shell
uv run pytest
```

Run focused test groups.

```shell
uv run pytest tests/json2qgis
uv run pytest tests/xlsform2qgis
```

Run linting.

```shell
uv run ruff check
```


## Running Locally

Generate a QGIS project from the sample JSON.

```shell
uv run json2qgis ./samples/sample.json --output-dir ./output/project
```

Generate a QGIS project from an XLSForm.

```shell
uv run xlsform2qgis path/to/survey.xlsx --output-dir ./output/project
```

Both commands initialize QGIS through the local Python bindings and write the project output to the provided directory.
