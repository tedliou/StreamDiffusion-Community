# Distribution is git clone plus start.cmd

Users get the Runtime by cloning the repository and running `start.cmd`. The script checks the NVIDIA driver, installs uv if it is missing, runs `uv sync --frozen` (which fetches Python 3.12 and every wheel, CUDA runtime included), downloads model weights at pinned Hugging Face revisions, and starts the Runtime. Everything it downloads lives inside the clone (`models/`, `cache/`) or in uv's cache, so deleting the folder uninstalls it. Running it needs no CUDA Toolkit, Visual Studio, NDI Tools or Node.js.

## Considered Options

- PyPI package: rejected for now. Users would still need a CUDA-specific torch index and the model weights, so it is not simpler for them.
- Frozen executable (PyInstaller): rejected. It would be a multi-gigabyte bundle tied to one CUDA build and rebuilt for every dependency bump.
