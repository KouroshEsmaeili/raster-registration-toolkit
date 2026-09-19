"""Domain-specific exceptions raised by the georeferencing pipeline."""


class GeoreferencerError(RuntimeError):
    """Base exception for expected rasterreg failures."""


class ImageValidationError(GeoreferencerError):
    """Raised when an input image cannot be used by the pipeline."""


class RegistrationError(GeoreferencerError):
    """Raised when image registration cannot produce an affine transform."""


class RPCMetadataError(GeoreferencerError):
    """Raised when RPC metadata is missing, malformed, or incomplete."""


class DEMValidationError(GeoreferencerError):
    """Raised when a DEM cannot support the requested scene workflow."""


class OrthorectificationError(GeoreferencerError):
    """Raised when GDAL cannot perform RPC orthorectification."""


class SceneDiscoveryError(GeoreferencerError):
    """Raised when satellite scene inputs are missing or ambiguous."""
