"""Validation and metadata helpers for user-supplied elevation rasters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.coords import BoundingBox
from rasterio.crs import CRS
from rasterio.errors import RasterioIOError
from rasterio.warp import transform

from .exceptions import DEMValidationError
from .rpc import RPCModel


@dataclass(frozen=True, slots=True)
class DEMInfo:
    """Validated metadata for one elevation raster."""

    path: Path
    crs: CRS
    bounds: BoundingBox
    width: int
    height: int
    dtype: str
    nodata: float | int | None


def validate_dem(path: str | Path) -> DEMInfo:
    """Validate that a DEM is a readable, georeferenced numeric raster."""
    dem_path = Path(path).expanduser()
    if not dem_path.is_file():
        raise DEMValidationError(f"DEM does not exist or is not a file: {dem_path}")
    try:
        with rasterio.open(dem_path) as dataset:
            if dataset.count < 1:
                raise DEMValidationError("DEM does not contain an elevation band.")
            if dataset.crs is None:
                raise DEMValidationError("DEM does not define a coordinate reference system.")
            if dataset.width <= 0 or dataset.height <= 0:
                raise DEMValidationError("DEM has invalid raster dimensions.")
            dtype = dataset.dtypes[0]
            if not np.issubdtype(np.dtype(dtype), np.number):
                raise DEMValidationError(f"DEM elevation band is not numeric: {dtype}")
            return DEMInfo(
                path=dem_path.resolve(),
                crs=dataset.crs,
                bounds=dataset.bounds,
                width=dataset.width,
                height=dataset.height,
                dtype=dtype,
                nodata=dataset.nodata,
            )
    except RasterioIOError as exc:
        raise DEMValidationError(f"Could not open DEM {dem_path}: {exc}") from exc


def validate_dem_for_rpc(dem: DEMInfo, rpc: RPCModel) -> None:
    """Ensure the DEM covers the RPC model's nominal WGS84 scene center."""
    try:
        x_values, y_values = transform(
            CRS.from_epsg(4326),
            dem.crs,
            [rpc.longitude_offset],
            [rpc.latitude_offset],
        )
    except (ValueError, TypeError) as exc:
        raise DEMValidationError(
            f"Could not transform the RPC scene center into the DEM CRS: {exc}"
        ) from exc
    x, y = x_values[0], y_values[0]
    if not (dem.bounds.left <= x <= dem.bounds.right and dem.bounds.bottom <= y <= dem.bounds.top):
        raise DEMValidationError(
            "The DEM does not cover the nominal RPC scene center. Supply a DEM "
            "covering the satellite scene."
        )
