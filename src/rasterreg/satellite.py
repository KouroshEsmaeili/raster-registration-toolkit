"""High-level, provider-neutral RPC/DEM satellite scene workflow."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import RegistrationConfig
from .dem import validate_dem, validate_dem_for_rpc
from .orthorectification import OrthorectificationConfig, orthorectify_rpc
from .pipeline import PipelineResult, georeference
from .reporting import write_footprint_geojson, write_metadata_report
from .rpc import parse_rpc_xml
from .scene import SceneInputs, SceneOverrides, discover_scene

StatusCallback = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class SatelliteSceneConfig:
    """Controls for the RPC/DEM workflow."""

    output_crs: str = "EPSG:4326"
    resolution_meters: float = 10.0
    use_dem: bool = True
    refine_features: bool = False
    overwrite: bool = False


@dataclass(frozen=True, slots=True)
class SatelliteSceneResult:
    """Outputs and factual processing details for a satellite scene."""

    output_path: Path
    metadata_path: Path
    footprint_path: Path
    scene: SceneInputs
    refinement: PipelineResult | None = None
    panchromatic_output: Path | None = None


@dataclass(frozen=True, slots=True)
class BatchSceneResult:
    """Success or isolated failure for one item in a sequential batch."""

    scene_directory: Path
    result: SatelliteSceneResult | None = None
    error: str | None = None


def _emit(callback: StatusCallback | None, message: str) -> None:
    if callback is not None:
        callback(message)


def process_satellite_scene(
    scene_directory: str | Path,
    dem_path: str | Path | None,
    output_directory: str | Path,
    *,
    reference_path: str | Path | None = None,
    config: SatelliteSceneConfig | None = None,
    overrides: SceneOverrides | None = None,
    status: StatusCallback | None = None,
) -> SatelliteSceneResult:
    """Discover, orthorectify, optionally refine, and report one scene."""
    settings = config or SatelliteSceneConfig()
    explicit = overrides or SceneOverrides()
    if reference_path is not None:
        explicit = SceneOverrides(
            image=explicit.image,
            rpc=explicit.rpc,
            panchromatic_image=explicit.panchromatic_image,
            panchromatic_rpc=explicit.panchromatic_rpc,
            reference=Path(reference_path),
        )

    _emit(status, "Discovering scene inputs")
    scene = discover_scene(scene_directory, explicit)
    _emit(status, "Parsing RPC metadata")
    document = parse_rpc_xml(scene.rpc)

    dem = None
    if settings.use_dem:
        if dem_path is None:
            raise ValueError("A DEM is required when DEM correction is enabled.")
        _emit(status, "Validating elevation raster")
        dem = validate_dem(dem_path)
        validate_dem_for_rpc(dem, document.rpc)

    output_dir = Path(output_directory).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    registered = output_dir / "registered.tif"
    coarse = output_dir / "rpc_orthorectified.tif"
    rpc_destination = coarse if settings.refine_features else registered
    ortho_config = OrthorectificationConfig(
        output_crs=settings.output_crs,
        resolution_meters=settings.resolution_meters,
        overwrite=settings.overwrite,
    )
    _emit(status, "Orthorectifying primary raster")
    orthorectify_rpc(scene.image, document.rpc, rpc_destination, dem=dem, config=ortho_config)

    refinement = None
    if settings.refine_features:
        if scene.reference is None:
            raise ValueError("Feature refinement requires a georeferenced reference raster.")
        _emit(status, "Refining alignment with image features")
        refinement = georeference(
            coarse,
            scene.reference,
            registered,
            RegistrationConfig(source_rotation_degrees=0, overwrite=settings.overwrite),
        )

    pan_output = None
    if scene.panchromatic_image is not None and scene.panchromatic_rpc is not None:
        _emit(status, "Orthorectifying panchromatic raster")
        pan_document = parse_rpc_xml(scene.panchromatic_rpc)
        if dem is not None:
            validate_dem_for_rpc(dem, pan_document.rpc)
        pan_output = output_dir / "panchromatic_registered.tif"
        orthorectify_rpc(
            scene.panchromatic_image,
            pan_document.rpc,
            pan_output,
            dem=dem,
            config=ortho_config,
        )

    _emit(status, "Writing processing reports")
    metadata: dict[str, Any] = {
        "workflow": "rpc-dem-satellite-scene",
        "scene_directory": str(scene.root),
        "source_raster": str(scene.image),
        "rpc_xml": str(scene.rpc),
        "dem": str(dem.path) if dem is not None else None,
        "output": str(registered),
        "output_crs": settings.output_crs,
        "resolution_meters": settings.resolution_meters,
        "feature_refinement": settings.refine_features,
        "rpc_schema": document.schema,
        "image_metadata": dict(document.image_metadata),
        "panchromatic_output": str(pan_output) if pan_output else None,
    }
    if refinement is not None:
        metadata["retained_matches"] = refinement.alignment.match_count
        metadata["ransac_inliers"] = refinement.alignment.inlier_count
    metadata_path = write_metadata_report(output_dir / "metadata.json", metadata)
    footprint_path = write_footprint_geojson(registered, output_dir / "footprint.geojson")
    _emit(status, "Satellite scene completed")
    return SatelliteSceneResult(
        registered.resolve(), metadata_path, footprint_path, scene, refinement, pan_output
    )


def process_satellite_batch(
    scene_directories: Iterable[str | Path],
    dem_path: str | Path | None,
    output_root: str | Path,
    *,
    config: SatelliteSceneConfig | None = None,
    status: StatusCallback | None = None,
) -> tuple[BatchSceneResult, ...]:
    """Process scenes sequentially while containing failures to each scene."""
    destination = Path(output_root).expanduser().resolve()
    items: list[BatchSceneResult] = []
    for value in scene_directories:
        scene_directory = Path(value).expanduser().resolve()
        _emit(status, f"Starting scene: {scene_directory.name}")
        try:
            result = process_satellite_scene(
                scene_directory,
                dem_path,
                destination / scene_directory.name,
                config=config,
                status=status,
            )
        except (OSError, ValueError) as exc:
            _emit(status, f"Scene failed: {scene_directory.name}: {exc}")
            items.append(BatchSceneResult(scene_directory, error=str(exc)))
        else:
            items.append(BatchSceneResult(scene_directory, result=result))
    return tuple(items)
