import atexit
import gc
import logging
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, cast

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCsException,
    QgsFeature,
    QgsFeatureRequest,
    QgsFeatureSink,
    QgsFeatureSource,
    QgsProject,
    QgsRectangle,
    QgsVectorLayer,
    QgsVectorLayerUtils,
)
from qgis.PyQt.QtCore import QObject, pyqtSignal

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger(__name__)

obj = QObject()

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

    assert project

    project.clear()

    if QGISAPP is not None:
        logger.info("Stopping QGIS app…")

        # NOTE we force run the GB just to make sure there are no dangling QGIS objects when we delete the QGIS application
        gc.collect()

        QGISAPP.exitQgis()

        del QGISAPP

        logger.info("Deleted QGIS app!")


def set_survey_features(  # noqa: PLR0911
    project: QgsProject, features: QgsFeatureSource
) -> "QgsRectangle | None":
    """
    Loads a given set of features into the survey layer of the project.

    Returns the extent of the added features converted to the project CRS,
    or empty extent if the extent is invalid or cannot be converted,
    or`None` if adding features failed.
    """
    survey_layer = project.mapLayer("survey_layer")

    if not survey_layer:
        logger.warning(
            obj.tr(
                "Failed to find the survey layer within the generated project to set geometries, skipping this step."
            )
        )
        return None

    if not isinstance(survey_layer, QgsVectorLayer):
        logger.warning(
            obj.tr(
                "The survey layer within the generated project is not a vector layer when trying to set geometries, skipping this step."
            )
        )
        return None

    if not survey_layer.isValid():
        logger.warning(
            obj.tr(
                "The survey layer within the generated project is invalid when trying to set geometries, skipping this step."
            )
        )
        return None

    if survey_layer.wkbType() != features.wkbType():
        logger.warning(
            obj.tr(
                "The provided features have a different geometry type than the survey layer within the generated project when trying to set geometries, skipping this step."
            )
        )
        return None

    if not survey_layer.isEditable() and not survey_layer.startEditing():
        logger.warning(
            obj.tr(
                "Failed to start editing the survey layer within the generated project to set geometries, skipping this step."
            )
        )
        return None

    data_provider = survey_layer.dataProvider()
    if data_provider is None or not bool(
        data_provider.capabilities() & Qgis.VectorProviderCapability.AddFeatures
    ):
        logger.warning(
            obj.tr(
                "The data provider of the survey layer within the generated project does not support adding features, skipping this step."
            )
        )

        return None

    if data_provider.hasErrors():
        logger.warning(
            obj.tr(
                "The data provider of the survey layer within the generated project has errors before adding features, skipping this step: %s"
            ),
            ", ".join(data_provider.errors()),
        )

        return None

    request = QgsFeatureRequest()
    request.setDestinationCrs(survey_layer.crs(), project.transformContext())
    features_iterator = cast("Iterable[QgsFeature]", features.getFeatures(request))
    for feature in features_iterator:
        output_features = QgsVectorLayerUtils.makeFeatureCompatible(
            feature,
            survey_layer,
            QgsFeatureSink.SinkFlag.RegeneratePrimaryKey,
        )
        if output_features:
            if not survey_layer.addFeature(
                output_features[0], QgsFeatureSink.Flag.FastInsert
            ):
                logger.warning(
                    obj.tr(
                        "Failed to add feature to the survey layer within the generated project, skipping this feature."
                    )
                )

    if not survey_layer.commitChanges():
        logger.warning(
            obj.tr(
                "Failed to commit changes to the survey layer within the generated project after setting geometries, skipping this step: %s"
            ),
            ", ".join(survey_layer.commitErrors()),
        )

        return None

    flush_gpkg_wal(survey_layer)

    return transform_bounding_box(
        survey_layer.extent(),
        survey_layer.crs(),
        project.crs(),
        project,
    )


def transform_bounding_box(
    extent: QgsRectangle,
    source_authid: "str | QgsCoordinateReferenceSystem",
    dest_authid: "str | QgsCoordinateReferenceSystem",
    project: QgsProject,
) -> QgsRectangle:
    if isinstance(source_authid, str):
        source_crs = QgsCoordinateReferenceSystem(source_authid)
    elif isinstance(source_authid, QgsCoordinateReferenceSystem):
        source_crs = source_authid
    else:
        raise TypeError(
            "Expected source CRS to be either a EPSG code or QgsCoordinateReferenceSystem"
        )

    if isinstance(dest_authid, str):
        dest_crs = QgsCoordinateReferenceSystem(dest_authid)
    elif isinstance(dest_authid, QgsCoordinateReferenceSystem):
        dest_crs = dest_authid
    else:
        raise TypeError(
            "Expected dest CRS to be either a EPSG code or QgsCoordinateReferenceSystem"
        )

    if not source_crs.isValid():
        logger.warning("Invalid source CRS: %s", source_authid)

        return QgsRectangle()

    if not dest_crs.isValid():
        logger.warning("Invalid destination CRS: %s", dest_authid)

        return QgsRectangle()

    transform = QgsCoordinateTransform(
        source_crs,
        dest_crs,
        project,
    )

    try:
        return transform.transformBoundingBox(extent)
    except QgsCsException as err:
        logger.warning(
            obj.tr("Failed to transform Survey layer extent to project CRS: {}").format(
                err
            )
        )

        return QgsRectangle()


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


class LoggingSignals(QObject):
    """Singleton class that has signals that are triggered by the logging class."""

    info = pyqtSignal(str)
    warning = pyqtSignal(str)
    error = pyqtSignal(str)
    debug = pyqtSignal(str)

    _instance: "LoggingSignals | None" = None

    def __new__(cls) -> "LoggingSignals":
        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance


class QtSignalsHandler(logging.Handler):
    def __init__(self, level: int = logging.NOTSET) -> None:
        super().__init__(level)

        self.signals = LoggingSignals()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)

            if record.levelno == logging.CRITICAL:
                self.signals.error.emit(msg)
            if record.levelno == logging.ERROR:
                self.signals.error.emit(msg)
            elif record.levelno == logging.WARNING:
                self.signals.warning.emit(msg)
            elif record.levelno == logging.INFO:
                self.signals.info.emit(msg)
            elif record.levelno == logging.DEBUG:
                self.signals.debug.emit(msg)
            # ignore all other levels
            else:
                pass

            self.flush()
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)
