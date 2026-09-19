import pytest
from rasterio.coords import BoundingBox
from rasterio.crs import CRS
from rasterio.transform import Affine

from rasterreg.exceptions import ImageValidationError
from rasterreg.geospatial import transform_for_bounds, validate_georeferencing


def test_transform_spans_reference_bounds() -> None:
    bounds = BoundingBox(left=10.0, bottom=20.0, right=14.0, top=26.0)

    transform = transform_for_bounds(bounds, width=8, height=6)

    assert transform == Affine(0.5, 0.0, 10.0, 0.0, -1.0, 26.0)


def test_reference_requires_a_crs() -> None:
    with pytest.raises(ImageValidationError, match="coordinate reference system"):
        validate_georeferencing(None, Affine.translation(10, 20))


def test_reference_rejects_identity_transform() -> None:
    with pytest.raises(ImageValidationError, match="identity"):
        validate_georeferencing(CRS.from_epsg(4326), Affine.identity())


@pytest.mark.parametrize(
    "transform",
    [
        Affine(1.0, 0.01, 10.0, 0.0, -1.0, 20.0),
        Affine(1.0, 0.0, 10.0, 0.01, -1.0, 20.0),
    ],
)
def test_reference_rejects_rotation_or_shear(transform: Affine) -> None:
    with pytest.raises(ImageValidationError, match="Rotated or sheared"):
        validate_georeferencing(CRS.from_epsg(4326), transform)


def test_reference_accepts_negligible_off_diagonal_terms() -> None:
    transform = Affine(1.0, 1e-13, 10.0, -1e-13, -1.0, 20.0)

    assert validate_georeferencing(CRS.from_epsg(4326), transform) == CRS.from_epsg(4326)
