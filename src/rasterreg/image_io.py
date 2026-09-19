"""Raster loading, display conversion, and GeoTIFF output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from numpy.typing import NDArray
from rasterio.coords import BoundingBox
from rasterio.crs import CRS
from rasterio.errors import RasterioIOError
from rasterio.transform import Affine

from .exceptions import ImageValidationError
from .geospatial import validate_georeferencing

ImageArray = NDArray[np.generic]


@dataclass(frozen=True, slots=True)
class RasterImage:
    """In-memory band-last raster data with its geospatial metadata."""

    data: ImageArray
    crs: CRS | None
    transform: Affine
    bounds: BoundingBox
    nodata: float | int | None


def read_raster(path: str | Path, *, require_georeferencing: bool = False) -> RasterImage:
    """Read all raster bands and return a band-last array."""
    raster_path = Path(path).expanduser()
    if not raster_path.is_file():
        raise ImageValidationError(f"Raster does not exist or is not a file: {raster_path}")
    try:
        with rasterio.open(raster_path) as dataset:
            data = np.moveaxis(dataset.read(), 0, -1)
            if data.shape[2] == 1:
                data = data[:, :, 0]
            crs = dataset.crs
            transform = dataset.transform
            bounds = dataset.bounds
            nodata = dataset.nodata
    except RasterioIOError as exc:
        raise ImageValidationError(f"Could not open raster {raster_path}: {exc}") from exc
    if data.size == 0:
        raise ImageValidationError(f"Raster contains no pixels: {raster_path}")
    if require_georeferencing:
        validate_georeferencing(crs, transform)
    return RasterImage(data=data, crs=crs, transform=transform, bounds=bounds, nodata=nodata)


def _normalize_band(band: ImageArray) -> NDArray[np.uint8]:
    """Robustly normalize one numeric band for feature extraction only."""
    finite = np.asarray(band)[np.isfinite(band)]
    if finite.size == 0:
        raise ImageValidationError("An image band contains no finite pixel values.")
    low, high = np.percentile(finite, [2.0, 98.0])
    if high <= low:
        return np.zeros(band.shape, dtype=np.uint8)
    scaled = (np.asarray(band, dtype=np.float64) - low) * (255.0 / (high - low))
    return np.clip(scaled, 0, 255).astype(np.uint8)


def feature_image(data: ImageArray) -> NDArray[np.uint8]:
    """Create an 8-bit one- or three-band view while preserving original data."""
    if data.ndim == 2:
        return _normalize_band(data)
    if data.ndim != 3 or data.shape[2] < 1:
        raise ImageValidationError(f"Unsupported raster shape: {data.shape}.")
    selected = data[:, :, : min(3, data.shape[2])]
    if selected.shape[2] == 1:
        return _normalize_band(selected[:, :, 0])
    if selected.shape[2] == 2:
        selected = np.dstack((selected, selected[:, :, 1]))
    return np.dstack([_normalize_band(selected[:, :, index]) for index in range(3)])


def add_alpha_from_valid_pixels(image: ImageArray) -> ImageArray:
    """Append an opaque mask where at least one band is nonzero."""
    bands = image[:, :, None] if image.ndim == 2 else image
    valid = np.any(bands != 0, axis=2)
    alpha_max = np.iinfo(image.dtype).max if np.issubdtype(image.dtype, np.integer) else 1.0
    alpha = np.where(valid, alpha_max, 0).astype(image.dtype)
    return np.dstack((bands, alpha))


def write_geotiff(
    path: str | Path,
    data: ImageArray,
    *,
    crs: CRS,
    transform: Affine,
    nodata: float | int | None = None,
) -> Path:
    """Write band-last image data as a compressed GeoTIFF."""
    output_path = Path(path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bands = data[:, :, None] if data.ndim == 2 else data
    if bands.ndim != 3:
        raise ImageValidationError(
            f"Expected output with two or three dimensions; got {data.shape}."
        )
    profile = {
        "driver": "GTiff",
        "height": bands.shape[0],
        "width": bands.shape[1],
        "count": bands.shape[2],
        "dtype": bands.dtype,
        "crs": crs,
        "transform": transform,
        "compress": "lzw",
    }
    if nodata is not None:
        profile["nodata"] = nodata
    with rasterio.open(output_path, "w", **profile) as destination:
        destination.write(np.moveaxis(bands, -1, 0))
    return output_path
