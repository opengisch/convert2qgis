from convert2qgis.errors import Convert2QgisBaseError


class Xlsform2QgisError(Convert2QgisBaseError):
    """Base class for all exceptions raised by `xlsform2qgis`."""


class XlsformSheetParserError(Xlsform2QgisError):
    """Raised when parsing XLSForm sheets."""
