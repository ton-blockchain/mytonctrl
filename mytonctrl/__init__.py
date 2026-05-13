try:
    from ._commit import __commit__
except ImportError:
    __commit__ = "unknown"
