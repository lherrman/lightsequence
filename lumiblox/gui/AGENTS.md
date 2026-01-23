# GUI Layer – Agent Guide

## Stack
- Built with PySide6 (Qt6). Widgets live in this folder and are composed in `gui.py` / `main_window.py`.
- `controller_thread.py` embeds the `LightController` runtime in a `QThread` so the UI thread stays free.
- Editor widgets (sequence, pilot, device status) dispatch events back to controllers via signals or the shared `LightController` instance.

## Design Principles
- **Threading**: Never touch controller objects directly from background threads except via the existing `ControllerThread`. Communicate with the GUI using Qt signals (`Signal`) and slots; avoid calling QWidget APIs from non-GUI threads.
- **State Sources**: Treat `LightController` as the single source of truth for playback/sequence state. UI widgets should call its methods or go through `controller_thread.controller`.
- **Responsiveness**: Heavy operations (file IO, sequence saves) should happen via controller methods or worker threads, not on the main Qt loop.
- **Styling**: Keep layout/styling logic encapsulated within widgets to prevent global side effects. No direct hardware calls here.

## When Editing
- Respect the signal/slot wiring already in place (e.g., `playback_state_changed_signal`). Add new signals instead of polling.
- Guard optional controller attributes – GUI can boot in simulation mode with missing hardware, so always check `if self.controller` before calling.
- After UI changes, run `run_editor.bat` for a manual smoke test.

## Testing
- There are no automated GUI tests yet. Document manual verification steps in PR descriptions, especially for new dialogs or shortcuts.
