"""Machine-readable reports for processed satellite scenes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import rasterio
from rasterio.warp import transform_bounds


def write_metadata_report(path: str | Path, values: dict[str, Any]) -> Path:
    """Write deterministic, human-readable JSON metadata."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(values, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination.resolve()


def write_footprint_geojson(raster_path: str | Path, output_path: str | Path) -> Path:
    """Write the raster bounds as a WGS84 GeoJSON polygon."""
    raster = Path(raster_path)
    with rasterio.open(raster) as dataset:
        if dataset.crs is None:
            raise ValueError(f"Cannot create a footprint without a CRS: {raster}")
        left, bottom, right, top = transform_bounds(
            dataset.crs, "EPSG:4326", *dataset.bounds, densify_pts=21
        )
    coordinates = [[[left, bottom], [right, bottom], [right, top], [left, top], [left, bottom]]]
    document = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"raster": raster.name},
                "geometry": {"type": "Polygon", "coordinates": coordinates},
            }
        ],
    }
    return write_metadata_report(output_path, document)
