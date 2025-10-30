# Comprehensive Pilot Settings Panel Implementation

## Overview
Created a unified, comprehensive settings dialog for all pilot system configuration, replacing the scattered UI elements across the main window and pilot widget.

## Key Features

### 1. **Unified Settings Dialog** (`pilot_settings.py`)
All pilot configuration in one place:
- MIDI device selection
- Deck region configuration
- MIDI action management
- Real-time MIDI monitor

### 2. **MIDI Device Selector Widget**
- Dropdown selector for each MIDI device:
  - **MIDI Clock**: Device for receiving clock sync
  - **LightSoftware In**: Output to lighting software
  - **LightSoftware Out**: Input from lighting software
- Refresh button to rescan devices
- Auto-selects devices matching keyword (e.g., "midiclock", "lightsoftware_in")
- Shows all available MIDI devices from system

### 3. **Deck Region Configuration**
- Visual status for all 4 decks (A, B, C, D)
- Shows current configuration status:
  - Green text with coordinates if configured
  - Gray "Not set" if not configured
- "Set Regions" button for each deck
- Opens overlay windows for positioning
- Status automatically refreshes after configuration

### 4. **MIDI Actions Management**
- List of all configured actions with details:
  - Action name
  - Action type (phrase_sync, etc.)
  - MIDI message (status byte, data1)
- "Learn New Action" button
- Delete button for each action
- Integrated MIDI learn dialog

### 5. **Real-time MIDI Monitor**
- Start/Stop monitoring button
- Displays incoming MIDI messages in real-time
- Shows message type, status byte, data1, data2
- Scrollable history (50 messages max)
- Automatically ignores clock messages (0xF8, etc.)
- Useful for debugging MIDI issues

## User Interface

### Settings Dialog Layout

```
┌─────────────────────────────────────┐
│     Pilot System Settings       [X] │
├─────────────────────────────────────┤
│ ┌─ MIDI Devices ─────────────────┐ │
│ │ MIDI Clock:        [device▾][⟳]│ │
│ │ LightSoftware In:  [device▾][⟳]│ │
│ │ LightSoftware Out: [device▾][⟳]│ │
│ └─────────────────────────────────┘ │
│                                     │
│ ┌─ Deck Capture Regions ─────────┐ │
│ │ Deck A  Button: (x, y)          │ │
│ │         Timeline: (x, y)  [Set] │ │
│ │ Deck B  Button: Not set         │ │
│ │         Timeline: Not set [Set] │ │
│ │ Deck C  Button: Not set         │ │
│ │         Timeline: Not set [Set] │ │
│ │ Deck D  Button: Not set         │ │
│ │         Timeline: Not set [Set] │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ┌─ MIDI Actions ─────────────────┐ │
│ │ Configured Actions:             │ │
│ │                 [Learn New]     │ │
│ │                                 │ │
│ │ Phrase Sync (0x90 60)      [🗑] │ │
│ │ ...                             │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ┌─ MIDI Monitor ─────────────────┐ │
│ │ MIDI Monitor    [Start]         │ │
│ │ ┌───────────────────────────┐   │ │
│ │ │ 0x90 (Note On) - Data1:60 │   │ │
│ │ │ 0xB0 (CC) - Data1:7       │   │ │
│ │ │ ...                       │   │ │
│ │ └───────────────────────────┘   │ │
│ └─────────────────────────────────┘ │
│                                     │
│                         [Close]     │
└─────────────────────────────────────┘
```

### Main Window Integration
- Settings button (gear icon) in pilot widget header
- Opens comprehensive settings dialog
- Dialog is non-modal (can stay open while using app)
- Auto-cleanup on close (stops MIDI monitoring)

## Usage Flow

### Initial Setup
1. Click gear icon in pilot widget
2. Settings dialog opens
3. Select MIDI devices from dropdowns
4. Configure deck regions:
   - Click "Set Regions" for each deck
   - Position overlay windows over DJ software
   - Press Enter to confirm
5. Add MIDI actions:
   - Click "Learn New Action"
   - Start learning
   - Press MIDI button on controller
   - Name and save action
6. Test with MIDI Monitor

### Testing MIDI Setup
1. Open settings dialog
2. Start MIDI Monitor
3. Press buttons on MIDI controller
4. Verify messages appear in monitor
5. Compare with expected MIDI messages for actions

### Troubleshooting
- **No MIDI devices shown**: Click refresh button (⟳)
- **MIDI not detected**: Check MIDI Monitor to see if messages arrive
- **Wrong device**: Select correct device from dropdown
- **Deck regions not working**: Verify positions with overlay windows

## Technical Details

### MIDI Device Detection
```python
# Scans all pygame MIDI devices
for i in range(pygame.midi.get_count()):
    info = pygame.midi.get_device_info(i)
    # Adds to dropdown
    # Auto-selects if name contains keyword
```

### Deck Region Status
- Reads from `config.json`
- Updates in real-time after configuration
- Shows coordinates for debugging

### MIDI Monitor Implementation
- Polls MIDI input every 50ms
- Filters out clock messages (0xF8, 0xFA, 0xFB, 0xFC)
- Displays message type name (Note On, CC, etc.)
- Scrollable history with auto-cleanup

### Dialog Lifecycle
- Non-modal (doesn't block main window)
- Cleanup on close:
  - Stops MIDI monitoring
  - Clears poll timer
  - Releases resources

## Files Modified/Created

### New Files
- **`lumiblox/gui/pilot_settings.py`**: Comprehensive settings dialog
  - `MidiDeviceSelector`: Device dropdown widget
  - `DeckRegionWidget`: Deck configuration status widget
  - `MidiMonitorWidget`: Real-time MIDI monitor
  - `MidiLearnDialog`: MIDI learning dialog (moved from pilot_widget)
  - `PilotSettingsDialog`: Main settings dialog

### Modified Files
- **`lumiblox/gui/pilot_widget.py`**:
  - Removed scattered MIDI actions UI
  - Removed deck configuration UI
  - Updated settings button to open new dialog
  - Simplified to focus on status display and presets

## Benefits

### User Experience
- **Everything in one place**: No more hunting for settings
- **Visual feedback**: See what's configured at a glance
- **MIDI debugging**: Monitor helps diagnose connection issues
- **Clear organization**: Grouped by function

### Maintainability
- **Single source**: All settings UI in one file
- **Modular widgets**: Reusable components
- **Consistent styling**: Uses app's style constants
- **Clean separation**: Settings vs. runtime display

### Discoverability
- **Clear labeling**: "MIDI Clock", "LightSoftware In/Out"
- **Status indicators**: Green for configured, gray for not set
- **Tooltips**: Helpful hints on buttons
- **Instructions**: MIDI learn dialog has step-by-step guide

## Future Enhancements

### Potential Additions
- **Device auto-reconnect**: Monitor and reconnect on disconnect
- **Device status indicators**: Show connected/disconnected state
- **Preset management**: Save/load device configurations
- **MIDI message templates**: Common patterns for learning
- **Advanced monitor filters**: Filter by message type, channel
- **Export MIDI log**: Save monitor history to file
- **Device info display**: Show device details (channels, etc.)

### Validation
- **Device testing**: Send test message button
- **Region preview**: Show captured image from deck regions
- **Action testing**: Trigger action manually
- **Configuration validation**: Warn about incomplete setups

## Summary

The new comprehensive settings dialog provides a professional, unified interface for all pilot system configuration. It addresses the confusion of scattered settings by bringing everything together in one well-organized dialog with clear visual feedback and real-time monitoring capabilities. The MIDI monitor is particularly valuable for debugging connection issues and verifying that messages are being received correctly.
