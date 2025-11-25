from typing import TypedDict, Literal


ConstraintStrength = Literal["hard", "soft", "not_set"]


class FieldDef(TypedDict):
    id: str
    name: str
    type: str
    length: int
    precision: int
    comment: str

    is_not_null: bool
    is_not_null_strength: ConstraintStrength

    constraint_expression: str
    constraint_expression_description: str
    constraint_expression_strength: ConstraintStrength

    is_unique: bool
    is_unique_strength: ConstraintStrength

    default_value: str | None
    set_default_value_on_update: bool
    alias: str
    widget_type: str
    widget_config: dict[str, object]
