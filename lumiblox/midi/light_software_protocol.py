"""
LightSoftware Protocol

Defines the structural interface that both ``LightSoftware`` (real DasLight 4)
and ``LightSoftwareSim`` (test simulator) must satisfy.  Uses
``typing.Protocol`` so existing classes conform without explicit inheritance.
"""

from typing import Dict, Optional, Protocol, Tuple, runtime_checkable


@runtime_checkable
class LightSoftwareProtocol(Protocol):
    """Structural protocol for light-software backends."""

    connection_good: bool

    def connect_midi(self) -> bool: ...

    def set_scene_state(self, scene_index: Tuple[int, int], active: bool) -> None: ...

    def get_scene_coordinates_for_note(self, note: int) -> Optional[Tuple[int, int]]: ...

    def process_feedback(self) -> Dict[int, bool]: ...

    def close(self) -> None: ...
