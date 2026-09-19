"""Optional GDAL-backed RPC orthorectification primitives."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from pathlib import Path

from rasterio.crs import CRS

from .dem import DEMInfo
from .exceptions import OrthorectificationError
from .rpc import RPCModel


@dataclass(frozen=True, slots=True)
class OrthorectificationConfig:
    """Output controls for RPC orthorectification.

    Resolution is specified in meters. For a geographic output CRS, the value
    is converted to an approximate angular resolution at the RPC scene center.
    """

    output_crs: str = "EPSG:4326"
    resolution_meters: float = 10.0
    resampling: str = "bilinear"
    add_alpha: bool = False
    overwrite: bool = False

    def __post_init__(self) -> None:
        if not math.isfinite(self.resolution_meters) or self.resolution_meters <= 0:
            raise ValueError("resolution_meters must be a positive finite value.")
        try:
            CRS.from_user_input(self.output_crs)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid output CRS: {self.output_crs}") from exc


@dataclass(frozen=True, slots=True)
class OrthorectificationResult:
    """Metadata describing one GDAL RPC warp output."""

    output_path: Path
    width: int
    height: int
    band_count: int
    crs: CRS


def output_resolution(config: OrthorectificationConfig, rpc: RPCModel) -> tuple[float, float]:
    """Convert meter resolution to units of the configured output CRS."""
    crs = CRS.from_user_input(config.output_crs)
    if crs.is_geographic:
        meters_per_degree_y = 111_320.0
        meters_per_degree_x = meters_per_degree_y * math.cos(math.radians(rpc.latitude_offset))
        if meters_per_degree_x <= 0:
            raise OrthorectificationError(
                "Cannot derive geographic resolution at the RPC latitude offset."
            )
        return (
            config.resolution_meters / meters_per_degree_x,
            config.resolution_meters / meters_per_degree_y,
        )

    try:
        _, meters_per_unit = crs.linear_units_factor
    except (AttributeError, TypeError, ValueError) as exc:
        raise OrthorectificationError(
            f"Cannot determine linear units for output CRS {crs}."
        ) from exc
    return (
        config.resolution_meters / meters_per_unit,
        config.resolution_meters / meters_per_unit,
    )


def orthorectify_rpc(
    image_path: str | Path,
    rpc: RPCModel,
    output_path: str | Path,
    *,
    dem: DEMInfo | None,
    config: OrthorectificationConfig | None = None,
) -> OrthorectificationResult:
    """Orthorectify an image using its RPC model and an optional validated DEM."""
    settings = config or OrthorectificationConfig()
    source_path = Path(image_path).expanduser()
    destination_path = Path(output_path).expanduser()
    if not source_path.is_file():
        raise OrthorectificationError(f"RPC source image does not exist: {source_path}")
    if source_path.resolve() == destination_path.resolve(strict=False):
        raise OrthorectificationError("RPC output must not overwrite the source image.")
    if destination_path.exists() and not settings.overwrite:
        raise OrthorectificationError(
            f"RPC output already exists: {destination_path}. Enable overwrite to replace it."
        )

    try:
        from osgeo import gdal
    except ImportError as exc:
        raise OrthorectificationError(
            "RPC orthorectification requires GDAL Python bindings. Install the "
            "optional satellite dependencies in a GDAL-compatible environment."
        ) from exc

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    output_crs = CRS.from_user_input(settings.output_crs)
    x_resolution, y_resolution = output_resolution(settings, rpc)
    vrt_path = f"/vsimem/rasterreg-{uuid.uuid4().hex}.vrt"
    created_output = not destination_path.exists()

    gdal.UseExceptions()
    source_dataset = None
    vrt_dataset = None
    result_dataset = None
    try:
        source_dataset = gdal.Open(str(source_path), gdal.GA_ReadOnly)
        if source_dataset is None:
            raise OrthorectificationError(f"GDAL could not open source image: {source_path}")
        vrt_dataset = gdal.Translate(vrt_path, source_dataset, format="VRT")
        if vrt_dataset is None:
            raise OrthorectificationError("GDAL could not create an in-memory RPC VRT.")
        vrt_dataset.SetMetadata(rpc.to_gdal_metadata(), "RPC")
        vrt_dataset.FlushCache()

        transformer_options = []
        if dem is not None:
            transformer_options.extend([f"RPC_DEM={dem.path}", "RPC_DEMINTERPOLATION=bilinear"])
        options = gdal.WarpOptions(
            format="GTiff",
            dstSRS=output_crs.to_wkt(),
            xRes=x_resolution,
            yRes=y_resolution,
            rpc=True,
            transformerOptions=transformer_options,
            resampleAlg=settings.resampling,
            dstAlpha=settings.add_alpha,
            creationOptions=["COMPRESS=LZW", "TILED=YES"],
        )
        result_dataset = gdal.Warp(str(destination_path), vrt_dataset, options=options)
        if result_dataset is None:
            raise OrthorectificationError("GDAL RPC warp did not produce an output dataset.")
        result_dataset.FlushCache()
        return OrthorectificationResult(
            output_path=destination_path.resolve(),
            width=result_dataset.RasterXSize,
            height=result_dataset.RasterYSize,
            band_count=result_dataset.RasterCount,
            crs=output_crs,
        )
    except OrthorectificationError:
        if created_output:
            destination_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        if created_output:
            destination_path.unlink(missing_ok=True)
        raise OrthorectificationError(f"GDAL RPC orthorectification failed: {exc}") from exc
    finally:
        result_dataset = None
        vrt_dataset = None
        source_dataset = None
        gdal.Unlink(vrt_path)
