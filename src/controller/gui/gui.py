"""
Modern web-based GUI for Light Sequence Controller using Reflex.
Provides a clean, responsive interface for controlling lighting scenes and sequences.
"""

import logging
import threading
import typing as t
from datetime import datetime
import sys
import os

# Add the parent controller directory to the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import reflex as rx

from main import LightController
from sequence_manager import SequenceStep, SequenceState
from enums import AppState

logger = logging.getLogger(__name__)

# Global controller instance (not serializable, so can't be in state)
_controller: t.Optional[LightController] = None

def get_controller() -> t.Optional[LightController]:
    """Get the global controller instance."""
    return _controller_instance

def set_controller(controller: t.Optional[LightController]) -> None:
    """Set the global controller instance."""
    global _controller_instance
    _controller_instance = controller

# Color constants for modern dark theme
COLORS = {
    "bg": "#0d1117",          # GitHub dark background
    "surface": "#161b22",      # Slightly lighter surface
    "border": "#30363d",       # Border color
    "text": "#f0f6fc",         # Primary text
    "text_muted": "#8b949e",   # Muted text
    "accent": "#238636",       # Green accent
    "warning": "#d29922",      # Amber warning
    "error": "#f85149",        # Red error
    "scene_active": "#58a6ff", # Blue for active scenes
    "scene_inactive": "#21262d", # Dark for inactive scenes
    "preset_active": "#238636", # Green for active presets
    "preset_inactive": "#30363d", # Gray for inactive presets
}

class LightControllerState(rx.State):
    """Main application state for the Light Controller GUI."""
    
    # Connection status
    is_connected: bool = False
    connection_status: str = "Disconnected"
    
    # Scene grid state (8x5 grid) - using lists instead of sets for serialization
    active_scenes: list[str] = []  # Store as "x,y" strings
    
    # Preset state (8x2 grid)
    active_preset: str = ""  # Store as "x,y" string
    preset_grid: dict[str, bool] = {}  # Store as {"x,y": bool}
    
    # Sequence state
    sequence_state: str = SequenceState.STOPPED.value
    current_sequence_preset: str = ""  # Store as "x,y" string
    current_step_info: dict[str, str] = {}  # Only string values for serialization
    
    # App state
    app_state: str = AppState.NORMAL.value
    is_simulation: bool = False
    
    # Sequence editor state
    show_sequence_editor: bool = False
    editing_preset: str = ""  # Store as "x,y" string
    sequence_steps_count: int = 0  # Just store count, not actual steps
    selected_step_index: int = -1
    
    # UI state
    last_update: str = ""
    status_message: str = "Ready"
    
    def __init__(self):
        super().__init__()
        # Initialize preset grid with string keys
        self.preset_grid = {f"{x},{y}": False for x in range(8) for y in range(2)}
    
    def initialize_controller(self, simulation: bool = False):
        """Initialize the light controller in a background thread."""
        self.is_simulation = simulation
        self.status_message = "Initializing controller..."
        
        try:
            # Initialize controller in background
            self._init_controller_async(simulation)
            self.is_connected = True
            self.connection_status = "Connected (Simulation)" if simulation else "Connected"
            self.status_message = "Controller ready"
            self._sync_state_with_controller()
        except Exception as e:
            logger.error(f"Failed to initialize controller: {e}")
            self.is_connected = False
            self.connection_status = f"Error: {str(e)}"
            self.status_message = f"Initialization failed: {str(e)}"
    
    def _init_controller_async(self, simulation: bool):
        """Initialize controller asynchronously."""
        def init_controller():
            controller = LightController(simulation=simulation)
            if hasattr(controller, 'initialize_hardware_connections'):
                controller.initialize_hardware_connections()
            set_controller(controller)
        
        # Run in thread to avoid blocking UI
        thread = threading.Thread(target=init_controller, daemon=True)
        thread.start()
        thread.join(timeout=10)  # 10 second timeout
        
        if not get_controller():
            raise Exception("Controller initialization timed out")
    
    def _sync_state_with_controller(self):
        """Sync GUI state with controller state."""
        controller = get_controller()
        if not controller:
            return
            
        # Sync active scenes - convert to string list
        self.active_scenes = [f"{x},{y}" for x, y in controller.currently_active_scenes]
        
        # Sync active preset - convert to string
        if controller.currently_active_preset:
            self.active_preset = f"{controller.currently_active_preset[0]},{controller.currently_active_preset[1]}"
        else:
            self.active_preset = ""
        
        # Sync preset grid (check which presets have data)
        for x in range(8):
            for y in range(2):
                preset_coords = [x, y]
                has_preset = controller.preset_manager.has_preset(preset_coords)
                self.preset_grid[f"{x},{y}"] = has_preset
        
        # Sync sequence state
        if hasattr(controller.sequence_manager, 'sequence_state'):
            self.sequence_state = controller.sequence_manager.sequence_state.value
        
        self.last_update = datetime.now().strftime("%H:%M:%S")
    
    def toggle_scene(self, x: int, y: int):
        """Toggle a scene on/off."""
        scene_str = f"{x},{y}"
        if scene_str in self.active_scenes:
            self.active_scenes.remove(scene_str)
        else:
            self.active_scenes.append(scene_str)
        
        # Send to controller if connected
        controller = get_controller()
        if controller:
            controller._route_button_event_to_handler({
                "type": "scene",
                "index": [x, y],
                "active": True
            })
        
        self.last_update = datetime.now().strftime("%H:%M:%S")
    
    def select_preset(self, x: int, y: int):
        """Select a preset."""
        preset_str = f"{x},{y}"
        
        if self.active_preset == preset_str:
            # Deactivate current preset
            self.active_preset = ""
            self.active_scenes = []
        else:
            # Activate new preset
            self.active_preset = preset_str
        
        # Send to controller if connected
        controller = get_controller()
        if controller:
            controller._route_button_event_to_handler({
                "type": "preset",
                "index": [x, y],
                "active": True
            })
        
        self._sync_state_with_controller()
    
    def save_current_scenes_to_preset(self, x: int, y: int):
        """Save current active scenes to a preset."""
        controller = get_controller()
        if not controller:
            self.status_message = "Controller not connected"
            return
            
        preset_coords = [x, y]
        # Convert string scenes back to coordinates
        scene_list = []
        for scene_str in self.active_scenes:
            sx, sy = map(int, scene_str.split(','))
            scene_list.append([sx, sy])
        
        controller.preset_manager.save_preset(preset_coords, scene_list)
        self.preset_grid[f"{x},{y}"] = True
        self.status_message = f"Saved {len(scene_list)} scenes to preset [{x}, {y}]"
        
        # Activate the preset we just saved
        self.select_preset(x, y)
    
    def toggle_sequence_playback(self):
        """Toggle sequence playback."""
        controller = get_controller()
        if not controller:
            return
            
        controller._toggle_sequence_playback()
        self._sync_state_with_controller()
    
    def next_sequence_step(self):
        """Advance to next sequence step."""
        controller = get_controller()
        if not controller:
            return
            
        controller._advance_to_next_sequence_step()
        self._sync_state_with_controller()
    
    def open_sequence_editor(self, x: int, y: int):
        """Open sequence editor for a preset."""
        self.editing_preset = f"{x},{y}"
        self.show_sequence_editor = True
        
        # Load existing sequence if any
        controller = get_controller()
        if controller:
            preset_coords = (x, y)
            sequence = controller.sequence_manager.get_sequence(preset_coords)
            if sequence:
                self.sequence_steps_count = len(sequence)
            else:
                self.sequence_steps_count = 0
        else:
            self.sequence_steps_count = 0
    
    def close_sequence_editor(self):
        """Close sequence editor."""
        self.show_sequence_editor = False
        self.editing_preset = ""
        self.sequence_steps_count = 0
        self.selected_step_index = -1
    
    def add_sequence_step(self):
        """Add a new sequence step."""
        controller = get_controller()
        if not controller or not self.editing_preset:
            return
        
        # Convert string coordinates back to tuples for SequenceStep
        active_scene_tuples = set()
        for coord_str in self.active_scenes:
            x, y = map(int, coord_str.split(','))
            active_scene_tuples.add((x, y))
        
        new_step = SequenceStep(
            scenes=active_scene_tuples,
            duration=2.0,
            name=f"Step {self.sequence_steps_count + 1}"
        )
        
        # Add to controller's sequence
        x, y = map(int, self.editing_preset.split(','))
        preset_coords = (x, y)
        sequence = controller.sequence_manager.get_sequence(preset_coords) or []
        sequence.append(new_step)
        controller.sequence_manager.set_sequence(preset_coords, sequence)
        self.sequence_steps_count = len(sequence)
    
    def remove_sequence_step(self, index: int):
        """Remove a sequence step."""
        controller = get_controller()
        if not controller or not self.editing_preset:
            return
            
        x, y = map(int, self.editing_preset.split(','))
        preset_coords = (x, y)
        sequence = controller.sequence_manager.get_sequence(preset_coords) or []
        
        if 0 <= index < len(sequence):
            sequence.pop(index)
            controller.sequence_manager.set_sequence(preset_coords, sequence)
            self.sequence_steps_count = len(sequence)
    
    def save_sequence(self):
        """Save the current sequence."""
        # Sequence is already saved in real-time
        self.status_message = f"Saved sequence with {self.sequence_steps_count} steps"
        self.close_sequence_editor()
    
    def clear_all_scenes(self):
        """Clear all active scenes."""
        self.active_scenes.clear()
        if self.controller:
            # Clear scenes in controller too
            self.controller._clear_all_scene_button_leds()
    
    def enter_save_mode(self):
        """Enter save mode."""
        self.app_state = AppState.SAVE_MODE.value
        self.status_message = "Save mode - select a preset to save current scenes"
    
    def exit_save_mode(self):
        """Exit save mode."""
        self.app_state = AppState.NORMAL.value
        self.status_message = "Ready"


def scene_button(x: int, y: int) -> rx.Component:
    """Create a scene button for the grid."""
    coord_str = f"{x},{y}"
    is_active = coord_str in LightControllerState.active_scenes
    
    return rx.button(
        f"{x},{y}",
        on_click=LightControllerState.toggle_scene(x, y),
        bg=rx.cond(is_active, COLORS["scene_active"], COLORS["scene_inactive"]),
        color=COLORS["text"],
        border=f"1px solid {COLORS['border']}",
        border_radius="4px",
        _hover={"bg": rx.cond(is_active, "#4184e4", "#30363d")},
        transition="all 0.2s",
        min_height="40px",
        font_size="12px",
        font_weight="500",
    )


def preset_button(x: int, y: int) -> rx.Component:
    """Create a preset button."""
    coord_str = f"{x},{y}"
    is_active = LightControllerState.active_preset == coord_str
    has_preset = LightControllerState.preset_grid[coord_str]
    
    # Button text shows preset coordinate and status
    button_text = rx.cond(
        has_preset,
        f"[{x},{y}] ●",  # Dot indicates preset has data
        f"[{x},{y}]"
    )
    
    return rx.hstack(
        rx.button(
            button_text,
            on_click=LightControllerState.select_preset(x, y),
            bg=rx.cond(
                is_active,
                COLORS["preset_active"],
                rx.cond(has_preset, COLORS["border"], COLORS["preset_inactive"])
            ),
            color=COLORS["text"],
            border=f"1px solid {COLORS['border']}",
            border_radius="4px",
            _hover={"bg": rx.cond(is_active, "#1f6f32", "#40464d")},
            transition="all 0.2s",
            flex="1",
            min_height="36px",
            font_size="12px",
            font_weight="500",
        ),
        rx.button(
            "SEQ",
            on_click=LightControllerState.open_sequence_editor(x, y),
            bg=COLORS["warning"],
            color=COLORS["text"],
            border=f"1px solid {COLORS['border']}",
            border_radius="4px",
            _hover={"bg": "#bb8a1f"},
            transition="all 0.2s",
            min_height="36px",
            font_size="10px",
            font_weight="500",
            px="8px",
        ),
        spacing="4px",
    )


def scene_grid() -> rx.Component:
    """Create the 8x5 scene grid."""
    return rx.box(
        rx.heading("Scenes", size="md", color=COLORS["text"], mb="12px"),
        rx.grid(
            *[
                scene_button(x, y)
                for y in range(5)
                for x in range(8)
            ],
            columns="8",
            gap="8px",
        ),
        bg=COLORS["surface"],
        border=f"1px solid {COLORS['border']}",
        border_radius="8px",
        p="16px",
    )


def preset_grid() -> rx.Component:
    """Create the 8x2 preset grid."""
    return rx.box(
        rx.heading("Presets", size="md", color=COLORS["text"], mb="12px"),
        rx.grid(
            *[
                preset_button(x, y)
                for y in range(2)
                for x in range(8)
            ],
            columns="8",
            gap="8px",
        ),
        bg=COLORS["surface"],
        border=f"1px solid {COLORS['border']}",
        border_radius="8px",
        p="16px",
    )


def control_panel() -> rx.Component:
    """Create the control panel with playback controls."""
    return rx.box(
        rx.heading("Controls", size="md", color=COLORS["text"], mb="12px"),
        rx.vstack(
            # Playback controls
            rx.hstack(
                rx.button(
                    rx.cond(
                        LightControllerState.sequence_state == "playing",
                        "⏸ Pause",
                        "▶ Play"
                    ),
                    on_click=LightControllerState.toggle_sequence_playback,
                    bg=COLORS["accent"],
                    color=COLORS["text"],
                    border_radius="6px",
                    _hover={"bg": "#1f6f32"},
                    transition="all 0.2s",
                    flex="1",
                ),
                rx.button(
                    "⏭ Next",
                    on_click=LightControllerState.next_sequence_step,
                    bg=COLORS["border"],
                    color=COLORS["text"],
                    border_radius="6px",
                    _hover={"bg": "#40464d"},
                    transition="all 0.2s",
                    flex="1",
                ),
                spacing="8px",
                width="100%",
            ),
            
            # Scene controls
            rx.hstack(
                rx.button(
                    "Clear All",
                    on_click=LightControllerState.clear_all_scenes,
                    bg=COLORS["error"],
                    color=COLORS["text"],
                    border_radius="6px",
                    _hover={"bg": "#d73648"},
                    transition="all 0.2s",
                    flex="1",
                ),
                rx.button(
                    rx.cond(
                        LightControllerState.app_state == "save_mode",
                        "Exit Save",
                        "Save Mode"
                    ),
                    on_click=rx.cond(
                        LightControllerState.app_state == "save_mode",
                        LightControllerState.exit_save_mode,
                        LightControllerState.enter_save_mode
                    ),
                    bg=rx.cond(
                        LightControllerState.app_state == "save_mode",
                        COLORS["warning"],
                        COLORS["accent"]
                    ),
                    color=COLORS["text"],
                    border_radius="6px",
                    _hover={"bg": rx.cond(
                        LightControllerState.app_state == "save_mode",
                        "#bb8a1f",
                        "#1f6f32"
                    )},
                    transition="all 0.2s",
                    flex="1",
                ),
                spacing="8px",
                width="100%",
            ),
            
            spacing="12px",
            width="100%",
        ),
        bg=COLORS["surface"],
        border=f"1px solid {COLORS['border']}",
        border_radius="8px",
        p="16px",
    )


def status_panel() -> rx.Component:
    """Create the status panel."""
    return rx.box(
        rx.heading("Status", size="md", color=COLORS["text"], mb="12px"),
        rx.vstack(
            rx.hstack(
                rx.text("Connection:", color=COLORS["text_muted"], font_size="sm"),
                rx.text(
                    LightControllerState.connection_status,
                    color=rx.cond(
                        LightControllerState.is_connected,
                        COLORS["accent"],
                        COLORS["error"]
                    ),
                    font_weight="500",
                    font_size="sm",
                ),
                justify="between",
                width="100%",
            ),
            rx.hstack(
                rx.text("State:", color=COLORS["text_muted"], font_size="sm"),
                rx.text(
                    LightControllerState.sequence_state.title(),
                    color=COLORS["text"],
                    font_weight="500",
                    font_size="sm",
                ),
                justify="between",
                width="100%",
            ),
            rx.hstack(
                rx.text("Active Preset:", color=COLORS["text_muted"], font_size="sm"),
                rx.text(
                    rx.cond(
                        LightControllerState.active_preset.to_string() != "None",
                        LightControllerState.active_preset.to_string(),
                        "None"
                    ),
                    color=COLORS["text"],
                    font_weight="500",
                    font_size="sm",
                ),
                justify="between",
                width="100%",
            ),
            rx.hstack(
                rx.text("Active Scenes:", color=COLORS["text_muted"], font_size="sm"),
                rx.text(
                    LightControllerState.active_scenes.length(),
                    color=COLORS["text"],
                    font_weight="500",
                    font_size="sm",
                ),
                justify="between",
                width="100%",
            ),
            rx.divider(border_color=COLORS["border"]),
            rx.text(
                LightControllerState.status_message,
                color=COLORS["text_muted"],
                font_size="sm",
                font_style="italic",
            ),
            rx.text(
                f"Last update: {LightControllerState.last_update}",
                color=COLORS["text_muted"],
                font_size="xs",
            ),
            spacing="8px",
            align_items="start",
            width="100%",
        ),
        bg=COLORS["surface"],
        border=f"1px solid {COLORS['border']}",
        border_radius="8px",
        p="16px",
    )


def sequence_editor() -> rx.Component:
    """Create the sequence editor modal."""
    return rx.cond(
        LightControllerState.show_sequence_editor,
        rx.box(
            # Modal backdrop
            rx.box(
                position="fixed",
                top="0",
                left="0",
                width="100vw",
                height="100vh",
                bg="rgba(0, 0, 0, 0.5)",
                z_index="1000",
                on_click=LightControllerState.close_sequence_editor,
            ),
            # Modal content
            rx.box(
                rx.vstack(
                    # Header
                    rx.hstack(
                        rx.heading(
                            f"Sequence Editor - Preset {LightControllerState.editing_preset}",
                            size="lg",
                            color=COLORS["text"],
                        ),
                        rx.button(
                            "✕",
                            on_click=LightControllerState.close_sequence_editor,
                            bg=COLORS["error"],
                            color=COLORS["text"],
                            border_radius="4px",
                            _hover={"bg": "#d73648"},
                            size="sm",
                        ),
                        justify="between",
                        width="100%",
                    ),
                    
                    # Sequence steps
                    rx.box(
                        rx.text(
                            f"Steps: {LightControllerState.sequence_steps_count}",
                            color=COLORS["text_muted"],
                            font_size="sm",
                            mb="8px",
                        ),
                        rx.cond(
                            LightControllerState.sequence_steps_count > 0,
                            rx.vstack(
                                *[
                                    rx.box(
                                        rx.hstack(
                                            rx.text(f"Step {i + 1}", font_weight="500", color=COLORS["text"]),
                                            rx.button(
                                                "Remove",
                                                on_click=lambda i=i: LightControllerState.remove_sequence_step(i),
                                                bg=COLORS["error"],
                                                color=COLORS["text"],
                                                size="sm",
                                                _hover={"bg": "#d73648"},
                                            ),
                                            justify="between",
                                        ),
                                        bg=COLORS["border"],
                                        p="8px",
                                        border_radius="4px",
                                        mb="4px",
                                    )
                                    for i in range(10)  # Show up to 10 steps
                                    if i < LightControllerState.sequence_steps_count
                                ],
                                spacing="4px",
                            ),
                            rx.text(
                                "No sequence steps yet",
                                color=COLORS["text_muted"],
                                font_style="italic",
                            ),
                        ),
                        max_height="300px",
                        overflow_y="auto",
                        mb="16px",
                    ),
                    
                    # Controls
                    rx.hstack(
                        rx.button(
                            "Add Step from Active Scenes",
                            on_click=LightControllerState.add_sequence_step,
                            bg=COLORS["accent"],
                            color=COLORS["text"],
                            border_radius="6px",
                            _hover={"bg": "#1f6f32"},
                        ),
                        rx.button(
                            "Save Sequence",
                            on_click=LightControllerState.save_sequence,
                            bg=COLORS["warning"],
                            color=COLORS["text"],
                            border_radius="6px",
                            _hover={"bg": "#bb8a1f"},
                        ),
                        spacing="8px",
                    ),
                    
                    spacing="16px",
                    width="100%",
                ),
                position="fixed",
                top="50%",
                left="50%",
                transform="translate(-50%, -50%)",
                bg=COLORS["surface"],
                border=f"1px solid {COLORS['border']}",
                border_radius="8px",
                p="24px",
                max_width="600px",
                width="90%",
                max_height="80vh",
                overflow="auto",
                z_index="1001",
            ),
        )
    )


def index() -> rx.Component:
    """Main application page."""
    return rx.box(
        # Header
        rx.box(
            rx.hstack(
                rx.heading(
                    "Light Sequence Controller",
                    size="xl",
                    color=COLORS["text"],
                ),
                rx.button(
                    rx.cond(
                        LightControllerState.is_connected,
                        "🟢 Connected",
                        "🔴 Disconnected"
                    ),
                    on_click=lambda: LightControllerState.initialize_controller(True),  # Simulation mode
                    bg=rx.cond(
                        LightControllerState.is_connected,
                        COLORS["accent"],
                        COLORS["error"]
                    ),
                    color=COLORS["text"],
                    border_radius="6px",
                    _hover={"opacity": "0.8"},
                ),
                justify="between",
                align="center",
                width="100%",
                mb="24px",
            ),
            bg=COLORS["surface"],
            border_bottom=f"1px solid {COLORS['border']}",
            p="16px",
        ),
        
        # Main content
        rx.container(
            rx.grid(
                # Left column - Scene grid
                scene_grid(),
                
                # Right column - Presets and controls
                rx.vstack(
                    preset_grid(),
                    control_panel(),
                    status_panel(),
                    spacing="16px",
                ),
                
                columns="2",
                gap="24px",
                width="100%",
            ),
            max_width="1200px",
            px="16px",
            py="24px",
        ),
        
        # Sequence editor modal
        sequence_editor(),
        
        # Global styles
        bg=COLORS["bg"],
        min_height="100vh",
        color=COLORS["text"],
        font_family="system-ui, -apple-system, sans-serif",
    )


# Initialize and configure the app
app = rx.App(
    theme=rx.theme(
        appearance="dark",
        accent_color="green",
    ),
)

app.add_page(
    index,
    title="Light Sequence Controller",
    description="Modern web interface for controlling lighting sequences",
)


def initialize_controller(simulation: bool = False):
    """Initialize the global controller instance."""
    global _controller
    if _controller is None:
        _controller = LightController(simulation=simulation)
    return _controller


def main(simulation: bool = False):
    """Main entry point for the Reflex GUI application."""
    print("🚀 Starting Light Sequence Controller GUI...")
    print(f"📡 Mode: {'Simulation' if simulation else 'Hardware'}")
    print("🌐 Open your browser to: http://localhost:3000")
    
    # Initialize the controller
    initialize_controller(simulation)
    
    # Configure the app for the specified mode
    if simulation:
        print("⚠️  Running in simulation mode - no hardware required")
    
    # Run the Reflex app using the command line interface
    try:
        import subprocess
        import sys
        import os
        
        print("🎯 Starting Reflex development server...")
        
        # Get the controller directory path
        controller_dir = os.path.dirname(os.path.abspath(__file__))
        print(f"📁 Working directory: {controller_dir}")
        
        # Run reflex from the controller directory
        result = subprocess.run(
            [sys.executable, "-m", "reflex", "run", "--env", "dev"],
            cwd=controller_dir,
            check=False
        )
        
        if result.returncode != 0:
            print(f"❌ Reflex exited with code {result.returncode}")
            
    except KeyboardInterrupt:
        print("\n🛑 Shutting down Light Sequence Controller GUI...")
    except Exception as e:
        print(f"❌ Error starting GUI: {e}")
        print("💡 Make sure reflex is installed and working directory is correct")


if __name__ == "__main__":
    import sys
    simulation = "--simulation" in sys.argv
    main(simulation=simulation)