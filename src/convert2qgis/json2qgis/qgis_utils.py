import logging
import sqlite3
from pathlib import Path
from typing import cast

from qgis.core import QgsProject, QgsVectorLayer

logger = logging.getLogger(__name__)


def flush_gpkg_wal(layer: QgsVectorLayer) -> None:
    """Flushes the WAL file of a GPKG database to make sure all changes are written to the main file."""
    data_provider = layer.dataProvider()

    if data_provider is None or data_provider.storageType() != "GPKG":
        return

    filename = layer.source().split("|")[0]
    path = Path(filename).parent.joinpath(str(filename) + "-wal")

    if path.exists() and path.stat().st_size > 0:
        conn = sqlite3.connect(str(filename))

        with conn:
            logger.debug('Flushing GPKG WAL file for layer "%s"', layer.name())

            conn.execute("PRAGMA wal_checkpoint")


def flush_all_gpkg_wal(project: QgsProject) -> None:
    """Flushes the WAL file of all GPKG layers in the project to make sure all changes are written to the main file."""
    for layer in project.mapLayers().values():
        if not isinstance(layer, QgsVectorLayer):
            continue

        layer = cast("QgsVectorLayer", layer)

        data_provider = layer.dataProvider()

        if data_provider is None or data_provider.storageType() != "GPKG":
            continue

        flush_gpkg_wal(layer)
