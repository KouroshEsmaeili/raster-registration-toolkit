# Raster Registration Toolkit

Raster Registration Toolkit provides feature-based registration of overlapping
rasters and terrain-aware orthorectification of satellite scenes with RPC
metadata and a user-supplied DEM. Both workflows produce portable GeoTIFF
outputs without provider-specific services.

The project began as a desktop workflow for registering high-resolution,
multiband aerial imagery—including a fourth infrared band—against lower
resolution basemap imagery. This repository consolidates that historical code
into one typed Python package, a command-line interface, and an optional
dual-workflow GUI.

## Method

```text
source image + user-supplied reference raster
                       │
                       ▼
             multi-scale preprocessing
                       │
                       ▼
              SIFT feature extraction
                       │
                       ▼
       2-nearest-neighbor descriptor matching
                       │
                       ▼
       ratio + distance-percentile filtering
                       │
                       ▼
            RANSAC affine estimation
                       │
                       ▼
          full-resolution multiband warp
                       │
                       ▼
       reference bounds and CRS → GeoTIFF
```

The default thresholds preserve the latest historical implementation: a 0.8
descriptor ratio, 20th–80th percentile distance trimming, source/reference
pyramid height limits of 5,000/10,000 pixels, and a 180-degree source rotation.
They are configurable through `RegistrationConfig` in the Python API.

## Architecture

- `alignment.py` contains SIFT extraction, descriptor filtering, RANSAC affine
  estimation, pyramid handling, scale conversion, and multiband warping.
- `image_io.py` loads rasters, builds normalized feature views without changing
  original band values, and writes compressed GeoTIFFs.
- `geospatial.py` validates reference metadata and derives output transforms.
- `pipeline.py` coordinates IO, registration, warping, and export.
- `rpc.py`, `dem.py`, and `orthorectification.py` provide the typed satellite
  metadata and GDAL-backed terrain-correction layer.
- `scene.py`, `satellite.py`, and `reporting.py` discover inputs, coordinate the
  satellite workflow, and write JSON/GeoJSON reports.
- `config.py` holds the historically derived registration defaults.
- `cli.py` and `app/gui.py` are thin application boundaries around the same
  pipeline.

More detail is available in [docs/methodology.md](docs/methodology.md) and
[docs/rpc-workflow.md](docs/rpc-workflow.md).

## Installation

Python 3.10 or newer is required. Rasterio also depends on GDAL-compatible
native libraries; wheels provide these on many platforms.

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e .
```

For the optional desktop interface or development tools:

```bash
python -m pip install -e ".[gui]"
python -m pip install -e ".[dev]"
```

RPC orthorectification additionally requires GDAL Python bindings compatible
with the native GDAL library on the host:

```bash
python -m pip install -e ".[satellite]"
```

## Command-line usage

```bash
python -m rasterreg register \
  --source /path/to/source.tif \
  --reference /path/to/reference.tif \
  --output /path/to/registered.tif \
  --verbose
```

The historical workflow rotated source imagery by 180 degrees. Override that
only when the source orientation is known:

```bash
python -m rasterreg register \
  --source source.tif \
  --reference reference.tif \
  --output registered.tif \
  --rotation 0 \
  --add-alpha
```

Existing outputs are protected by default. Pass `--overwrite` to replace one;
the source and reference paths can never be used as the output path.

The original flat registration form (`rasterreg --source ...`) remains
supported. Process a satellite scene with external RPC XML and a DEM using:

```bash
python -m rasterreg scene \
  --scene-dir /path/to/scene \
  --dem /path/to/elevation.tif \
  --output-dir /path/to/output \
  --resolution 10
```

## Docker

The Docker image packages the core registration CLI and its runtime
dependencies only. It does not include the optional PyQt GUI, GDAL satellite
extra, or any imagery.

Build the image:

```bash
docker build -t raster-registration-toolkit .
```

Display CLI help:

```bash
docker run --rm raster-registration-toolkit --help
```

On Linux or macOS, place user-supplied input rasters in a writable `data`
directory and mount it into the container:

```bash
docker run --rm \
  -v "$(pwd)/data:/data" \
  raster-registration-toolkit \
  --source /data/source.tif \
  --reference /data/reference.tif \
  --output /data/registered.tif
```

The equivalent PowerShell command is:

```powershell
docker run --rm `
  -v "${PWD}/data:/data" `
  raster-registration-toolkit `
  --source /data/source.tif `
  --reference /data/reference.tif `
  --output /data/registered.tif
```

Docker provides a controlled CLI environment; it does not alter the validation
status described below.

## Python API

```python
from rasterreg import RegistrationConfig, georeference

result = georeference(
    source_path="source.tif",
    reference_path="reference.tif",
    output_path="registered.tif",
    config=RegistrationConfig(source_rotation_degrees=180),
)
print(result.alignment.match_count, result.alignment.inlier_count)
```

## Optional GUI

After installing the `gui` extra:

```bash
python app/gui.py
```

The GUI exposes separate **Raster Registration** and **Satellite Scene
(RPC / DEM)** tabs. Work runs outside the Qt event loop and the status panel
shows actual processing stages and factual outputs.

## Input requirements

For feature registration, the source and reference must:

- be raster formats readable by Rasterio;
- show sufficient overlapping visual structure for local feature matching;
- have numeric pixel values supported by OpenCV affine warping (`uint8`,
  `uint16`, `int16`, `float32`, or `float64`);
- use their first three bands as the visual feature image when multiband;
- fit in memory during full-resolution warping.

The reference raster must additionally contain a non-identity, north-up affine
transform and a CRS. Rotated or sheared reference rasters are rejected because
the current output grid is reconstructed from axis-aligned reference bounds.
The source does not need geospatial metadata. All source bands are warped
together, preserving the fourth band used as infrared data by the historical
workflow. `--add-alpha` adds a separate validity mask; otherwise
out-of-footprint warp pixels are zero.

For satellite processing, the primary TIFF needs a matching RPB/IMAGE RPC XML.
Terrain correction needs a georeferenced numeric DEM covering the nominal RPC
scene center. Automatic discovery rejects unresolved ambiguity.

## Data and imagery rights

The original high-resolution imagery, lower-resolution imagery, local basemap,
and cached map tiles are not included. The active application performs no tile
downloads and does not depend on Google imagery or a provider-specific cache.
Users must supply imagery and elevation data that they are legally permitted to
use and distribute. Review the rights of every documentation image before
publishing a fork.

## Validation scope

CI checks installation, imports, linting, deterministic unit tests, source
compilation, and core Docker startup. These engineering checks do not measure
positional accuracy. Evaluate operational outputs against independent ground
control appropriate to the sensor, DEM, and target dataset.

## Limitations

- SIFT needs enough distinctive, overlapping visual features in both images.
- A single affine model cannot represent terrain relief, lens effects, or other
  complex non-affine distortions.
- Matching thresholds may need tuning for different sensors, resolutions, and
  scene types.
- The output transform assumes the registered canvas spans the reference
  raster's bounds and that the reference CRS and transform are correct.
- Reference rasters must be north-up; rotated or sheared affine transforms are
  not supported by the current output-grid model.
- Full-resolution, multiband warping can require substantial memory and CPU.
- RPC accuracy depends on sensor metadata, DEM quality, and GDAL configuration.
- The satellite extra must match the native GDAL library on the host.
- Zero-valued source pixels and zero-filled pixels outside the warped footprint
  are indistinguishable unless an alpha band is requested.

## Development checks

```bash
python -m pytest
python -m ruff check .
python -m compileall -q src app tests
```

For quantitative accuracy assessment, compare registered outputs against
independent ground-control points appropriate to the target dataset.

GitHub Actions runs these engineering checks on Python 3.10, 3.11, and 3.12 for
pushes to `main` and `refactor/**` branches and for pull requests.
