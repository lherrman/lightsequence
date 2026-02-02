# Lightsequence – Agent Guide

## Repository Purpose
- Hybrid hardware+software controller for light shows driven by MIDI, Launchpad MK2, and custom sequences.
- Core runtime lives in `lumiblox/controller`, GUI/editor tooling in `lumiblox/gui`, pilot/clock sync helpers in `lumiblox/pilot`.
- **Project data** (pilots with embedded sequences) stored in `pilots.json`, managed via `ProjectDataRepository`.

## Tooling & Environment
- Python 3.12 environment is managed through `uv`. Prefer `uv run` to execute tooling (e.g., `uv run python run.py`, `uv run pytest …`).
- Install or upgrade dependencies with `uv add <package>` so `pyproject.toml` stays in sync; avoid raw `pip install`.
- Entry points: `run.py` for CLI usage and `run_editor.bat` for the GUI/editor. Both should be launched via `uv run` when executing Python modules.

## Coding Standards
- Use type hints and dataclasses where practical. Maintain compatibility with Python 3.10+ syntax (no pattern matching assumptions beyond that).
- Keep threading explicit and guarded (see `SequenceController`). Avoid file-global state unless necessary.
- Logging via the stdlib `logging` module; default level is INFO. Prefer `logger.debug` for verbose traces.
- Respect existing config in `lumiblox/common/config.py`; never hard-code device IDs in controllers.

## Testing & Validation
- Unit tests currently focus on controller logic (`tests/controller/test_sequence.py`) and import smoke tests (`tests/test_imports.py`). Run `python -m pytest tests/controller/test_sequence.py tests/test_imports.py` before committing controller or packaging changes.
- GUI code lacks automated tests; when touching PySide6 widgets, smoke-test via `run_editor.bat` and document manual verification steps.

## Directory-Level Guides
- `lumiblox/controller/AGENTS.md` – orchestration layer guidance.
- `lumiblox/gui/AGENTS.md` – PySide6/Qt specifics.
- `tests/AGENTS.md` – expectations for new/updated tests.

Add new AGENT files when introducing major subsystems so other agents have localized context.
