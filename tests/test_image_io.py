import numpy as np

from rasterreg.image_io import add_alpha_from_valid_pixels, feature_image


def test_feature_image_normalizes_first_three_bands_without_mutating_source() -> None:
    source = np.arange(4 * 4 * 4, dtype=np.uint16).reshape(4, 4, 4)
    original = source.copy()

    result = feature_image(source)

    assert result.shape == (4, 4, 3)
    assert result.dtype == np.uint8
    np.testing.assert_array_equal(source, original)


def test_alpha_mask_uses_native_integer_range() -> None:
    image = np.zeros((2, 2, 3), dtype=np.uint16)
    image[0, 1, 2] = 7

    result = add_alpha_from_valid_pixels(image)

    assert result.shape == (2, 2, 4)
    assert result[0, 0, 3] == 0
    assert result[0, 1, 3] == np.iinfo(np.uint16).max
