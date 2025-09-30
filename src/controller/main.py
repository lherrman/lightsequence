import logging
import time
import numpy as np

from controller.daslight import Daslight
from controller.launchpad import LaunchpadMK2

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

scene_states = np.zeros((8, 8), dtype=bool)

BUTTON_SCENES_TO_NOTE = {
    (0, 1): 81,
    (0, 2): 71,
    (0, 3): 61,
    (0, 4): 51,
    (0, 5): 41,
    (1, 1): 82,
    (1, 2): 72,
    (1, 3): 62,
    (1, 4): 52,
    (1, 5): 42,
    (2, 1): 83,
    (2, 2): 73,
    (2, 3): 63,
    (2, 4): 53,
    (2, 5): 43,
    (3, 1): 84,
    (3, 2): 74,
    (3, 3): 64,
    (3, 4): 54,
    (3, 5): 44,
    (4, 1): 85,
    (4, 2): 75,
    (4, 3): 65,
    (4, 4): 55,
    (4, 5): 45,
    (5, 1): 86,
    (5, 2): 76,
    (5, 3): 66,
    (5, 4): 56,
    (5, 5): 46,
    (6, 1): 87,
    (6, 2): 77,
    (6, 3): 67,
    (6, 4): 57,
    (6, 5): 47,
    (7, 1): 88,
    (7, 2): 78,
    (7, 3): 68,
    (7, 4): 58,
    (7, 5): 48,
}

BUTTON_PRESETS_MAP = {
    (0, 6): 31,
    (0, 7): 21,
    (0, 8): 11,
    (1, 6): 32,
    (1, 7): 22,
    (1, 8): 12,
    (2, 6): 33,
    (2, 7): 23,
    (2, 8): 13,
    (3, 6): 34,
    (3, 7): 24,
    (3, 8): 14,
    (4, 6): 35,
    (4, 7): 25,
    (4, 8): 15,
    (5, 6): 36,
    (5, 7): 26,
    (5, 8): 16,
    (6, 6): 37,
    (6, 7): 27,
    (6, 8): 17,
    (7, 6): 38,
    (7, 7): 28,
    (7, 8): 18,
}


COLOR_PRESET_ON = [0.1, 1.0, 0.0]  # Yellow
COLOR_PRESET_OFF = [0.0, 0.0, 0.0]  # Off


def main():
    midi_software = Daslight()
    midi_software.connect_midi()
    changes = midi_software.process_feedback()

    launchpad = LaunchpadMK2()
    active_preset = None
    while True:
        button_event = launchpad.get_button_events()
        if button_event:
            # send to DasLight
            x, y = button_event["index"]
            state = button_event["active"]
            note = BUTTON_SCENES_TO_NOTE.get((x, y))
            if note and state is True:
                midi_software.send_scene_command(note)

            if (x, y) in BUTTON_PRESETS_MAP and state is True:
                # show on Launchpad which preset is active
                if active_preset:
                    launchpad.set_led(
                        active_preset[0], active_preset[1], COLOR_PRESET_OFF
                    )

                if active_preset == [x, y]:
                    # deactivate if same preset button pressed again
                    active_preset = None
                    launchpad.set_led(x, y, COLOR_PRESET_OFF)
                    continue

                active_preset = [x, y]
                launchpad.set_led(x, y, COLOR_PRESET_ON)

        # get feedback from DasLight
        changes = midi_software.process_feedback()
        for note, state in changes.items():
            button_mapped = [k for k, v in BUTTON_SCENES_TO_NOTE.items() if v == note]
            if button_mapped:
                x, y = button_mapped[0]
                color = [0.0, 1.0, 0.0] if state else [0.0, 0.0, 0.0]
                launchpad.set_led(x, y, color)
        time.sleep(0.1)


if __name__ == "__main__":
    main()
