import pytest

from rasterreg.config import RegistrationConfig


def test_default_configuration_uses_expected_rotation_and_ratio() -> None:
    config = RegistrationConfig()

    assert config.source_rotation_degrees == 180
    assert config.ratio_threshold == 0.8
    assert (config.distance_percentile_low, config.distance_percentile_high) == (20.0, 80.0)
    assert config.overwrite is False


@pytest.mark.parametrize("rotation", [-90, 45, 360])
def test_rejects_non_quarter_turn_rotation(rotation: int) -> None:
    with pytest.raises(ValueError, match="source_rotation_degrees"):
        RegistrationConfig(source_rotation_degrees=rotation)


def test_rejects_reversed_percentiles() -> None:
    with pytest.raises(ValueError, match="percentiles"):
        RegistrationConfig(distance_percentile_low=80, distance_percentile_high=20)
