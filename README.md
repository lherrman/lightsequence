# LightSequence

A Python-based lighting controller for DasLight systems with Launchpad MK2 hardware integration.

## Features

- **Hardware Integration**: Control DasLight via MIDI with Launchpad MK2 as physical interface
- **Sequence Management**: Create, save, and playback lighting sequences with precise timing
- **Preset System**: Store and recall lighting presets instantly
- **Background Animation**: Automated background lighting effects
- **GUI Configuration**: User-friendly interface for sequence editing and management
- **Real-time Control**: Live lighting control with visual feedback

Only tested on Windows with DasLight and Launchpad MK2. Easily adaptable to other Launchpad models or Lighting software.

## Quick Start

### Requirements
- Python 3.12+
- DasLight software
- Launchpad MK2 (optional but recommended)
- loopMIDI (for MIDI communication)

### Installation

```bash
# Clone the repository
git clone https://github.com/lherrman/lightsequence.git
cd lightsequence

# run
uv run run.py
```

### Usage

**GUI Mode (Recommended):**
```bash
uv run run.py --mode gui
```

**Controller Mode (Standalone):**
```bash
uv run run.py --mode controller
```

**Quick Launch:**
- Windows: Run `src/run_editor.bat` (GUI) or `src/run.bat` (controller)

## Setup

1. Connect Launchpad MK2 via USB
2. Install and configure loopMIDI with ports named "DasLight_in" and "DasLight_out"
3. Configure DasLight to receive MIDI input and output on these ports
4. Configure at least one Scene that feedbacks MIDI NOTE_ON on channel 1 Number 127 (Ping Scene)
5. Launch the application
6. Configure MIDI feedback in DasLight for the buttons you want to use



Open source - feel free to use and modify for your lighting projects.