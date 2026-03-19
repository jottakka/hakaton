"""BenchmarkControl Arcade MCP server package."""

__version__ = "0.2.0"


def __getattr__(name: str):
    if name == "workflow_entrypoint":
        import importlib

        return importlib.import_module(".workflow_entrypoint", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
