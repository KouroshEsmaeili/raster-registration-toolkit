"""Configuration for the image-registration pipeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RegistrationConfig:
    """Tunable values retained from the historical implementation.

    The defaults preserve the latest implementation's matching thresholds,
    pyramid limits, deterministic OpenCV seed, and 180-degree source rotation.
    Applications can override them for different sensors and scene types.
    """

    source_max_height: int = 5_000
    reference_max_height: int = 10_000
    ratio_threshold: float = 0.8
    distance_percentile_low: float = 20.0
    distance_percentile_high: float = 80.0
    ransac_reprojection_threshold: float = 3.0
    seed: int = 42
    source_rotation_degrees: int = 180
    add_alpha: bool = False
    overwrite: bool = False

    def __post_init__(self) -> None:
        """Reject invalid settings before expensive image work begins."""
        if self.source_max_height <= 0 or self.reference_max_height <= 0:
            raise ValueError("Pyramid height limits must be positive.")
        if not 0.0 < self.ratio_threshold < 1.0:
            raise ValueError("ratio_threshold must be between 0 and 1.")
        if not 0.0 <= self.distance_percentile_low < self.distance_percentile_high <= 100.0:
            raise ValueError("Distance percentiles must satisfy 0 <= low < high <= 100.")
        if self.ransac_reprojection_threshold <= 0:
            raise ValueError("ransac_reprojection_threshold must be positive.")
        if self.source_rotation_degrees not in {0, 90, 180, 270}:
            raise ValueError("source_rotation_degrees must be 0, 90, 180, or 270.")
