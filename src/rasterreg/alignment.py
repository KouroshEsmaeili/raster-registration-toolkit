"""Computer-vision primitives for multi-scale affine image registration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

from .config import RegistrationConfig
from .exceptions import ImageValidationError, RegistrationError

ImageArray = NDArray[np.generic]


@dataclass(frozen=True, slots=True)
class AlignmentResult:
    """Affine registration result and the pyramid metadata used to derive it."""

    full_resolution_matrix: NDArray[np.float64]
    downscaled_matrix: NDArray[np.float64]
    output_size: tuple[int, int]
    source_pyramid_levels: int
    reference_pyramid_levels: int
    match_count: int
    inlier_count: int


def pyramid_levels(height: int, maximum_height: int) -> int:
    """Return the number of half-resolution steps needed below a height limit."""
    if height <= 0 or maximum_height <= 0:
        raise ValueError("Image height and maximum height must be positive.")
    levels = 0
    while height > maximum_height:
        height //= 2
        levels += 1
    return levels


def pyramid_downscale(image: ImageArray, levels: int) -> ImageArray:
    """Downscale an image by repeatedly applying OpenCV's Gaussian pyramid."""
    if image.size == 0:
        raise ImageValidationError("Cannot downscale an empty image.")
    if levels < 0:
        raise ValueError("Pyramid levels cannot be negative.")
    result = image
    for _ in range(levels):
        result = cv2.pyrDown(result)
    return result


def to_grayscale(image: ImageArray) -> NDArray[np.uint8]:
    """Convert a display-ready image to an 8-bit grayscale feature image."""
    if image.ndim == 2:
        return image.astype(np.uint8, copy=False)
    if image.ndim != 3 or image.shape[2] not in {3, 4}:
        raise ImageValidationError(
            f"Feature images must have one, three, or four channels; got shape {image.shape}."
        )
    code = cv2.COLOR_RGB2GRAY if image.shape[2] == 3 else cv2.COLOR_RGBA2GRAY
    return cv2.cvtColor(image, code)


def detect_features(
    gray_image: NDArray[np.uint8],
) -> tuple[Sequence[cv2.KeyPoint], NDArray[np.float32]]:
    """Detect SIFT keypoints and descriptors in an 8-bit grayscale image."""
    keypoints, descriptors = cv2.SIFT_create().detectAndCompute(gray_image, None)
    if descriptors is None or len(keypoints) < 3:
        raise RegistrationError("SIFT found fewer than three usable features in an input image.")
    return keypoints, np.asarray(descriptors, dtype=np.float32)


def match_descriptors(
    source_descriptors: NDArray[np.float32],
    reference_descriptors: NDArray[np.float32],
    config: RegistrationConfig,
) -> list[cv2.DMatch]:
    """Apply two-nearest-neighbor matching, Lowe ratio filtering, and trimming.

    Percentile trimming discards both the closest and most distant
    ratio-filtered matches and should be validated on representative data when
    tuning its defaults.
    """
    matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
    neighbor_pairs = matcher.knnMatch(source_descriptors, reference_descriptors, k=2)
    ratio_matches: list[cv2.DMatch] = []
    for pair in neighbor_pairs:
        if len(pair) != 2:
            continue
        first, second = pair
        if first.distance < config.ratio_threshold * second.distance:
            ratio_matches.append(first)
    if len(ratio_matches) < 3:
        raise RegistrationError(
            f"Only {len(ratio_matches)} matches passed ratio filtering; "
            "at least three are required."
        )

    distances = np.asarray([match.distance for match in ratio_matches])
    low, high = np.percentile(
        distances,
        [config.distance_percentile_low, config.distance_percentile_high],
    )
    trimmed = [match for match in ratio_matches if low < match.distance < high]
    if len(trimmed) < 3:
        raise RegistrationError(
            f"Only {len(trimmed)} matches remained after percentile filtering; "
            "at least three are required."
        )
    return trimmed


def estimate_affine(
    source_keypoints: Sequence[cv2.KeyPoint],
    reference_keypoints: Sequence[cv2.KeyPoint],
    matches: Sequence[cv2.DMatch],
    reprojection_threshold: float,
) -> tuple[NDArray[np.float64], int]:
    """Estimate a six-parameter affine transform with RANSAC."""
    source_points = np.float32([source_keypoints[match.queryIdx].pt for match in matches]).reshape(
        -1, 2
    )
    reference_points = np.float32(
        [reference_keypoints[match.trainIdx].pt for match in matches]
    ).reshape(-1, 2)
    matrix, inlier_mask = cv2.estimateAffine2D(
        source_points,
        reference_points,
        method=cv2.RANSAC,
        ransacReprojThreshold=reprojection_threshold,
    )
    if matrix is None:
        raise RegistrationError("RANSAC could not estimate an affine transformation.")
    inlier_count = int(inlier_mask.sum()) if inlier_mask is not None else 0
    return np.asarray(matrix, dtype=np.float64), inlier_count


def scale_affine_to_full_resolution(
    downscaled_matrix: NDArray[np.float64],
    source_levels: int,
    reference_levels: int,
    reference_shape: tuple[int, ...],
) -> tuple[NDArray[np.float64], tuple[int, int]]:
    """Map a pyramid-space affine transform to the full-resolution output grid.

    The output grid uses the source pyramid's effective pixel scale. Translation
    is converted back to full-resolution source coordinates, while output
    dimensions account for the relative source and reference pyramid scales.
    """
    source_scale = 1.0 / (2**source_levels)
    reference_scale = 1.0 / (2**reference_levels)
    output_scale = reference_scale / source_scale
    matrix = np.asarray(downscaled_matrix, dtype=np.float64).copy()
    matrix[:, 2] /= source_scale
    output_size = (
        max(1, int(reference_shape[1] * output_scale)),
        max(1, int(reference_shape[0] * output_scale)),
    )
    return matrix, output_size


def register_images(
    source_feature_image: ImageArray,
    reference_feature_image: ImageArray,
    config: RegistrationConfig,
) -> AlignmentResult:
    """Register source imagery to reference imagery using SIFT and RANSAC."""
    cv2.setRNGSeed(config.seed)
    source_levels = pyramid_levels(source_feature_image.shape[0], config.source_max_height)
    reference_levels = pyramid_levels(reference_feature_image.shape[0], config.reference_max_height)
    source_small = pyramid_downscale(source_feature_image, source_levels)
    reference_small = pyramid_downscale(reference_feature_image, reference_levels)
    source_keypoints, source_descriptors = detect_features(to_grayscale(source_small))
    reference_keypoints, reference_descriptors = detect_features(to_grayscale(reference_small))
    matches = match_descriptors(source_descriptors, reference_descriptors, config)
    downscaled_matrix, inlier_count = estimate_affine(
        source_keypoints,
        reference_keypoints,
        matches,
        config.ransac_reprojection_threshold,
    )
    full_matrix, output_size = scale_affine_to_full_resolution(
        downscaled_matrix,
        source_levels,
        reference_levels,
        reference_feature_image.shape,
    )
    return AlignmentResult(
        full_resolution_matrix=full_matrix,
        downscaled_matrix=downscaled_matrix,
        output_size=output_size,
        source_pyramid_levels=source_levels,
        reference_pyramid_levels=reference_levels,
        match_count=len(matches),
        inlier_count=inlier_count,
    )


def warp_multiband(
    image: ImageArray,
    matrix: NDArray[np.float64],
    output_size: tuple[int, int],
) -> ImageArray:
    """Apply one affine transform to every source band without rescaling values."""
    if image.ndim not in {2, 3}:
        raise ImageValidationError(f"Expected a 2D or 3D image; got shape {image.shape}.")
    supported_dtypes = {
        np.dtype(np.uint8),
        np.dtype(np.uint16),
        np.dtype(np.int16),
        np.dtype(np.float32),
        np.dtype(np.float64),
    }
    if image.dtype not in supported_dtypes:
        raise ImageValidationError(
            f"OpenCV affine warping does not support source dtype {image.dtype}; "
            "convert it to uint8, uint16, int16, float32, or float64."
        )
    return cv2.warpAffine(image, matrix, output_size)
