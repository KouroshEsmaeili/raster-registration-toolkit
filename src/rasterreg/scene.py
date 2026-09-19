"""Provider-neutral discovery of satellite scene rasters and RPC metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import rasterio

from .exceptions import SceneDiscoveryError

_RASTER_SUFFIXES = {".tif", ".tiff"}
_PREVIEW_SUFFIXES = {".jpg", ".jpeg", ".png"}


@dataclass(frozen=True, slots=True)
class SceneOverrides:
    """Explicit scene inputs, used before automatic discovery."""

    image: Path | None = None
    rpc: Path | None = None
    panchromatic_image: Path | None = None
    panchromatic_rpc: Path | None = None
    reference: Path | None = None


@dataclass(frozen=True, slots=True)
class SceneInputs:
    """Inputs discovered for one RPC satellite scene."""

    root: Path
    image: Path
    rpc: Path
    panchromatic_image: Path | None = None
    panchromatic_rpc: Path | None = None
    reference: Path | None = None
    preview: Path | None = None


def _files(root: Path, suffixes: set[str]) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes),
        key=lambda path: str(path).lower(),
    )


def _dimensions(path: Path) -> tuple[int, int, int]:
    try:
        with rasterio.open(path) as dataset:
            return dataset.width, dataset.height, dataset.count
    except Exception as exc:
        raise SceneDiscoveryError(f"Could not inspect scene raster {path}: {exc}") from exc


def _select_unique(candidates: list[Path], purpose: str) -> Path:
    if not candidates:
        raise SceneDiscoveryError(f"No {purpose} candidate was found.")
    if len(candidates) > 1:
        joined = ", ".join(str(path) for path in candidates)
        raise SceneDiscoveryError(f"Ambiguous {purpose}; specify an explicit path: {joined}")
    return candidates[0]


def _related_rpc(image: Path, xml_files: list[Path]) -> Path:
    stem = image.stem.lower()
    direct = [path for path in xml_files if path.stem.lower() == stem]
    if len(direct) == 1:
        return direct[0]
    containing = [path for path in xml_files if stem in path.stem.lower()]
    if len(containing) == 1:
        return containing[0]
    same_dir = [path for path in xml_files if path.parent == image.parent]
    return _select_unique(same_dir or xml_files, f"RPC XML for {image.name}")


def discover_scene(
    scene_directory: str | Path,
    overrides: SceneOverrides | None = None,
) -> SceneInputs:
    """Discover a primary multispectral image, its RPC XML, and optional companions.

    Explicit overrides always win. Automatic selection uses directory/name hints
    followed by raster dimensions; unresolved ties are rejected instead of guessed.
    """
    root = Path(scene_directory).expanduser().resolve()
    if not root.is_dir():
        raise SceneDiscoveryError(f"Scene directory does not exist: {root}")
    selected = overrides or SceneOverrides()
    rasters = _files(root, _RASTER_SUFFIXES)
    xml_files = _files(root, {".xml"})
    if not rasters and selected.image is None:
        raise SceneDiscoveryError(f"No TIFF rasters were found below {root}.")

    dimensions = {path: _dimensions(path) for path in rasters}
    if selected.image is not None:
        image = selected.image.expanduser().resolve()
    else:
        primary_candidates = [
            path
            for path in rasters
            if not any(
                token in path.stem.lower()
                for token in ("reference", "quicklook", "preview", "ortho")
            )
        ] or rasters
        multispectral = [
            path
            for path in primary_candidates
            if dimensions[path][2] > 1
            or any(token in str(path).lower() for token in ("psh", "pansharp", "multispectral"))
        ]
        pool = multispectral or primary_candidates
        largest = max(dimensions[path][0] * dimensions[path][1] for path in pool)
        image = _select_unique(
            [path for path in pool if dimensions[path][0] * dimensions[path][1] == largest],
            "primary scene raster",
        )
    if not image.is_file():
        raise SceneDiscoveryError(f"Primary scene raster does not exist: {image}")

    rpc = selected.rpc.expanduser().resolve() if selected.rpc else _related_rpc(image, xml_files)
    if not rpc.is_file():
        raise SceneDiscoveryError(f"Primary RPC XML does not exist: {rpc}")

    pan = selected.panchromatic_image
    if pan is None:
        candidates = [
            path
            for path in rasters
            if path != image
            and dimensions[path][2] == 1
            and any(token in str(path).lower() for token in ("/pan/", "\\pan\\", "_pan", "-pan"))
        ]
        if len(candidates) == 1:
            pan = candidates[0]
    if pan is not None:
        pan = pan.expanduser().resolve()
        if not pan.is_file():
            raise SceneDiscoveryError(f"Panchromatic raster does not exist: {pan}")

    pan_rpc = selected.panchromatic_rpc
    if pan_rpc is not None:
        pan_rpc = pan_rpc.expanduser().resolve()
    elif pan is not None:
        try:
            pan_rpc = _related_rpc(pan, [path for path in xml_files if path != rpc])
        except SceneDiscoveryError:
            pan_rpc = None

    reference = selected.reference
    if reference is None:
        candidates = [
            path
            for path in rasters
            if path != image
            and path != pan
            and any(token in path.stem.lower() for token in ("reference", "quicklook", "ortho"))
        ]
        if len(candidates) == 1:
            reference = candidates[0]
    if reference is not None:
        reference = reference.expanduser().resolve()

    previews = _files(root, _PREVIEW_SUFFIXES)
    preview = previews[0] if len(previews) == 1 else None
    return SceneInputs(root, image, rpc, pan, pan_rpc, reference, preview)
