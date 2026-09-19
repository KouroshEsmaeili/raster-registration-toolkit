"""Application pipeline coordinating raster IO, registration, and output."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2

from .alignment import AlignmentResult, register_images, warp_multiband
from .config import RegistrationConfig
from .exceptions import ImageValidationError
from .geospatial import transform_for_bounds
from .image_io import add_alpha_from_valid_pixels, feature_image, read_raster, write_geotiff

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Summary of one completed pipeline invocation."""

    output_path: Path
    alignment: AlignmentResult


def _rotate_quarter_turns(image, degrees: int):
    """Rotate by quarter turns without interpolation."""
    rotations = {
        0: None,
        90: cv2.ROTATE_90_COUNTERCLOCKWISE,
        180: cv2.ROTATE_180,
        270: cv2.ROTATE_90_CLOCKWISE,
    }
    code = rotations[degrees]
    return image if code is None else cv2.rotate(image, code)


def georeference(
    source_path: str | Path,
    reference_path: str | Path,
    output_path: str | Path,
    config: RegistrationConfig | None = None,
) -> PipelineResult:
    """Register a source raster to a georeferenced reference and write GeoTIFF.

    All source bands—including a fourth infrared band when present—are rotated
    and warped with the same affine transform. The reference supplies bounds
    and CRS; its pixel values are used only for feature matching.
    """
    settings = config or RegistrationConfig()
    source_path = Path(source_path).expanduser()
    reference_path = Path(reference_path).expanduser()
    output_path = Path(output_path).expanduser()
    output_resolved = output_path.resolve(strict=False)
    input_paths = {
        source_path.resolve(strict=False),
        reference_path.resolve(strict=False),
    }
    if output_resolved in input_paths:
        raise ImageValidationError("The output path must not overwrite either input raster.")
    if output_path.exists() and not settings.overwrite:
        raise ImageValidationError(
            f"Output already exists: {output_path}. Enable overwrite explicitly to replace it."
        )

    LOGGER.info("Reading source raster: %s", source_path)
    source = read_raster(source_path)
    LOGGER.info("Reading georeferenced reference raster: %s", reference_path)
    reference = read_raster(reference_path, require_georeferencing=True)

    rotated_source = _rotate_quarter_turns(source.data, settings.source_rotation_degrees)
    LOGGER.info("Estimating affine registration")
    alignment = register_images(
        feature_image(rotated_source),
        feature_image(reference.data),
        settings,
    )
    LOGGER.info(
        "Warping %s retained matches (%s RANSAC inliers)",
        alignment.match_count,
        alignment.inlier_count,
    )
    warped = warp_multiband(
        rotated_source,
        alignment.full_resolution_matrix,
        alignment.output_size,
    )
    if settings.add_alpha:
        warped = add_alpha_from_valid_pixels(warped)

    transform = transform_for_bounds(
        reference.bounds,
        width=warped.shape[1],
        height=warped.shape[0],
    )
    written_path = write_geotiff(
        output_path,
        warped,
        crs=reference.crs,  # validated by read_raster
        transform=transform,
    )
    LOGGER.info("Wrote registered GeoTIFF: %s", written_path)
    return PipelineResult(output_path=written_path, alignment=alignment)
