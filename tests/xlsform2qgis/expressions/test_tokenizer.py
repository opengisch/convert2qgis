import pytest

from convert2qgis.xlsform2qgis.expressions.errors import TokenizationError
from convert2qgis.xlsform2qgis.expressions.tokenizer import (
    tokenize_expression,
    tokenize_template,
)
from convert2qgis.xlsform2qgis.expressions.type_defs import (
    Token,
    TokenType,
)


def _tokens(expression: str) -> list[Token]:
    return list(tokenize_expression(expression))


def _template_tokens(expression: str) -> list[Token]:
    return list(tokenize_template(expression))


def _strip_eof(tokens: list[Token]) -> list[Token]:
    return [token for token in tokens if token.type != TokenType.EOF]


class TestTokenizerBasics:
    def test_empty_expression(self):
        tokens = _tokens("")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.EOF
        assert tokens[0].start == 0
        assert tokens[0].end == 0

    def test_whitespace_only(self):
        tokens = _tokens(" \t\n ")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.EOF

    def test_single_identifier(self):
        tokens = _tokens("field")
        token = _strip_eof(tokens)[0]
        assert token.type == TokenType.IDENT
        assert token.value == "field"
        assert token.raw_value == "field"
        assert token.start == 0
        assert token.end == 5

    def test_identifier_with_hyphen_and_colon(self):
        tokens = _tokens("jr:choice-name")
        assert _strip_eof(tokens)[0].type == TokenType.IDENT
        assert _strip_eof(tokens)[0].value == "jr:choice-name"
        assert _strip_eof(tokens)[0].raw_value == "jr:choice-name"

    def test_variable_reference(self):
        tokens = _tokens("${field_name}")
        token = _strip_eof(tokens)[0]
        assert token.type == TokenType.VARIABLE
        assert token.value == "field_name"
        assert token.raw_value == "${field_name}"
        assert token.start == 0
        assert token.end == len("${field_name}")


class TestTokenizerStrings:
    @pytest.mark.parametrize(
        ("expression", "raw_value", "value"),
        [
            # Opening: [U+0027] Apostrophe; Closing: [U+0027] Apostrophe: ''
            ("'hello'", "'hello'", "hello"),
            # Opening: [U+0022] Quotation Mark; Closing: [U+0022] Quotation Mark: ""
            ('"hello"', '"hello"', "hello"),
            # Opening: [U+2018] Left Single Quotation Mark; Closing: [U+2019] Right Single Quotation Mark: \u2018\u2019
            ("\u2018hello\u2019", "\u2018hello\u2019", "hello"),
            # Opening: [U+201A] Single Low-9 Quotation Mark; Closing: [U+2019] Right Single Quotation Mark: \u201A\u2019
            ("\u201ahello\u2019", "\u201ahello\u2019", "hello"),
            # Opening: [U+201A] Single Low-9 Quotation Mark; Closing: [U+201B] Single High-Reversed-9 Quotation Mark: \u201A\u201B
            ("\u201ahello\u201b", "\u201ahello\u201b", "hello"),
            # Opening: [U+201C] Left Double Quotation Mark; Closing: [U+201D] Right Double Quotation Mark: “”
            ("\u201chello\u201d", "\u201chello\u201d", "hello"),
            # Opening: [U+201E] Double Low-9 Quotation Mark; Closing: [U+201D] Right Double Quotation Mark: „”
            ("\u201ehello\u201d", "\u201ehello\u201d", "hello"),
            # Opening: [U+201E] Double Low-9 Quotation Mark; Closing: [U+201F] Double High-Reversed-9 Quotation Mark: „‟
            ("\u201ehello\u201f", "\u201ehello\u201f", "hello"),
        ],
    )
    def test_quoted_string(self, expression, raw_value, value):
        tokens = _tokens(expression)
        token = _strip_eof(tokens)[0]

        assert token.type == TokenType.STRING
        assert token.value == value
        assert token.raw_value == raw_value

    def test_poorly_quoted_string(self):
        with pytest.raises(TokenizationError, match='Unexpected character: "'):
            _tokens('"unmatched”')

    def test_unterminated_string(self):
        with pytest.raises(TokenizationError, match="Unexpected character: '"):
            _tokens("'unterminated")

    def test_string_with_escaped_quote(self):
        tokens = _tokens("'it\\'s'")
        token = _strip_eof(tokens)[0]
        assert token.type == TokenType.STRING
        assert token.value == "it\\'s"
        assert token.raw_value == "'it\\'s'"

    def test_string_with_escaped_backslash(self):
        tokens = _tokens("'c:\\\\temp'")
        token = _strip_eof(tokens)[0]
        assert token.type == TokenType.STRING
        assert token.value == "c:\\\\temp"
        assert token.raw_value == "'c:\\\\temp'"


class TestTokenizerNumbers:
    def test_integer_number(self):
        tokens = _tokens("42")
        token = _strip_eof(tokens)[0]
        assert token.type == TokenType.NUMBER
        assert token.value == "42"
        assert token.raw_value == "42"

    def test_decimal_number(self):
        tokens = _tokens("3.14")
        token = _strip_eof(tokens)[0]
        assert token.type == TokenType.NUMBER
        assert token.value == "3.14"
        assert token.raw_value == "3.14"

    def test_leading_dot_number(self):
        tokens = _tokens(".5")
        token = _strip_eof(tokens)[0]
        assert token.type == TokenType.NUMBER
        assert token.value == ".5"
        assert token.raw_value == ".5"


class TestTokenizerCurrent:
    def test_current_dot(self):
        tokens = _tokens(".")
        token = _strip_eof(tokens)[0]
        assert token.type == TokenType.CURRENT
        assert token.value == "."
        assert token.raw_value == "."

    def test_current_in_expression(self):
        tokens = _strip_eof(_tokens(". = 1"))
        assert [t.type for t in tokens] == [
            TokenType.CURRENT,
            TokenType.OPERATOR,
            TokenType.NUMBER,
        ]

    def test_current_in_expression_comparison(self):
        tokens = _strip_eof(_tokens(". > -1"))
        assert [t.type for t in tokens] == [
            TokenType.CURRENT,
            TokenType.OPERATOR,
            TokenType.OPERATOR,
            TokenType.NUMBER,
        ]
        assert tokens[0].value == "."
        assert tokens[1].value == ">"
        assert tokens[2].value == "-"
        assert tokens[3].value == "1"


class TestTokenizerOperators:
    def test_symbol_operators(self):
        tokens = _strip_eof(_tokens("= != > >= < <= + - *"))
        values = [token.value for token in tokens]
        assert values == ["=", "!=", ">", ">=", "<", "<=", "+", "-", "*"]
        assert all(token.type == TokenType.OPERATOR for token in tokens)

    def test_word_operators(self):
        tokens = _strip_eof(_tokens("and or div mod"))
        values = [token.value for token in tokens]
        assert values == ["and", "or", "div", "mod"]
        assert all(token.type == TokenType.OPERATOR for token in tokens)

    def test_mixed_operator_expression(self):
        tokens = _strip_eof(_tokens("${a} >= 10 and ${b} < 20"))
        types = [token.type for token in tokens]
        assert types == [
            TokenType.VARIABLE,
            TokenType.OPERATOR,
            TokenType.NUMBER,
            TokenType.OPERATOR,
            TokenType.VARIABLE,
            TokenType.OPERATOR,
            TokenType.NUMBER,
        ]

    def test_unsupported_operator(self):
        with pytest.raises(TokenizationError, match="Unexpected character: /"):
            _tokens("4 / 2 = 2")


class TestTokenizerPunctuation:
    def test_punctuation_tokens(self):
        tokens = _strip_eof(_tokens("( ),"))
        values = [token.value for token in tokens]
        assert values == ["(", ")", ","]
        assert all(token.type == TokenType.PUNCTUATION for token in tokens)


class TestTokenizerPositions:
    def test_positions_and_raw_values(self):
        tokens = _strip_eof(_tokens("${x} + 10"))
        first = tokens[0]
        second = tokens[1]
        third = tokens[2]
        assert (first.start, first.end) == (0, 4)
        assert first.raw_value == "${x}"
        assert (second.start, second.end) == (5, 6)
        assert second.raw_value == "+"
        assert (third.start, third.end) == (7, 9)
        assert third.raw_value == "10"


class TestTokenizerErrors:
    def test_unterminated_variable(self):
        with pytest.raises(TokenizationError, match="Unexpected character: \\$"):
            _tokens("${missing")

    def test_unterminated_string(self):
        with pytest.raises(TokenizationError, match="Unexpected character: '"):
            _tokens("'missing")

    def test_unsupported_operator(self):
        with pytest.raises(TokenizationError, match="Unexpected character: !"):
            _tokens("!")

    def test_unexpected_character(self):
        with pytest.raises(TokenizationError, match="Unexpected character: @"):
            _tokens("@")


class TestTemplateTokenizer:
    def test_template_with_text_only(self):
        tokens = _strip_eof(_template_tokens("Hello Santa, welcome!"))

        assert len(tokens) == 1
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "Hello Santa, welcome!"

    def test_template_with_variable_and_text(self):
        tokens = _strip_eof(_template_tokens("Hello ${name}, welcome!"))

        assert len(tokens) == 3
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "Hello "
        assert tokens[1].type == TokenType.VARIABLE
        assert tokens[1].value == "name"
        assert tokens[2].type == TokenType.STRING
        assert tokens[2].value == ", welcome!"
