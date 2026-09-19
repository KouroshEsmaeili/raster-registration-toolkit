"""Typed RPC metadata and parsing for RPB-style satellite XML."""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .exceptions import RPCMetadataError

_SCALAR_FIELDS = {
    "LINE_OFF": "line_offset",
    "SAMP_OFF": "sample_offset",
    "LAT_OFF": "latitude_offset",
    "LONG_OFF": "longitude_offset",
    "HEIGHT_OFF": "height_offset",
    "LINE_SCALE": "line_scale",
    "SAMP_SCALE": "sample_scale",
    "LAT_SCALE": "latitude_scale",
    "LONG_SCALE": "longitude_scale",
    "HEIGHT_SCALE": "height_scale",
}

_XML_SCALAR_FIELDS = {
    "LINEOFFSET": "line_offset",
    "SAMPOFFSET": "sample_offset",
    "LATOFFSET": "latitude_offset",
    "LONGOFFSET": "longitude_offset",
    "HEIGHTOFFSET": "height_offset",
    "LINESCALE": "line_scale",
    "SAMPSCALE": "sample_scale",
    "LATSCALE": "latitude_scale",
    "LONGSCALE": "longitude_scale",
    "HEIGHTSCALE": "height_scale",
}

_COEFFICIENT_FIELDS = {
    "LINE_NUM_COEFF": "line_numerator",
    "LINE_DEN_COEFF": "line_denominator",
    "SAMP_NUM_COEFF": "sample_numerator",
    "SAMP_DEN_COEFF": "sample_denominator",
}

_XML_COEFFICIENT_FIELDS = {
    "LINENUMCOEF": "line_numerator",
    "LINEDENCOEF": "line_denominator",
    "SAMPNUMCOEF": "sample_numerator",
    "SAMPDENCOEF": "sample_denominator",
}


@dataclass(frozen=True, slots=True)
class RPCModel:
    """Vendor-neutral rational polynomial coefficient model."""

    line_offset: float
    sample_offset: float
    latitude_offset: float
    longitude_offset: float
    height_offset: float
    line_scale: float
    sample_scale: float
    latitude_scale: float
    longitude_scale: float
    height_scale: float
    line_numerator: tuple[float, ...]
    line_denominator: tuple[float, ...]
    sample_numerator: tuple[float, ...]
    sample_denominator: tuple[float, ...]

    def __post_init__(self) -> None:
        """Validate scalar values and the four 20-term polynomials."""
        scalar_values = (
            self.line_offset,
            self.sample_offset,
            self.latitude_offset,
            self.longitude_offset,
            self.height_offset,
            self.line_scale,
            self.sample_scale,
            self.latitude_scale,
            self.longitude_scale,
            self.height_scale,
        )
        if not all(math.isfinite(value) for value in scalar_values):
            raise RPCMetadataError("RPC offsets and scales must be finite numbers.")
        if any(
            value <= 0
            for value in (
                self.line_scale,
                self.sample_scale,
                self.latitude_scale,
                self.longitude_scale,
                self.height_scale,
            )
        ):
            raise RPCMetadataError("RPC scale values must be positive.")

        for name in (
            "line_numerator",
            "line_denominator",
            "sample_numerator",
            "sample_denominator",
        ):
            coefficients = getattr(self, name)
            if len(coefficients) != 20:
                raise RPCMetadataError(
                    f"RPC polynomial {name!r} must contain exactly 20 coefficients."
                )
            if not all(math.isfinite(value) for value in coefficients):
                raise RPCMetadataError(f"RPC polynomial {name!r} contains a non-finite value.")

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> RPCModel:
        """Create a model from standard GDAL RPC field names."""
        missing = [key for key in (*_SCALAR_FIELDS, *_COEFFICIENT_FIELDS) if key not in values]
        if missing:
            raise RPCMetadataError(f"Missing required RPC fields: {', '.join(missing)}")

        parsed: dict[str, object] = {}
        try:
            for rpc_name, field_name in _SCALAR_FIELDS.items():
                parsed[field_name] = float(values[rpc_name])
            for rpc_name, field_name in _COEFFICIENT_FIELDS.items():
                raw = values[rpc_name]
                if isinstance(raw, str):
                    items = raw.replace(",", " ").split()
                else:
                    items = list(raw)  # type: ignore[arg-type]
                parsed[field_name] = tuple(float(value) for value in items)
        except (TypeError, ValueError) as exc:
            raise RPCMetadataError(f"RPC metadata contains a non-numeric value: {exc}") from exc
        return cls(**parsed)  # type: ignore[arg-type]

    def to_gdal_metadata(self) -> dict[str, str]:
        """Return GDAL-compatible RPC metadata strings."""
        metadata: dict[str, str] = {}
        for rpc_name, field_name in _SCALAR_FIELDS.items():
            metadata[rpc_name] = format(getattr(self, field_name), ".17g")
        for rpc_name, field_name in _COEFFICIENT_FIELDS.items():
            metadata[rpc_name] = " ".join(
                format(value, ".17g") for value in getattr(self, field_name)
            )
        return metadata


@dataclass(frozen=True, slots=True)
class RPCDocument:
    """Parsed RPC model plus non-essential image metadata from its XML document."""

    rpc: RPCModel
    schema: str
    image_metadata: Mapping[str, str | float] = field(default_factory=dict)


def parse_rpc_xml(path: str | Path) -> RPCDocument:
    """Parse RPC metadata from an RPB/IMAGE XML document."""
    xml_path = Path(path).expanduser()
    if not xml_path.is_file():
        raise RPCMetadataError(f"RPC XML does not exist or is not a file: {xml_path}")
    try:
        root = ET.parse(xml_path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise RPCMetadataError(f"Could not parse RPC XML {xml_path}: {exc}") from exc
    return _parse_rpb_document(root)


def parse_rpc_xml_string(xml_text: str) -> RPCDocument:
    """Parse RPB/IMAGE XML text, primarily for deterministic tests."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise RPCMetadataError(f"Could not parse RPC XML text: {exc}") from exc
    return _parse_rpb_document(root)


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1].upper()


def _first_descendant(root: ET.Element, name: str) -> ET.Element | None:
    expected = name.upper()
    return next((element for element in root.iter() if _local_name(element) == expected), None)


def _first_child(root: ET.Element, name: str) -> ET.Element | None:
    expected = name.upper()
    return next((element for element in root if _local_name(element) == expected), None)


def _required_text(root: ET.Element, name: str) -> str:
    element = _first_descendant(root, name)
    if element is None or element.text is None or not element.text.strip():
        raise RPCMetadataError(f"Missing required RPC XML element: {name}")
    return element.text.strip()


def _parse_rpb_document(root: ET.Element) -> RPCDocument:
    rpb = _first_descendant(root, "RPB")
    if rpb is None:
        raise RPCMetadataError("RPC XML does not contain an RPB section.")
    image = _first_child(rpb, "IMAGE")
    if image is None:
        raise RPCMetadataError("RPC XML RPB section does not contain an IMAGE element.")

    model_values: dict[str, object] = {}
    for xml_name, field_name in _XML_SCALAR_FIELDS.items():
        try:
            model_values[field_name] = float(_required_text(image, xml_name))
        except ValueError as exc:
            raise RPCMetadataError(f"RPC XML element {xml_name} is not numeric.") from exc
    for xml_name, field_name in _XML_COEFFICIENT_FIELDS.items():
        raw = _required_text(image, xml_name).replace(",", " ").split()
        try:
            model_values[field_name] = tuple(float(value) for value in raw)
        except ValueError as exc:
            raise RPCMetadataError(
                f"RPC XML coefficient list {xml_name} contains a non-numeric value."
            ) from exc

    metadata: dict[str, str | float] = {}
    imd = _first_descendant(root, "IMD")
    if imd is not None:
        for name in (
            "NUMROWS",
            "NUMCOLUMNS",
            "ROWGSD",
            "COLGSD",
            "GENERATIONTIME",
            "PRODUCTORDERID",
            "IMAGEDESCRIPTOR",
            "BANDID",
            "PRODUCTLEVEL",
            "PRODUCTTYPE",
        ):
            element = _first_descendant(imd, name)
            if element is None or element.text is None:
                continue
            text = element.text.strip()
            if name in {"NUMROWS", "NUMCOLUMNS", "ROWGSD", "COLGSD"}:
                try:
                    metadata[name] = float(text)
                    continue
                except ValueError:
                    pass
            metadata[name] = text

    return RPCDocument(
        rpc=RPCModel(**model_values),  # type: ignore[arg-type]
        schema="RPB/IMAGE XML",
        image_metadata=metadata,
    )
