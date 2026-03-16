import argparse
import json
import logging

from convert2qgis.json2qgis.json2qgis import ProjectCreator

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a JSON project definition into a QGIS project file."
    )
    parser.add_argument(
        "json_file",
        type=argparse.FileType("r"),
        help="Path to the JSON project definition file",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        required=True,
        help="Path to the output QGIS project file",
    )

    args = parser.parse_args()

    project_def = json.load(args.json_file)

    creator = ProjectCreator(project_def)
    creator.build(args.output)
