import pytest

from rasterreg.exceptions import RPCMetadataError
from rasterreg.rpc import RPCModel, parse_rpc_xml_string


def _coefficients(start: int = 1) -> str:
    return " ".join(str(value) for value in range(start, start + 20))


def _rpc_xml(*, line_coefficients: str | None = None) -> str:
    line_values = line_coefficients or _coefficients()
    return f"""
    <isd>
      <IMD><NUMROWS>1000</NUMROWS><NUMCOLUMNS>2000</NUMCOLUMNS></IMD>
      <RPB>
        <IMAGE>
          <LINEOFFSET>500</LINEOFFSET><SAMPOFFSET>1000</SAMPOFFSET>
          <LATOFFSET>30.5</LATOFFSET><LONGOFFSET>52.25</LONGOFFSET>
          <HEIGHTOFFSET>1200</HEIGHTOFFSET>
          <LINESCALE>500</LINESCALE><SAMPSCALE>1000</SAMPSCALE>
          <LATSCALE>0.1</LATSCALE><LONGSCALE>0.2</LONGSCALE>
          <HEIGHTSCALE>800</HEIGHTSCALE>
          <LINENUMCOEFList><LINENUMCOEF>{line_values}</LINENUMCOEF></LINENUMCOEFList>
          <LINEDENCOEFList><LINEDENCOEF>{_coefficients(21)}</LINEDENCOEF></LINEDENCOEFList>
          <SAMPNUMCOEFList><SAMPNUMCOEF>{_coefficients(41)}</SAMPNUMCOEF></SAMPNUMCOEFList>
          <SAMPDENCOEFList><SAMPDENCOEF>{_coefficients(61)}</SAMPDENCOEF></SAMPDENCOEFList>
        </IMAGE>
      </RPB>
    </isd>
    """


def test_parse_rpb_xml_and_convert_to_gdal_metadata() -> None:
    document = parse_rpc_xml_string(_rpc_xml())

    assert document.rpc.latitude_offset == 30.5
    assert document.rpc.longitude_offset == 52.25
    assert document.rpc.line_numerator == tuple(float(value) for value in range(1, 21))
    assert document.image_metadata["NUMROWS"] == 1000.0

    gdal_metadata = document.rpc.to_gdal_metadata()
    assert gdal_metadata["LINE_OFF"] == "500"
    assert len(gdal_metadata["SAMP_DEN_COEFF"].split()) == 20


def test_rpc_rejects_missing_rpb_section() -> None:
    with pytest.raises(RPCMetadataError, match="RPB section"):
        parse_rpc_xml_string("<isd><IMD /></isd>")


def test_rpc_rejects_wrong_coefficient_count() -> None:
    with pytest.raises(RPCMetadataError, match="exactly 20"):
        parse_rpc_xml_string(_rpc_xml(line_coefficients="1 2 3"))


def test_rpc_mapping_requires_every_standard_field() -> None:
    with pytest.raises(RPCMetadataError, match="Missing required RPC fields"):
        RPCModel.from_mapping({"LINE_OFF": 1})
