import re
from hashlib import md5
from html.parser import HTMLParser
from io import StringIO


class HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, data: str) -> None:
        self.text.write(data)

    def get_data(self) -> str:
        return self.text.getvalue()


def strip_html(html: str) -> str:
    """Strips HTML tags from a string."""
    s = HTMLStripper()
    s.feed(html)
    return s.get_data()


def parse_xlsform_range_parameters(
    xlsform_parameters: str,
) -> tuple[float, float, float]:
    start_match = re.search(
        r"start=\s*([0-9]+)", xlsform_parameters, flags=re.IGNORECASE
    )
    end_match = re.search(r"end=\s*([0-9]+)", xlsform_parameters, flags=re.IGNORECASE)
    step_match = re.search(r"step=\s*([0-9]+)", xlsform_parameters, flags=re.IGNORECASE)

    if start_match is None:
        start = 0.0
    else:
        start = float(start_match.group(1))

    if end_match is None:
        end = 10.0
    else:
        end = float(end_match.group(1))

    if step_match is None:
        step = 1.0
    else:
        step = float(step_match.group(1))

    return start, end, step


def parse_xlsform_select_from_file_parameters(
    xlsform_parameters: str,
) -> tuple[str, str]:
    match = re.search(r"(?:value)\s*=\s*([^\s]*)", xlsform_parameters)
    if match:
        list_key = match.group(1)
    else:
        list_key = "name"

    match = re.search(r"(?:label)\s*=\s*([^\s]*)", xlsform_parameters)
    if match:
        list_value = match.group(1)
    else:
        list_value = "label"

    return list_key, list_value


def get_xlsform_type(raw_xls_type: str) -> str:
    xlsform_type, *_ = str(raw_xls_type).split(" ", 1)
    xlsform_type = xlsform_type.strip().lower()

    return xlsform_type


def build_choices_layer_name(part: str) -> str:
    return f"list_{part}"


def build_choices_layer_id(part: str) -> str:
    prefix = build_choices_layer_name(part)
    md5_hash = md5(prefix.encode(), usedforsecurity=False).hexdigest()

    return f"{prefix}_{md5_hash}"


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def get_unique_label(label: str, existing_labels: list[str]) -> str:
    label = label.strip()

    if not label:
        return label

    unique_label = label
    # starting from 2, assuming the one without suffix is the first occurrence, and the suffix is only needed for duplicates
    suffix = 2
    while unique_label in existing_labels:
        unique_label = f"{label} ({suffix})"
        suffix += 1

    return unique_label
