# Controller Layer – Agent Guide

## Scope
This directory orchestrates the runtime stack:
- `light_controller.py`: connects hardware (Launchpad, lighting software), handles input routing, manages `ProjectDataRepository`, and exposes callbacks to the GUI.
- `sequence_controller.py`: owns sequence playback, threading, and beat/bar timing. **Persists via `ProjectDataRepository`**.
- `scene_controller.py`, `led_controller.py`, `device_monitor.py`, etc. provide subsystem responsibilities.

## Key Concepts
- **Sequences**: Multi-step presets stored in `pilots.json` under each pilot. Use `SequenceController.save_sequence()` / `.activate_sequence()`; sequences persist automatically through the repository.
- **Pilots**: Each pilot contains its own sequences and automation rules. Switch pilots with `LightController.switch_pilot()`.
- **Threading**: Playback runs in a single background thread created via `_start_playback_thread_if_needed()`. When adding long-running logic, reuse the existing stop-event/condition variables rather than spawning extra threads.
- **Callbacks**: Controllers communicate via callback attributes (e.g., `SequenceController.on_step_change`). Guard user callbacks with try/except and keep them non-blocking.
- **Hardware Abstraction**: Device-related modules must route through `DeviceManager` + `DeviceMonitor` so the GUI receives state updates. No direct hardware calls from GUI helpers.

## Implementation Guidelines
- Keep controller modules pure Python (no PySide imports). They should be UI-agnostic and safe to run headless for tests.
- Prefer dataclasses + enums (see `SequenceStep`, `SequenceDurationUnit`, `PlaybackState`). Reuse existing ones instead of redefining.
- Whenever you change sequence semantics, add/adjust coverage in `tests/controller/test_sequence.py` and update docs mentioning storage format.
- Logging: use module-level loggers; avoid printing directly.
- When exposing new controller functionality to the GUI, surface it through `LightController` methods and set matching callbacks so hardware + GUI stay in sync.

## Quick Testing
- Run `python -m pytest tests/controller/test_sequence.py` after editing sequence or scene modules.
- For manual checks, `python run.py` (CLI) and `run_editor.bat` (GUI) should still initialize without hardware connected; handle missing devices gracefully.
