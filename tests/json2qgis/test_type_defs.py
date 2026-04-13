from typing import cast

from convert2qgis.json2qgis.generate import (
    generate_field_def,
    generate_form_item_def,
    generate_relation_def,
    generate_vector_dataset_def,
)
from convert2qgis.json2qgis.json2qgis import ProjectCreator
from convert2qgis.json2qgis.type_defs import (
    DatasetGroupDef,
    FieldDef,
    ProjectDef,
    ProjectMetadataDef,
    RelationFieldPairDef,
    VectorDatasetDef,
)


def build_project_dict() -> dict:
    layer = cast(
        VectorDatasetDef,
        generate_vector_dataset_def(
            layer_type="vector",
            layer_id="layer_1",
            name="Survey",
            geometry_type="NoGeometry",
            fields=[
                generate_field_def(
                    field_id="field_1",
                    name="uuid",
                    type="string",
                    widget_type="TextEdit",
                )
            ],
            form_config=[
                generate_form_item_def(
                    item_id="form_1",
                    type="field",
                    field_name="uuid",
                )
            ],
            primary_key="uuid",
        ),
    )
    relation = generate_relation_def(
        relation_id="rel_1",
        name="survey_relation",
        from_layer_id="layer_1",
        to_layer_id="layer_1",
        field_pairs=[RelationFieldPairDef(from_field="uuid", to_field="uuid")],
    )

    return ProjectDef(
        project=ProjectMetadataDef(
            title="Survey",
            author="Tester",
            crs="EPSG:4326",
            extent="0 0, 1 1",
        ),
        version="1.0",
        datasets=[DatasetGroupDef(vector_datasets=[layer])],
        layer_tree=[],
        relations=[relation],
        polymorphic_relations=[],
    ).to_dict()


def test_field_def_round_trip() -> None:
    field_dict = {
        "field_id": "field_1",
        "name": "uuid",
        "type": "string",
        "length": 10,
        "precision": 0,
        "comment": "id field",
        "is_not_null": True,
        "is_not_null_strength": "hard",
        "constraint_expression": "",
        "constraint_expression_description": "",
        "constraint_expression_strength": "not_set",
        "is_unique": True,
        "is_unique_strength": "soft",
        "default_value": "uuid()",
        "set_default_value_on_update": False,
        "alias": "UUID",
        "alias_expression": "",
        "widget_type": "TextEdit",
        "widget_config": {},
    }

    field_def = FieldDef.from_data(field_dict)

    assert field_def.to_dict() == field_dict


def test_vector_layer_round_trip() -> None:
    layer_dict = generate_vector_dataset_def(
        layer_id="layer_1",
        name="Survey",
        geometry_type="NoGeometry",
        fields=[
            generate_field_def(
                field_id="field_1",
                name="uuid",
                type="string",
                widget_type="TextEdit",
            )
        ],
        form_config=[
            generate_form_item_def(
                item_id="form_1",
                type="field",
                field_name="uuid",
            )
        ],
        primary_key="uuid",
    ).to_dict()

    dataset_def = VectorDatasetDef.from_data(layer_dict)

    assert dataset_def.to_dict() == layer_dict


def test_project_round_trip() -> None:
    project_dict = build_project_dict()

    project_def = ProjectDef.from_data(project_dict)

    assert project_def.to_dict() == project_dict


def test_mutable_defaults_are_not_shared() -> None:
    left = generate_vector_dataset_def()
    right = generate_vector_dataset_def()

    assert isinstance(left, VectorDatasetDef)
    assert isinstance(right, VectorDatasetDef)

    left.fields.append(generate_field_def(name="left_only"))
    left.custom_properties["scope"] = "left"

    assert right.fields == []
    assert right.custom_properties == {}


def test_project_creator_accepts_dict_input() -> None:
    project_dict = build_project_dict()

    creator = ProjectCreator(project_dict)

    assert isinstance(creator.definition, ProjectDef)
    assert creator.definition.to_dict() == project_dict


def test_project_creator_accepts_dataclass_input() -> None:
    project_def = ProjectDef.from_data(build_project_dict())

    creator = ProjectCreator(project_def)

    assert creator.definition is project_def
