try:
    from ._version import __commit__, __version__
except ImportError:
    __commit__ = "unknown"
    __version__ = "unknown"

try:
    from . import _version

    __image_ref__ = getattr(_version, "__image_ref__", "")
except ImportError:
    __image_ref__ = ""
