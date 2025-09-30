# Light Controller

Professional party lighting controller for Novation Launchpad MK2.

## Features

- **Hardware Control**: Direct integration with Novation Launchpad MK2
- **Scene Management**: Create and organize lighting scenes  
- **Preset Playlists**: Build cycling sequences of scenes
- **MIDI Integration**: Send lighting commands to DasLight4
- **Modern GUI**: Dark-themed interface for live control
- **Production Ready**: Clean architecture, minimal dependencies

## Quick Start

```bash
# Run the GUI
uv run run.py

# Or install and run
uv install
lightcontroller-gui
```

## Hardware Setup

1. Connect Novation Launchpad MK2 via USB
2. Install DasLight4 lighting software (optional)
3. Configure scenes using the GUI
4. Create presets and start controlling!

## Architecture

```
src/lightcontroller/
├── config.py      # YAML configuration management
├── controller.py  # Main lighting controller  
├── gui.py         # PySide6 interface
├── midi.py        # MIDI note mapping
└── simulator.py   # Hardware simulation
```

Total: **~500 lines** of clean, production-ready code.

## MIDI Mapping

The controller uses the correct Launchpad MK2 mapping:
- **8x8 Grid**: Notes 11-88 (verified with hardware)
- **Preset Buttons**: Right column, notes 89-96
- **Scene Feedback**: Automatic button lighting

## Usage

1. **Start System**: Click START to initialize MIDI
2. **Create Scenes**: Each scene maps to a grid button
3. **Build Presets**: Combine scenes into cycling playlists  
4. **Live Control**: Press preset buttons to activate sequences
5. **Emergency**: BLACKOUT button stops everything

Scenes are sent to DasLight4, presets handled in Python for maximum performance.