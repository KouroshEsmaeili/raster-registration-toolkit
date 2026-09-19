"""Geospatial metadata helpers for registered raster output."""

from __future__ import annotations

from rasterio.coords import BoundingBox
from rasterio.crs import CRS
from rasterio.transform import Affine, from_bounds

from .exceptions import ImageValidationError

_TRANSFORM_TOLERANCE = 1e-12


def validate_georeferencing(crs: CRS | None, transform: Affine) -> CRS:
    """Ensure a reference raster has usable, north-up georeferencing."""
    if crs is None:
        raise ImageValidationError("The reference raster has no coordinate reference system.")
    if transform.is_identity:
        raise ImageValidationError(
            "The reference raster has an identity (ungeoreferenced) transform."
        )
    if abs(transform.b) > _TRANSFORM_TOLERANCE or abs(transform.d) > _TRANSFORM_TOLERANCE:
        raise ImageValidationError(
            "Rotated or sheared reference rasters are not supported by the current "
            "output-grid model."
        )
    return crs


def transform_for_bounds(bounds: BoundingBox, width: int, height: int) -> Affine:
    """Construct a north-up pixel transform spanning reference raster bounds."""
    if width <= 0 or height <= 0:
        raise ValueError("Output width and height must be positive.")
    if bounds.left >= bounds.right or bounds.bottom >= bounds.top:
        raise ImageValidationError(f"Reference bounds are invalid: {bounds!r}.")
    return from_bounds(bounds.left, bounds.bottom, bounds.right, bounds.top, width, height)
