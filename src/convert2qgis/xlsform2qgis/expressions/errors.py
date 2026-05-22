from typing import Optional

from convert2qgis.xlsform2qgis.errors import Xlsform2QgisError
from convert2qgis.xlsform2qgis.expressions.type_defs import Token


class ParseError(Xlsform2QgisError):
    message: str
    position: Optional[int] = None
    token: Optional[Token] = None

    def __init__(
        self,
        message: str,
        position: Optional[int] = None,
        token: Optional[Token] = None,
    ) -> None:
        self.message = message
        self.position = position
        self.token = token

        super().__init__(self.__str__())

    def __str__(self) -> str:
        msg = self.message

        if self.token:
            msg += f" `{self.token.raw_value}`"

        if self.position is not None:
            msg += f" at position {self.position}"

        return msg


class TokenizationError(Xlsform2QgisError):
    pass
