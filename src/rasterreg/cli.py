"""Command-line interfaces for raster registration and RPC satellite scenes."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from .config import RegistrationConfig
from .exceptions import GeoreferencerError
from .pipeline import georeference
from .satellite import SatelliteSceneConfig, process_satellite_scene


def _add_registration_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", required=True, type=Path, help="Source raster to align.")
    parser.add_argument(
        "--reference",
        required=True,
        type=Path,
        help="Georeferenced reference raster supplying imagery, bounds, and CRS.",
    )
    parser.add_argument("--output", required=True, type=Path, help="Output GeoTIFF path.")
    parser.add_argument("--rotation", type=int, choices=(0, 90, 180, 270), default=180)
    parser.add_argument("--add-alpha", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--verbose", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser without performing any work."""
    parser = argparse.ArgumentParser(
        prog="rasterreg",
        description="Register rasters or process an RPC/DEM satellite scene.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser("register", help="Feature-register overlapping rasters.")
    _add_registration_arguments(register)
    scene = commands.add_parser("scene", help="Process an RPC satellite scene.")
    scene.add_argument("--scene-dir", required=True, type=Path)
    scene.add_argument("--dem", type=Path, help="Elevation raster; required unless --no-dem.")
    scene.add_argument("--output-dir", required=True, type=Path)
    scene.add_argument("--reference", type=Path, help="Reference raster for optional refinement.")
    scene.add_argument("--output-crs", default="EPSG:4326")
    scene.add_argument("--resolution", type=float, default=10.0, metavar="METERS")
    scene.add_argument("--no-dem", action="store_true")
    scene.add_argument("--refine", action="store_true")
    scene.add_argument("--overwrite", action="store_true")
    scene.add_argument("--verbose", action="store_true")
    return parser


def _normalized_argv(argv: Sequence[str] | None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if values and values[0] not in {"register", "scene", "-h", "--help"}:
        values.insert(0, "register")
    return values


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected workflow and return a process exit code."""
    args = build_parser().parse_args(_normalized_argv(argv))
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s: %(message)s"
    )
    try:
        if args.command == "register":
            result = georeference(
                args.source,
                args.reference,
                args.output,
                RegistrationConfig(
                    source_rotation_degrees=args.rotation,
                    add_alpha=args.add_alpha,
                    overwrite=args.overwrite,
                ),
            )
            print(result.output_path)
            print(
                f"retained_matches={result.alignment.match_count} "
                f"ransac_inliers={result.alignment.inlier_count}"
            )
        else:
            result = process_satellite_scene(
                args.scene_dir,
                args.dem,
                args.output_dir,
                reference_path=args.reference,
                config=SatelliteSceneConfig(
                    output_crs=args.output_crs,
                    resolution_meters=args.resolution,
                    use_dem=not args.no_dem,
                    refine_features=args.refine,
                    overwrite=args.overwrite,
                ),
                status=lambda message: logging.info("%s", message),
            )
            print(result.output_path)
            print(result.metadata_path)
            print(result.footprint_path)
    except (GeoreferencerError, OSError, ValueError) as exc:
        logging.error("%s", exc)
        return 1
    return 0
