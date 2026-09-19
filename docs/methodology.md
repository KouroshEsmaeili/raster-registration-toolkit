# Methodology

## Scope

Raster Registration Toolkit applies established local-feature registration to
geospatial raster export. Feature extraction, matching, affine estimation,
raster IO, geospatial metadata, configuration, and application interfaces are
implemented as separate reusable components.

## Feature images and multiband data

Rasterio loads every source band into a height × width × bands array. The first
three bands are independently percentile-normalized to 8-bit only for feature
detection. This prevents a 16-bit source from being truncated while leaving the
original values untouched for final warping. For grayscale inputs, the sole
band is normalized directly. Additional source bands, including a fourth
infrared band, bypass feature extraction but receive the same final affine
transform.

By default the source is rotated 180 degrees before both matching and warping.
The CLI permits 0, 90, 180, or 270 degree counter-clockwise rotations without
interpolation.

## Image pyramids

Large source and reference feature images are repeatedly reduced using
OpenCV's Gaussian `pyrDown` operation. The default maximum heights are 5,000
source pixels and 10,000 reference pixels. If an image uses `l` pyramid
levels, its coordinate scale is

```text
s = 1 / 2^l.
```

Different level counts allow the matcher to operate at roughly manageable
sizes even when source and reference resolutions differ.

## SIFT feature extraction

SIFT identifies scale- and rotation-aware local keypoints and assigns a
floating-point descriptor to each. Feature extraction runs on the downscaled
8-bit grayscale views. Registration stops with an informative error when
either image yields fewer than three usable descriptors.

## Descriptor matching and filtering

A brute-force L2 matcher obtains the two nearest reference descriptors for
each source descriptor. A candidate `(m, n)` passes the ratio test when

```text
distance(m) < 0.8 × distance(n).
```

The implementation then retains matches strictly between the 20th and 80th
percentiles of the accepted match distances. This configurable heuristic
removes both very low- and high-distance matches and may require tuning for
imagery with different feature distributions.

## Affine model and RANSAC

Matched source points `(x, y)` map to reference points `(x', y')` with a
six-parameter affine model:

```text
[x']   [a b tx] [x]
[y'] = [c d ty] [y]
                 [1]
```

OpenCV's `estimateAffine2D` estimates these parameters with RANSAC. RANSAC
repeatedly proposes a model from minimal subsets, measures reprojection error,
and identifies a consensus set, reducing the influence of mismatches. The
result records both the post-filter match count and RANSAC inlier count.

## Mapping to the full-resolution canvas

Let `s_source` and `s_reference` be the pyramid scales. The output coordinate
convention keeps the affine matrix's 2 × 2 linear component, divides
translation by `s_source`, and uses canvas dimensions

```text
reference dimensions × (s_reference / s_source).
```

That convention is isolated in `scale_affine_to_full_resolution` and covered by
a deterministic unit test, making the coordinate behavior explicit and
maintainable.

The pipeline does not add geometry-derived padding after warping. The output
canvas therefore retains a direct relationship with the geographic bounds
assigned to the output raster.

## Raster georeferencing

The reference raster must provide a CRS, valid bounds, and a non-identity,
north-up affine transform. Under Rasterio's affine convention, the `b` and `d`
terms encode rotation or shear. The pipeline accepts them only within a small
numerical tolerance of zero and otherwise raises `ImageValidationError`; it
does not silently flatten rotated grids.

For a supported reference, the output grid spans its axis-aligned bounds. Its
pixel transform is constructed as

```text
x_resolution = (right - left) / output_width
y_resolution = (bottom - top) / output_height
```

with the origin at `(left, top)`. This retains the north-up negative y pixel
size produced by Rasterio's `from_bounds`. The CRS is copied from the reference
raster rather than being hard-coded to a specific CRS.

## GeoTIFF and multiband preservation

The full-resolution affine transform is applied once to the original rotated
source array, so every band uses identical interpolation and geometry. Rasterio
writes the band-last result as a LZW-compressed GeoTIFF without converting the
source dtype. Optional alpha generation marks pixels where any warped source
band is nonzero. Because black can be valid imagery, that mask is only an
explicit compatibility option and is not enabled by default.

## Configuration considerations

Source orientation, pyramid limits, matching thresholds, band ordering, and
reference-raster coverage depend on the imagery being processed. Quantitative
deployments should measure registration error against independent ground-control
points and tune the configuration for their sensors and scene types.

## References

1. Lowe, D. G. (2004). Distinctive image features from scale-invariant
   keypoints. *International Journal of Computer Vision, 60*, 91–110.
   <https://doi.org/10.1023/B:VISI.0000029664.99615.94>
2. Fischler, M. A., & Bolles, R. C. (1981). Random sample consensus: A paradigm
   for model fitting with applications to image analysis and automated
   cartography. *Communications of the ACM, 24*(6), 381–395.
   <https://doi.org/10.1145/358669.358692>

OpenCV supplies the SIFT, descriptor-matching, affine-estimation, and warping
implementations. Rasterio supplies raster IO, CRS metadata, bounds, and affine
transform utilities. These libraries are implementation dependencies rather
than methodological contributions of this project.
