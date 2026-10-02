from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from qgis.core import (
    Qgis,
    QgsProject,
    QgsProviderRegistry,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

from convert2qgis.json2qgis.errors import (
    Qgis2JsonError,
    UnknownVectorLayerDataproviderError,
)
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
    LegendTreeGroupDef,
    OapifDatasourceDef,
    OgrDatasourceDef,
    PostgresDatasourceDef,
    ProjectDef,
    ProjectMetadataDef,
    RelationFieldPairDef,
    VectorDatasetDef,
    WfsDatasourceDef,
    vector_datasource_from_data,
)
from convert2qgis.json2qgis.utils import create_fields


def build_project_dict() -> dict[str, Any]:
    layer = generate_vector_dataset_def(
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
        virtual_fields=[
            generate_field_def(
                field_id="field_2",
                name="total",
                type="integer",
                widget_type="Hidden",
                default_value='"count_a" + "count_b"',
                set_default_value_on_update=True,
            )
        ],
        form_config=[
            generate_form_item_def(
                item_id="tab_1",
                type="tab",
                label="Survey",
                children=[
                    generate_form_item_def(
                        item_id="form_1",
                        type="field",
                        field_name="uuid",
                    )
                ],
            )
        ],
        primary_key="uuid",
    )
    relation = generate_relation_def(
        relation_id="rel_1",
        name="survey_relation",
        from_layer_id="layer_1",
        to_layer_id="layer_1",
        field_pairs=[RelationFieldPairDef(from_field="uuid", to_field="uuid")],
    )

    return ProjectDef(  # type: ignore[no-any-return]
        project=ProjectMetadataDef(
            title="Survey",
            author="Tester",
            crs="EPSG:4326",
            extent="0 0, 1 1",
        ),
        version="1.0",
        datasets=[DatasetGroupDef(vector_datasets=[layer])],
        legend_tree=LegendTreeGroupDef(
            item_id="legend_root",
            name="",
            children=[],
        ),
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
                item_id="tab_1",
                type="tab",
                label="Survey",
                children=[
                    generate_form_item_def(
                        item_id="form_1",
                        type="field",
                        field_name="uuid",
                    )
                ],
            )
        ],
        primary_key="uuid",
    ).to_dict()

    dataset_def = VectorDatasetDef.from_data(layer_dict)

    assert dataset_def.to_dict() == layer_dict


def test_vector_layer_round_trip_with_row_form_container() -> None:
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
                item_id="tab_1",
                type="tab",
                label="Survey",
                children=[
                    generate_form_item_def(
                        item_id="row_1",
                        type="row",
                        label="Row",
                        children=[
                            generate_form_item_def(
                                item_id="form_1",
                                type="field",
                                field_name="uuid",
                            )
                        ],
                    )
                ],
            )
        ],
        primary_key="uuid",
    ).to_dict()

    dataset_def = VectorDatasetDef.from_data(layer_dict)
    ProjectCreator(
        {
            **build_project_dict(),
            "datasets": [
                {
                    "vector_datasets": [
                        layer_dict,
                    ],
                    "raster_datasets": [],
                }
            ],
        }
    )

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


def test_project_creator_accepts_empty_crs_for_no_geometry_layer(tmp_path) -> None:
    project_dict = build_project_dict()
    project_dict["datasets"][0]["vector_datasets"][0]["crs"] = ""

    creator = ProjectCreator(project_dict)
    project = creator.build(tmp_path)
    layer = project.mapLayer("layer_1")

    assert layer is not None
    assert not layer.crs().isValid()
    assert layer.crs().authid() == ""


def test_project_creator_resolves_relative_output_dir(tmp_path, monkeypatch) -> None:
    project_dict = build_project_dict()

    monkeypatch.chdir(tmp_path)

    creator = ProjectCreator(project_dict)
    project = creator.build(Path("output"))
    layer = project.mapLayer("layer_1")

    assert layer is not None

    uri = QgsProviderRegistry.instance().decodeUri("ogr", layer.source())

    assert Path(uri["path"]).is_absolute()


def test_project_creator_rejects_empty_crs_for_spatial_layer() -> None:
    pytest.importorskip("fastjsonschema")

    project_dict = build_project_dict()
    project_dict["datasets"][0]["vector_datasets"][0]["geometry_type"] = "Point"
    project_dict["datasets"][0]["vector_datasets"][0]["crs"] = ""

    with pytest.raises(Qgis2JsonError):
        ProjectCreator(project_dict)


def test_project_creator_rejects_malformed_project_crs() -> None:
    pytest.importorskip("fastjsonschema")

    project_dict = build_project_dict()
    project_dict["project"]["crs"] = "invalid EPSG:4326 value"

    with pytest.raises(Qgis2JsonError):
        ProjectCreator(project_dict)


def test_project_creator_accepts_valid_project_crs() -> None:
    pytest.importorskip("fastjsonschema")

    project_dict = build_project_dict()
    project_dict["project"]["crs"] = "EPSG:7801"

    creator = ProjectCreator(project_dict)

    assert creator.definition.project.crs == "EPSG:7801"


def test_project_creator_accepts_time_field_type() -> None:
    pytest.importorskip("fastjsonschema")

    project_dict = build_project_dict()
    project_dict["datasets"][0]["vector_datasets"][0]["fields"].append(
        generate_field_def(
            field_id="field_time",
            name="appointment_time",
            type="time",
            widget_type="DateTime",
        ).to_dict()
    )

    creator = ProjectCreator(project_dict)

    dataset_def = creator.definition.datasets[0].vector_datasets[0]
    assert dataset_def.fields[-1].name == "appointment_time"
    assert dataset_def.fields[-1].type == "time"


def test_project_creator_raises_for_unexpected_vector_writer_output(
    tmp_path, monkeypatch
) -> None:
    project_def = ProjectDef.from_data(build_project_dict())
    [dataset_group] = project_def.datasets
    [dataset_def] = dataset_group.vector_datasets
    creator = ProjectCreator(project_def)
    creator._output_dir = tmp_path

    def write_vector_layer(*_args: object) -> tuple[object, str, str, str]:
        return (
            QgsVectorFileWriter.WriterError.NoError,
            "",
            str(tmp_path / "unexpected.gpkg"),
            "unexpected_layer",
        )

    monkeypatch.setattr(
        QgsVectorFileWriter,
        "writeAsVectorFormatV3",
        write_vector_layer,
    )

    with pytest.raises(
        Qgis2JsonError,
        match='Unexpected vector writer output for layer "Survey"',
    ):
        creator._create_vector_layer(dataset_def)


def test_project_creator_validates_raw_dict_before_defaults() -> None:
    pytest.importorskip("fastjsonschema")

    project_dict = build_project_dict()

    # Make the project definition invalid by removing a required property
    del project_dict["project"]["title"]

    with pytest.raises(Qgis2JsonError):
        ProjectCreator(project_dict)


def test_project_creator_validates_raw_dict_before_dropping_unknown_properties() -> (
    None
):
    pytest.importorskip("fastjsonschema")

    project_dict = build_project_dict()
    # Make the project definition invalid by adding unknown property
    project_dict["datasets"][0]["vector_datasets"][0]["unknown_property"] = (
        "should fail"
    )

    with pytest.raises(Qgis2JsonError):
        ProjectCreator(project_dict)


def test_project_creator_sets_polymorphic_relations() -> None:
    project_dict = build_project_dict()
    project_dict["relations"] = []
    project_dict["polymorphic_relations"] = [
        {
            "relation_id": "poly_rel_1",
            "name": "document_owner",
            "from_layer_id": "documents",
            "to_layer_field": "layer_id",
            "to_layer_expression": "@layer_id",
            "to_layer_ids": ["birds", "mammals"],
            "strength": "composition",
            "field_pairs": [
                {
                    "from_field": "uuid",
                    "to_field": "document_uuid",
                },
            ],
        },
    ]
    creator = ProjectCreator(project_dict)
    project = QgsProject.instance()
    project.clear()
    documents_layer = QgsVectorLayer(
        "Point?field=layer_id:string&field=uuid:string&crs=EPSG:4326",
        "documents",
        "memory",
    )
    documents_layer.setId("documents")
    birds_layer = QgsVectorLayer(
        "Point?field=document_uuid:string&crs=EPSG:4326",
        "birds",
        "memory",
    )
    birds_layer.setId("birds")
    mammals_layer = QgsVectorLayer(
        "Point?field=document_uuid:string&crs=EPSG:4326",
        "mammals",
        "memory",
    )
    mammals_layer.setId("mammals")
    project.addMapLayers([documents_layer, birds_layer, mammals_layer])
    creator._project = project

    creator._set_relations()

    relation_manager = project.relationManager()

    assert relation_manager is not None
    assert relation_manager.polymorphicRelation("poly_rel_1").isValid()
    project.clear()


def test_project_creator_raises_when_vector_data_insert_fails() -> None:
    creator = ProjectCreator(build_project_dict())
    dataset_def = generate_vector_dataset_def(
        name="Survey",
        fields=[
            generate_field_def(
                name="name",
                type="string",
                widget_type="TextEdit",
            )
        ],
        data=[
            {
                "name": "Test",
            }
        ],
    )
    provider = MagicMock()
    provider.isValid.return_value = True
    provider.addFeatures.return_value = (False, [])
    layer = MagicMock()
    layer.dataProvider.return_value = provider
    layer.geometryType.return_value = Qgis.GeometryType.Null
    layer.fields.return_value = create_fields(dataset_def)

    with pytest.raises(
        Qgis2JsonError,
        match='Failed to add feature data to layer "Survey"',
    ):
        creator._add_vector_layer_data(layer, dataset_def)

    provider.addFeatures.assert_called_once()
    layer.commitChanges.assert_not_called()


def test_project_creator_raises_when_vector_data_commit_fails() -> None:
    creator = ProjectCreator(build_project_dict())
    dataset_def = generate_vector_dataset_def(
        name="Survey",
        fields=[
            generate_field_def(
                name="name",
                type="string",
                widget_type="TextEdit",
            )
        ],
        data=[
            {
                "name": "Test",
            }
        ],
    )
    provider = MagicMock()
    provider.isValid.return_value = True
    provider.addFeatures.return_value = (True, [])
    layer = MagicMock()
    layer.dataProvider.return_value = provider
    layer.geometryType.return_value = Qgis.GeometryType.Null
    layer.fields.return_value = create_fields(dataset_def)
    layer.commitChanges.return_value = False

    with pytest.raises(
        Qgis2JsonError,
        match='Failed to commit feature data to layer "Survey"',
    ):
        creator._add_vector_layer_data(layer, dataset_def)

    provider.addFeatures.assert_called_once()
    layer.updateExtents.assert_called_once()
    layer.commitChanges.assert_called_once()


def write_gpkg_layer(gpkg_path: Path, layer_name: str) -> None:
    layer = QgsVectorLayer(
        "Point?crs=EPSG:4326&field=uuid:string",
        layer_name,
        "memory",
    )
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = layer_name

    write_result, error_message, _new_file, _new_layer = (
        QgsVectorFileWriter.writeAsVectorFormatV3(
            layer,
            str(gpkg_path),
            QgsProject.instance().transformContext(),
            options,
        )
    )

    assert write_result == QgsVectorFileWriter.WriterError.NoError, error_message


def build_datasource_project_dict(
    datasource: dict[str, Any], datasource_format: str = "ogr"
) -> dict[str, Any]:
    project_dict = build_project_dict()
    dataset_dict = project_dict["datasets"][0]["vector_datasets"][0]
    dataset_dict["datasource"] = datasource
    dataset_dict["datasource_format"] = datasource_format
    dataset_dict["fields"][0]["alias"] = "Identifier"
    dataset_dict["fields"][0]["widget_type"] = "ValueMap"
    dataset_dict["fields"][0]["widget_config"] = {"map": {"First": "first"}}

    return project_dict


@pytest.mark.parametrize("datasource_format", ["gpkg", "ogr"])
def test_project_creator_loads_vector_layer_from_datasource(
    tmp_path, datasource_format: str
) -> None:
    gpkg_path = tmp_path / "source" / "existing.gpkg"
    gpkg_path.parent.mkdir()
    write_gpkg_layer(gpkg_path, "existing")
    output_dir = tmp_path / "output"

    creator = ProjectCreator(
        build_datasource_project_dict(
            {"path": str(gpkg_path), "layer_name": "existing"},
            datasource_format,
        )
    )
    project = creator.build(output_dir)
    layer = project.mapLayer("layer_1")

    assert isinstance(layer, QgsVectorLayer)
    assert layer.providerType() == "ogr"

    uri = QgsProviderRegistry.instance().decodeUri("ogr", layer.source())

    assert Path(uri["path"]) == gpkg_path
    assert uri["layerName"] == "existing"
    # the geometry type is decided by the datasource, not by the definition
    assert layer.geometryType() == Qgis.GeometryType.Point

    field_idx = layer.fields().indexOf("uuid")

    assert layer.fields().field(field_idx).alias() == "Identifier"
    assert layer.editorWidgetSetup(field_idx).type() == "ValueMap"
    assert layer.fields().indexOf("total") != -1
    assert list(output_dir.glob("*.gpkg")) == []


@pytest.mark.parametrize(
    ("datasource_format", "datasource", "datasource_def_class"),
    [
        ("gpkg", {"path": "/data/roads.gpkg"}, OgrDatasourceDef),
        (
            "ogr",
            {"path": "/data/roads.gpkg", "layer_name": "roads"},
            OgrDatasourceDef,
        ),
        (
            "postgres",
            {
                "table": "roads",
                "schema": "public",
                "geometry_column": "geom",
                "key_column": "id",
                "service": "my_db",
                "port": 5432,
                "sslmode": "require",
            },
            PostgresDatasourceDef,
        ),
        (
            "wfs",
            {
                "url": "https://example.com/wfs",
                "type_name": "ns:roads",
                "version": "2.0.0",
            },
            WfsDatasourceDef,
        ),
        (
            "oapif",
            {
                "url": "https://example.com/ogcapi",
                "collection": "roads",
                "authcfg": "abc1234",
            },
            OapifDatasourceDef,
        ),
    ],
)
def test_vector_dataset_def_datasource_round_trip(
    datasource_format: str,
    datasource: dict[str, Any],
    datasource_def_class: type,
) -> None:
    project_dict = build_datasource_project_dict(datasource, datasource_format)
    dataset_dict = project_dict["datasets"][0]["vector_datasets"][0]

    dataset_def = VectorDatasetDef.from_data(dataset_dict)

    assert isinstance(dataset_def.datasource, datasource_def_class)
    assert dataset_def.to_dict()["datasource"] == datasource
    # validated against the schema when `fastjsonschema` is available
    ProjectCreator(project_dict)


def test_vector_datasource_from_data_raises_for_memory() -> None:
    with pytest.raises(NotImplementedError, match="memory"):
        vector_datasource_from_data("memory", {"path": "/data/roads.gpkg"})


@pytest.mark.parametrize("datasource_format", ["ogr", "postgres", "oapif", "wfs"])
def test_project_creator_rejects_provider_format_without_datasource(
    datasource_format: str,
) -> None:
    pytest.importorskip("fastjsonschema")

    project_dict = build_project_dict()
    dataset_dict = project_dict["datasets"][0]["vector_datasets"][0]
    dataset_dict["datasource_format"] = datasource_format

    dataset_dict.pop("datasource", None)
    with pytest.raises(Qgis2JsonError):
        ProjectCreator(project_dict)

    dataset_dict["datasource"] = {}
    with pytest.raises(Qgis2JsonError):
        ProjectCreator(project_dict)


@pytest.mark.parametrize(
    ("datasource_format", "datasource"),
    [
        ("gpkg", {"path": ""}),
        ("ogr", "/data/roads.gpkg|layername=roads"),
        ("ogr", {"table": "roads"}),
        ("postgres", {"path": "/data/roads.gpkg"}),
        ("postgres", {"table": "roads", "port": "5432"}),
        ("postgres", {"table": "roads", "sslmode": "always"}),
        ("wfs", {"url": "https://example.com/wfs"}),
        ("wfs", {"url": "https://example.com/wfs", "typename": "ns:roads"}),
        ("oapif", {"url": "https://example.com/ogcapi", "type_name": "roads"}),
        ("memory", {"path": "/data/roads.gpkg"}),
    ],
)
def test_project_creator_rejects_invalid_datasource(
    datasource_format: str, datasource: Any
) -> None:
    pytest.importorskip("fastjsonschema")

    with pytest.raises(Qgis2JsonError):
        ProjectCreator(build_datasource_project_dict(datasource, datasource_format))


@pytest.mark.parametrize("datasource_format", ["memory", "postgres"])
def test_project_creator_raises_for_datasource_not_matching_format(
    tmp_path, datasource_format: str
) -> None:
    creator = ProjectCreator(
        build_datasource_project_dict({"path": str(tmp_path / "existing.gpkg")})
    )
    [dataset_def] = creator.definition.datasets[0].vector_datasets
    # bypass the schema validation, which already rejects such definitions
    dataset_def.datasource_format = datasource_format

    with pytest.raises(UnknownVectorLayerDataproviderError, match='"OgrDatasourceDef"'):
        creator.build(tmp_path)


def test_project_creator_raises_for_invalid_datasource(tmp_path) -> None:
    creator = ProjectCreator(
        build_datasource_project_dict(
            {"path": str(tmp_path / "missing.gpkg"), "layer_name": "missing"}
        )
    )

    with pytest.raises(Qgis2JsonError, match="Vector layer invalid: Survey"):
        creator.build(tmp_path)


def test_project_creator_raises_for_data_with_datasource(tmp_path) -> None:
    gpkg_path = tmp_path / "existing.gpkg"
    write_gpkg_layer(gpkg_path, "existing")
    project_dict = build_datasource_project_dict(
        {"path": str(gpkg_path), "layer_name": "existing"}
    )
    project_dict["datasets"][0]["vector_datasets"][0]["data"] = [{"uuid": "first"}]

    creator = ProjectCreator(project_dict)

    with pytest.raises(
        NotImplementedError, match='"Survey" with an existing datasource'
    ):
        creator.build(tmp_path)
