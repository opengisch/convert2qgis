import argparse
import json

from json2qgis.json2qgis import ProjectCreator


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
        default="output/project.qgs",
        help="Path to the output QGIS project file",
    )

    args = parser.parse_args()

    project_def = json.load(args.json_file)

    creator = ProjectCreator(project_def)
    creator.build("output/project.qgs")
