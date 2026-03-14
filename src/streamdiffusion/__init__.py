__all__ = ["StreamDiffusion"]


def __getattr__(name: str):
    if name == "StreamDiffusion":
        from .pipeline import StreamDiffusion

        return StreamDiffusion

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
