import numpy as np
import pytest
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_bounds

from rasterreg.dem import validate_dem, validate_dem_for_rpc
from rasterreg.exceptions import DEMValidationError
from rasterreg.rpc import RPCModel

_DEFAULT_CRS = CRS.from_epsg(4326)


def _rpc(latitude: float = 30.0, longitude: float = 52.0) -> RPCModel:
    coefficients = tuple(float(index) for index in range(20))
    return RPCModel(
        line_offset=50,
        sample_offset=50,
        latitude_offset=latitude,
        longitude_offset=longitude,
        height_offset=1000,
        line_scale=50,
        sample_scale=50,
        latitude_scale=0.1,
        longitude_scale=0.1,
        height_scale=500,
        line_numerator=coefficients,
        line_denominator=coefficients,
        sample_numerator=coefficients,
        sample_denominator=coefficients,
    )


def _write_dem(path, *, crs: CRS | None = _DEFAULT_CRS) -> None:
    data = np.arange(100, dtype=np.float32).reshape(10, 10)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=10,
        height=10,
        count=1,
        dtype=data.dtype,
        crs=crs,
        transform=from_bounds(51.0, 29.0, 53.0, 31.0, 10, 10),
    ) as destination:
        destination.write(data, 1)


def test_validate_dem_reads_geospatial_metadata(tmp_path) -> None:
    path = tmp_path / "dem.tif"
    _write_dem(path)

    info = validate_dem(path)

    assert info.width == 10
    assert info.height == 10
    assert info.crs == CRS.from_epsg(4326)
    validate_dem_for_rpc(info, _rpc())


def test_validate_dem_rejects_missing_crs(tmp_path) -> None:
    path = tmp_path / "dem-without-crs.tif"
    _write_dem(path, crs=None)

    with pytest.raises(DEMValidationError, match="coordinate reference system"):
        validate_dem(path)


def test_validate_dem_rejects_scene_outside_bounds(tmp_path) -> None:
    path = tmp_path / "dem.tif"
    _write_dem(path)

    with pytest.raises(DEMValidationError, match="does not cover"):
        validate_dem_for_rpc(validate_dem(path), _rpc(latitude=10, longitude=10))
