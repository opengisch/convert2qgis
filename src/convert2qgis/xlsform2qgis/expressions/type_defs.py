from dataclasses import dataclass
from enum import Enum


class TokenType(str, Enum):
    VARIABLE = "variable"
    IDENT = "ident"
    NUMBER = "number"
    STRING = "string"
    OPERATOR = "operator"
    PUNCTUATION = "punctuation"
    CURRENT = "current"
    EOF = "eof"


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: str
    raw_value: str
    start: int
    end: int
