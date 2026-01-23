# Tests – Agent Guide

## Philosophy
- Prefer **fast, deterministic** pytest tests. Avoid dependencies on hardware, MIDI devices, or GUI event loops.
- Focus coverage on pure-Python modules (controllers, utils). GUI layers should be tested indirectly by exercising controllers.

## Structure
- `tests/controller/test_sequence.py`: authoritative suite for `SequenceController` behavior (persistence, callbacks, threading, beat sync).
- `tests/test_imports.py`: smoke tests ensuring top-level modules import cleanly.

## Guidelines
- Keep tests hermetic by using `tmp_path`/`tmp_path_factory` for file IO. Do not read/write repo-level JSON fixtures directly.
- Use real classes instead of mocks where possible; when mocking, prefer `unittest.mock` or pytest monkeypatch fixtures.
- Every new controller feature should ship with regression tests in this directory.
- When you add a new subsystem, create a dedicated test module under `tests/<area>/` plus an AGENT file if the area is large.

## Commands
- Run targeted suites: `uv run pytest tests/controller/test_sequence.py`.
- Run smoke tests before committing: `uv run pytest tests/controller/test_sequence.py tests/test_imports.py`.
