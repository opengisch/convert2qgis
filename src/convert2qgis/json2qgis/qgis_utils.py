import atexit
import gc
import logging
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import cast

from qgis.core import Qgis, QgsApplication, QgsProject, QgsVectorLayer

logger = logging.getLogger(__name__)

QGISAPP: "QgsApplication | None" = None


def start_app() -> str:
    """
    Will start a QgsApplication and call all initialization code like
    registering the providers and other infrastructure. It will not load
    any plugins.

    You can always get the reference to a running app by calling `QgsApplication.instance()`.

    The initialization will only happen once, so it is safe to call this method repeatedly.

    Returns
    -------
        str: QGIS app version that was started.

    """
    global QGISAPP  # noqa: PLW0603

    if QGISAPP is None:
        logger.info(
            "Starting QGIS app version %s (%s)...", Qgis.versionInt(), Qgis.devVersion()
        )
        argvb: list[str] = []

        os.environ["QGIS_CUSTOM_CONFIG_PATH"] = tempfile.mkdtemp("", "QGIS_CONFIG")

        # Note: QGIS_PREFIX_PATH is evaluated in QgsApplication -
        # no need to mess with it here.
        gui_flag = False
        QGISAPP = QgsApplication(argvb, gui_flag)

        QGISAPP.initQgis()

        # make sure the app is closed, otherwise the container exists with non-zero
        @atexit.register
        def exitQgis() -> None:  # noqa: N802
            stop_app()

        logger.info("QGIS app started!")

    return cast("str", Qgis.version())


def stop_app() -> None:
    """Cleans up and exits QGIS"""
    global QGISAPP  # noqa: PLW0603

    # note that if this function is called from @atexit.register, the globals are cleaned up
    if "QGISAPP" not in globals():
        return

    project = QgsProject.instance()

    assert project is not None

    project.clear()

    if QGISAPP is not None:
        logger.info("Stopping QGIS app…")

        # NOTE we force run the GB just to make sure there are no dangling QGIS objects when we delete the QGIS application
        gc.collect()

        QGISAPP.exitQgis()

        del QGISAPP

        logger.info("Deleted QGIS app!")


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
