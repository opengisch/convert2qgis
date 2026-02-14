# json2qgis

A library that converts schema defined JSON structure into a QGIS project.


## Capabilities

The library supports:

- [x] Vector layers:
  - [x] Creation
    - [x] Supported providers
      - [x] Memory
      - [x] GeoPackage
    - [x] Data types
      - [x] string
      - [x] integer
      - [x] double
      - [x] boolean
      - [x] date
      - [x] time
      - [x] datetime
      - [ ] array
    - [x] Form types
      - [x] Tab
      - [x] Group box
      - [x] Row
      - [x] Hidden
      - [x] Color
      - [x] TextEdit
      - [x] Range
      - [x] DateTime
      - [x] ExternalResource
      - [x] CheckBox
      - [x] ValueMap
      - [x] ValueRelation
    - [ ] Loading from existing data source
    - [x] Relations
    - [x] Polymorphic relations
- [ ] Raster layers
- [x] Layer tree
- [ ] Symbology

## Usage

```shell
json2qgis ./samples/sample.json -o ./output/project/
```


## Development

```shell
uv run json2qgis ./samples/sample.json -o ./output/project/
```
