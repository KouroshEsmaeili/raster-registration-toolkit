import pytest

from rasterreg.orthorectification import (
    OrthorectificationConfig,
    output_resolution,
)
from rasterreg.rpc import RPCModel


def _rpc() -> RPCModel:
    coefficients = tuple(float(index) for index in range(20))
    return RPCModel(
        line_offset=50,
        sample_offset=50,
        latitude_offset=0,
        longitude_offset=0,
        height_offset=100,
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


def test_projected_output_resolution_remains_in_meters() -> None:
    config = OrthorectificationConfig(output_crs="EPSG:3857", resolution_meters=12.5)

    assert output_resolution(config, _rpc()) == (12.5, 12.5)


def test_orthorectification_rejects_invalid_resolution() -> None:
    with pytest.raises(ValueError, match="positive finite"):
        OrthorectificationConfig(resolution_meters=0)
