from __future__ import annotations

import re
import unicodedata

from convert2qgis.xlsform2qgis.expressions.errors import TokenizationError
from convert2qgis.xlsform2qgis.expressions.type_defs import Token, TokenType

OPERATORS: set[str] = {
    # math operators, see https://docs.getodk.org/form-operators-functions/#math-operators
    "+",
    "-",
    "*",
    "div",
    "mod",
    # comparison operators, see https://docs.getodk.org/form-operators-functions/#comparison-operators
    "=",
    "!=",
    ">",
    ">=",
    "<",
    "<=",
    # boolean operators, see https://docs.getodk.org/form-operators-functions/#boolean-operators
    "and",
    "or",
}

PUNCTUATION: set[str] = {
    "(",
    ")",
    ",",
}

Lexicon = tuple[tuple[TokenType, re.Pattern[str]], ...]

EXPRESSION_LEXICON: Lexicon = (
    (
        TokenType.STRING,
        re.compile(
            # Opening: [U+0027] Apostrophe: '
            # Closing: [U+0027] Apostrophe: '
            r"'(?:\\.|[^'\\])*'"
            # Opening: [U+0022] Quotation Mark: "
            # Closing: [U+0022] Quotation Mark: "
            r'|"(?:\\.|[^"\\])*"'
            # allow the more exotic quotes; unicode notation is used, as ruff complains with RUF001 in comments
            # Opening: [U+2018] Left Single Quotation Mark: \u2018
            # Closing: [U+2019] Right Single Quotation Mark: \u2019
            r"|‘(?:\\.|[^’\\])*’"  # noqa: RUF001
            # Opening: [U+201A] Single Low-9 Quotation Mark; \u201A
            # Closing: [U+201B] Single High-Reversed-9 Quotation Mark: \u201B
            # OR
            # Closing: [U+2019] Right Single Quotation Mark: \u2019
            r"|‚(?:\\.|[^’‛\\])*(?:’|‛)"  # noqa: RUF001
            # Opening: [U+201C] Left Double Quotation Mark: “
            # Closing: [U+201D] Right Double Quotation Mark: ”
            r"|“(?:\\.|[^”\\])*”"
            # Opening: [U+201E] Double Low-9 Quotation Mark: „
            # Closing: [U+201F] Double High-Reversed-9 Quotation Mark: ‟
            # OR
            # Closing: [U+201D] Right Double Quotation Mark: ”
            r"|„(?:\\.|[^”‟\\])*(?:”|‟)"
        ),
    ),
    (TokenType.VARIABLE, re.compile(r"\$\{[^}]*\}")),
    (TokenType.NUMBER, re.compile(r"\d+(?:\.\d+)?|\.\d+")),
    (TokenType.CURRENT, re.compile(r"\.")),
    (TokenType.OPERATOR, re.compile(r"!=|>=|<=|=|>|<|\+|-|\*")),
    (TokenType.OPERATOR, re.compile(r"\b(?:and|or|div|mod)\b")),
    (TokenType.PUNCTUATION, re.compile(r"[\(\),]")),
    (TokenType.IDENT, re.compile(r"[A-Za-z_][A-Za-z0-9_\-:]*")),
)

TEMPLATE_LEXICON: Lexicon = (
    (TokenType.VARIABLE, re.compile(r"\$\{[^}]*\}")),
    (TokenType.STRING, re.compile(r"[\s\S]*?(?=(\$\{)|$)")),
)


_WHITESPACE = re.compile(r"\s+")


def _normalize_value(token_type: TokenType, raw_value: str, is_template: bool) -> str:
    if token_type == TokenType.VARIABLE:
        return raw_value[2:-1]

    if token_type == TokenType.STRING:
        # for template strings, we want to preserve the quotes if they are part of the string
        if is_template:
            return raw_value

        return raw_value[1:-1]

    if token_type == TokenType.CURRENT:
        return "."

    return raw_value


def tokenize(expression: str, lexicon: Lexicon, is_template: bool) -> list[Token]:
    tokens: list[Token] = []
    pos: int = 0
    length: int = len(expression)

    while pos < length:
        # if we are tokenizing an expression, skip whitespace
        if not is_template:
            whitespace_match = _WHITESPACE.match(expression, pos)
            if whitespace_match:
                pos = whitespace_match.end()
                continue

        best_type: TokenType | None = None
        best_match: re.Match[str] | None = None

        for token_type, pattern in lexicon:
            match = pattern.match(expression, pos)
            if not match:
                continue

            if best_match is None or match.end() > best_match.end():
                best_match = match
                best_type = token_type

        if best_match is None or best_type is None:
            char_name = unicodedata.name(expression[pos], "UNKNOWN CHARACTER")
            raise TokenizationError(
                f"Unexpected character: {expression[pos]} ({char_name}) at position {pos}"
            )

        start = pos
        end = best_match.end()
        raw_value = expression[start:end]

        assert not (best_type == TokenType.OPERATOR and raw_value not in OPERATORS)

        value = _normalize_value(best_type, raw_value, is_template)
        tokens.append(Token(best_type, value, raw_value, start, end))
        pos = end

    tokens.append(Token(TokenType.EOF, "", "", length, length))

    return tokens


def tokenize_expression(expression: str) -> list[Token]:
    return tokenize(expression, EXPRESSION_LEXICON, is_template=False)


def tokenize_template(expression: str) -> list[Token]:
    return tokenize(expression, TEMPLATE_LEXICON, is_template=True)
