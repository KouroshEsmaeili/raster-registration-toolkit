"""Raster registration and RPC/DEM orthorectification toolkit."""

from .config import RegistrationConfig
from .exceptions import (
    DEMValidationError,
    GeoreferencerError,
    ImageValidationError,
    OrthorectificationError,
    RegistrationError,
    RPCMetadataError,
    SceneDiscoveryError,
)
from .pipeline import PipelineResult, georeference
from .satellite import (
    BatchSceneResult,
    SatelliteSceneConfig,
    SatelliteSceneResult,
    process_satellite_batch,
    process_satellite_scene,
)

__all__ = [
    "BatchSceneResult",
    "DEMValidationError",
    "GeoreferencerError",
    "ImageValidationError",
    "OrthorectificationError",
    "PipelineResult",
    "RegistrationConfig",
    "RegistrationError",
    "RPCMetadataError",
    "SatelliteSceneConfig",
    "SatelliteSceneResult",
    "SceneDiscoveryError",
    "georeference",
    "process_satellite_batch",
    "process_satellite_scene",
]

__version__ = "0.1.0"
