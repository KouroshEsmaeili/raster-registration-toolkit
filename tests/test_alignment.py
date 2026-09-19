import numpy as np

from rasterreg.alignment import pyramid_levels, scale_affine_to_full_resolution


def test_pyramid_levels_halves_until_height_is_within_limit() -> None:
    assert pyramid_levels(5_000, 5_000) == 0
    assert pyramid_levels(20_001, 5_000) == 2
    assert pyramid_levels(40_001, 5_000) == 3


def test_full_resolution_scaling_preserves_historical_coordinate_convention() -> None:
    downscaled = np.array([[1.1, 0.2, 12.0], [-0.1, 0.9, -8.0]])

    matrix, output_size = scale_affine_to_full_resolution(
        downscaled,
        source_levels=2,
        reference_levels=1,
        reference_shape=(1_000, 2_000, 3),
    )

    np.testing.assert_allclose(matrix[:, :2], downscaled[:, :2])
    np.testing.assert_allclose(matrix[:, 2], [48.0, -32.0])
    assert output_size == (4_000, 2_000)
