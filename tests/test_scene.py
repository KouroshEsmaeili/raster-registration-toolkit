import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from rasterreg.exceptions import SceneDiscoveryError
from rasterreg.scene import SceneOverrides, discover_scene


def _raster(path, width: int, height: int, count: int) -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=count,
        dtype="uint8",
        crs="EPSG:4326",
        transform=from_origin(0, 1, 0.01, 0.01),
    ) as destination:
        destination.write(np.zeros((count, height, width), dtype=np.uint8))


def test_discover_scene_prefers_multiband_primary_and_matching_xml(tmp_path) -> None:
    primary = tmp_path / "scene_psh.tif"
    pan = tmp_path / "scene_pan.tif"
    _raster(primary, 40, 30, 4)
    _raster(pan, 80, 60, 1)
    (tmp_path / "scene_psh.xml").write_text("<isd />")
    (tmp_path / "scene_pan.xml").write_text("<isd />")

    scene = discover_scene(tmp_path)

    assert scene.image == primary
    assert scene.rpc == tmp_path / "scene_psh.xml"
    assert scene.panchromatic_image == pan
    assert scene.panchromatic_rpc == tmp_path / "scene_pan.xml"


def test_discover_scene_explicit_overrides_take_precedence(tmp_path) -> None:
    first = tmp_path / "first.tif"
    second = tmp_path / "second.tif"
    rpc = tmp_path / "custom.xml"
    _raster(first, 10, 10, 3)
    _raster(second, 20, 20, 3)
    rpc.write_text("<isd />")

    scene = discover_scene(tmp_path, SceneOverrides(image=first, rpc=rpc))

    assert scene.image == first
    assert scene.rpc == rpc


def test_discover_scene_rejects_equal_primary_candidates(tmp_path) -> None:
    _raster(tmp_path / "a.tif", 10, 10, 3)
    _raster(tmp_path / "b.tif", 10, 10, 3)
    (tmp_path / "a.xml").write_text("<isd />")
    (tmp_path / "b.xml").write_text("<isd />")

    with pytest.raises(SceneDiscoveryError, match="Ambiguous primary"):
        discover_scene(tmp_path)
