# RPC/DEM satellite workflow

The satellite workflow converts a scene raster with rational polynomial
coefficient (RPC) metadata into a georeferenced GeoTIFF.

The processing layer uses a provider-neutral internal RPC model. The current
metadata adapter parses RPB/IMAGE XML documents; additional vendor formats can
be added by translating their metadata into the same internal RPC model.
Users supply the scene imagery, compatible RPC metadata, and, when terrain
correction is enabled, an elevation raster.

## Processing stages

1. Discover TIFF imagery and matching XML metadata. Explicit paths take
   precedence; ambiguous automatic matches are rejected.
2. Parse the `RPB/IMAGE` RPC fields into a validated, typed model.
3. Validate the elevation raster and ensure it covers the nominal scene center.
4. Run GDAL's RPC transformer, optionally with `RPC_DEM` terrain correction.
5. Optionally register the orthorectified result against a user-supplied
   georeferenced reference raster using the existing SIFT/RANSAC pipeline.
6. Write `registered.tif`, `metadata.json`, and a WGS84
   `footprint.geojson` representing the output raster bounds.
7. Process a separately described panchromatic image only when it has its own
   RPC XML.

Install GDAL Python bindings compatible with the GDAL library on the host, then
install the satellite extra where appropriate:

```bash
python -m pip install -e ".[satellite]"
```

Example:

```bash
rasterreg scene \
  --scene-dir /data/scene \
  --dem /data/elevation.tif \
  --output-dir /data/output \
  --resolution 10
```

Feature refinement is opt-in and requires `--reference` together with
`--refine`. The registration method is affine and therefore does not model
arbitrary terrain or sensor distortions.

## Design decisions

Scene discovery, RPC metadata parsing, DEM-backed RPC warping, optional
panchromatic processing, feature refinement, and machine-readable reporting are
kept as separate components. The implementation avoids provider-specific tile
services, machine-specific paths, fixed translation biases, regional coordinate
assumptions, and hard-coded accuracy claims.

Feature refinement uses the same explicit pyramid-coordinate convention as the
primary registration workflow, with deterministic unit tests covering the scale
conversion.

## Validation scope

Unit tests cover RPC parsing, scene selection, DEM validation, coordinate
handling, output-resolution calculations, error paths, and other deterministic
components. CI does not perform an end-to-end RPC orthorectification against
real satellite imagery and a real DEM.

Actual positional accuracy depends on sensor metadata, DEM quality, reference
imagery, GDAL configuration, and scene characteristics. Quantitative accuracy
must therefore be evaluated against independent ground control on representative
datasets.
