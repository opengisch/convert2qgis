import logging

pkg_logger = logging.getLogger(__package__)
pkg_logger.setLevel(logging.INFO)

try:
    from convert2qgis.xlsform2qgis.qgis_utils import QtSignalsHandler

    logger_handler = QtSignalsHandler(pkg_logger.level)
    pkg_logger.addHandler(logger_handler)

    pkg_logger.debug("The logger will also emit pyQt signals!")
except Exception:
    pkg_logger.debug(
        "Running outside QGIS, failed to import `QtSignalsHandler`, the logger will not emit `pyQt` signals!"
    )
