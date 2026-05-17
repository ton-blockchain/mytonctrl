try:
    from ._version import __commit__, __version__
except ImportError:
    __commit__ = "unknown"
    __version__ = "unknown"
