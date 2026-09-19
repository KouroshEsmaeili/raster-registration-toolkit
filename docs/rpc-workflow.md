# RPC/DEM satellite workflow

The satellite workflow converts a scene raster carrying separate rational
polynomial coefficient (RPC) metadata into a georeferenced GeoTIFF. It is
provider-neutral: users supply the scene directory, RPC XML and, when terrain
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
   `footprint.geojson`. A separately described panchromatic image is processed
   only when it has its own RPC XML.

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

## Migration decisions

The legacy archive was treated as read-only reference material. The migration
retains RPB parsing, DEM-backed RPC warping, panchromatic handling, scene
discovery, and progress reporting. It intentionally excludes provider-specific
tile downloads, machine-specific paths, regional coordinate clamps, fixed
translation biases, and unsupported accuracy claims. Experimental duplicate
feature-matching and phase-correlation scripts were not promoted over the
tested registration engine already in this package.

The legacy variants used conflicting rules for expanding a downsampled affine
matrix to full resolution. The existing package convention remains unchanged:
coordinates are scaled according to the source and reference pyramid levels,
as covered by deterministic unit tests.

## Validation scope

Unit tests validate parsing, selection, coordinate handling, error paths, and
other deterministic components. Actual positional accuracy depends on sensor
metadata, DEM quality, reference imagery, and GDAL configuration and must be
measured with independent ground control for each operational dataset.
