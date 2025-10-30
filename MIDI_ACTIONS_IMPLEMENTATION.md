# MIDI Actions Implementation Summary

## Overview
Implemented a comprehensive configurable MIDI message action system that allows users to map arbitrary MIDI messages (from the MIDI clock device) to specific actions within the application. The first implemented action is "phrase sync" which aligns/syncs the phrase timing (equivalent to pressing the sync button in the GUI).

## Key Features

### 1. **Flexible MIDI Action System**
- Map any MIDI message (note on, note off, CC, program change, etc.) to actions
- Configurable status byte, data1, and data2 matching
- Extensible architecture for adding new action types in the future

### 2. **MIDI Learn Functionality**
- User-friendly "learn" mode in the GUI
- Automatically captures incoming MIDI messages
- Displays message details (status, data1, data2 in hex and decimal)
- User can name the action and select its type

### 3. **Phrase Sync Action**
- First implemented action type
- Triggers the phrase alignment/sync functionality
- Same behavior as clicking the "Align to Beat" button in the GUI
- Useful for synchronizing with specific cues in DJ software

### 4. **Persistent Configuration**
- MIDI actions are saved in `config.json`
- Loaded automatically on startup
- GUI provides management interface (add/delete actions)

## Architecture

### New Files Created

#### `lumiblox/pilot/midi_actions.py`
Core action system implementation:
- **`MidiActionType`**: Enum defining action types (PHRASE_SYNC, future: SEQUENCE_SWITCH, etc.)
- **`MidiActionConfig`**: Dataclass for action configuration
  - name: User-friendly name
  - action_type: Type of action to perform
  - status: MIDI status byte (e.g., 0x90 for note on)
  - data1: Optional first data byte (e.g., note number)
  - data2: Optional second data byte (e.g., velocity), None to ignore
  - parameters: Additional action-specific parameters
- **`MidiActionHandler`**: Manages action configurations and execution
  - Processes incoming MIDI messages
  - Matches messages against configured actions
  - Triggers appropriate callbacks

### Modified Files

#### `lumiblox/pilot/clock_sync.py`
- Added `MidiActionHandler` integration
- Processes MIDI messages through action handler
- Maintains backward compatibility with legacy `zero_signal` configuration
- Default phrase_sync callback automatically registered

#### `lumiblox/pilot/pilot_controller.py`
- Added methods to manage MIDI actions:
  - `add_midi_action(action)`
  - `remove_midi_action(name)`
  - `get_midi_actions()`
  - `clear_midi_actions()`
- Maintains legacy `configure_zero_signal()` for backward compatibility

#### `lumiblox/common/config.py`
- Added `midi_actions` array to config schema
- Methods to manage MIDI actions in config:
  - `get_midi_actions()`
  - `set_midi_actions(actions)`
  - `add_midi_action(action)`
  - `remove_midi_action(name)`
- Maintains backward compatibility with `zero_signal` config

#### `lumiblox/gui/pilot_widget.py`
- **New `MidiLearnDialog` class**:
  - Modal dialog for learning MIDI messages
  - "Start Learning" button to capture MIDI input
  - Real-time MIDI message display
  - Action naming and type selection
  - Save button to create the action
- **Updated `PilotWidget`**:
  - New "MIDI Actions" section in UI
  - Learn button to open MIDI learn dialog
  - List of configured actions with delete buttons
  - Visual display of action details (name, type, MIDI message)

#### `lumiblox/gui/main_window.py`
- Pass `pilot_controller` reference to `PilotWidget`
- Enables MIDI learn functionality to access MIDI input

#### `lumiblox/gui/controller_thread.py`
- Load MIDI actions from config on startup
- Configure actions on pilot controller
- Handle action errors gracefully

## Usage Guide

### Adding a MIDI Action

1. **Start the Pilot System**
   - Click the robot icon to start the pilot
   - Ensure MIDI clock device is connected

2. **Open MIDI Learn Dialog**
   - Click the WiFi icon (learn button) in the "MIDI Actions" section

3. **Learn MIDI Message**
   - Click "Start Learning"
   - Press a button/pad on your MIDI controller
   - The dialog will capture and display the MIDI message

4. **Configure Action**
   - Give the action a descriptive name (e.g., "Phrase Sync from Pad 1")
   - Select the action type (currently only "Phrase Sync" is available)
   - Click "Save"

5. **Action is Now Active**
   - The action appears in the MIDI Actions list
   - It's automatically saved to `config.json`
   - Pressing the same MIDI button will now trigger the action

### Deleting a MIDI Action

- Click the trash icon next to the action in the list
- Confirm deletion
- Action is removed from memory and config

## Configuration File Format

```json
{
  "pilot": {
    "midi_actions": [
      {
        "name": "Phrase Sync",
        "action_type": "phrase_sync",
        "status": 144,       // 0x90 = Note On
        "data1": 60,         // Middle C
        "data2": null,       // Ignore velocity (trigger on any)
        "parameters": {}
      }
    ]
  }
}
```

## Technical Details

### MIDI Message Matching

The system matches MIDI messages with a hierarchical approach:
1. **Status byte** must always match
2. **data1** is checked if specified (not null)
3. **data2** is checked if specified (not null)
4. Setting data1 or data2 to `null` means "ignore this byte" (match any value)

This allows for flexible matching:
- Match any Note On on channel 1: `status=0x90, data1=null, data2=null`
- Match specific note regardless of velocity: `status=0x90, data1=60, data2=null`
- Match specific note with specific velocity: `status=0x90, data1=60, data2=127`

### Action Execution

When a MIDI message matches an action:
1. `MidiActionHandler` detects the match
2. Calls the registered callback for that action type
3. For PHRASE_SYNC: calls `clock_sync.align_to_tap()`
4. This aligns the phrase timing to the nearest beat

### Extensibility

To add new action types:

1. **Add to `MidiActionType` enum**:
```python
class MidiActionType(str, Enum):
    PHRASE_SYNC = "phrase_sync"
    SEQUENCE_SWITCH = "sequence_switch"  # NEW
```

2. **Register callback in appropriate controller**:
```python
midi_action_handler.register_callback(
    MidiActionType.SEQUENCE_SWITCH,
    lambda action: self.switch_to_sequence(action.parameters["sequence"])
)
```

3. **Update GUI to allow selecting new action type**:
```python
self.action_type_combo.addItem("Switch Sequence", MidiActionType.SEQUENCE_SWITCH.value)
```

## Testing Recommendations

1. **MIDI Learn Functionality**
   - Test with various MIDI controllers (keyboard, pads, control surface)
   - Test different message types (note on, CC, program change)
   - Verify correct display of MIDI message details

2. **Phrase Sync Action**
   - Configure a phrase sync action
   - Start pilot and ensure it's aligned
   - Trigger the MIDI action
   - Verify phrase timing is re-aligned

3. **Configuration Persistence**
   - Add multiple MIDI actions
   - Restart the application
   - Verify actions are loaded correctly
   - Verify actions still work after reload

4. **Edge Cases**
   - Test with pilot not running (should show warning)
   - Test learning while MIDI clock messages are coming in (should ignore clock)
   - Test with invalid config data (should handle gracefully)

## Future Enhancements

### Potential New Action Types

1. **Sequence Switch** (`SEQUENCE_SWITCH`)
   - Switch to a specific sequence (x.y coordinates)
   - Parameters: `{"sequence": "1.2"}`

2. **Scene Toggle** (`SCENE_TOGGLE`)
   - Toggle a specific scene on/off
   - Parameters: `{"scene": [x, y]}`

3. **Tempo Tap** (`TEMPO_TAP`)
   - Tap tempo detection
   - No parameters needed

4. **BPM Override** (`BPM_OVERRIDE`)
   - Set a specific BPM
   - Parameters: `{"bpm": 128.0}`

### UI Enhancements

- Edit existing MIDI actions (currently must delete and recreate)
- Drag and drop reordering of actions
- Enable/disable actions without deleting
- Test action button (trigger without MIDI controller)
- Visual feedback when action is triggered (flash indicator)

### Advanced Features

- Action conditions (only trigger if already aligned, only on specific phrase types)
- Action sequences (trigger multiple actions in order)
- Delay/timing parameters (trigger after X beats/bars)
- MIDI output actions (send MIDI messages to other devices)

## Backward Compatibility

The implementation maintains full backward compatibility:
- Legacy `zero_signal` configuration still works
- Existing configurations load without modification
- Old and new systems can coexist

## Error Handling

- Invalid MIDI action configs are logged and skipped
- Missing pilot controller shows user-friendly warning
- Failed action execution is logged but doesn't crash the system
- MIDI learn ignores clock messages automatically

## Summary

This implementation provides a powerful, extensible system for mapping MIDI messages to application actions. The initial phrase sync action demonstrates the capability, and the architecture supports easy addition of new action types in the future. The MIDI learn functionality makes it accessible to users without requiring manual configuration file editing.
