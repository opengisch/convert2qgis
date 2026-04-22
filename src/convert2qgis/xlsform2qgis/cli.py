import argparse

from convert2qgis.xlsform2qgis.qgis_utils import start_app
from convert2qgis.xlsform2qgis.xlsform2qgis import convert_xlsform


def main():
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
