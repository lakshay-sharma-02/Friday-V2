"""Screenshot adapter — cross-platform screenshot capture."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from friday_mcu.adapters import Adapter, register_adapter
from friday_mcu.core.contracts import Idempotency, contract
from friday_mcu.core.errors import PrimitiveError


@contract(
    precondition="A screenshot tool is available.",
    postcondition="Returns the path to the captured screenshot.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError if capture fails.",
    returns="str: the path to the screenshot file.",
)
def capture(target: str = "full", output_path: str = "") -> str:
    """Capture a screenshot.

    target: 'full' for full screen, 'active' for active window.
    output_path: where to save (auto-generated if empty).
    """
    if not output_path:
        output_path = os.path.join(
            tempfile.gettempdir(),
            f"friday_screenshot_{int(os.times()[4])}.png",
        )

    # Try grim (Wayland/Hyprland)
    try:
        result = subprocess.run(
            ["grim", output_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and Path(output_path).exists():
            return output_path
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Try scrot (X11)
    try:
        result = subprocess.run(
            ["scrot", output_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and Path(output_path).exists():
            return output_path
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Try PIL on Windows
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.save(output_path)
        return output_path
    except Exception:
        pass

    raise PrimitiveError("no screenshot tool available (install grim, scrot, or Pillow)")


class ScreenshotAdapter(Adapter):
    @property
    def name(self) -> str:
        return "screenshot"

    @property
    def capabilities(self) -> list[str]:
        return ["capture"]

    async def initialize(self) -> None:
        pass

    async def execute(self, action: str, **kwargs: Any) -> Any:
        if action == "capture":
            return capture(**kwargs)
        raise PrimitiveError(f"Unknown screenshot action: {action}")

    async def observe(self) -> list:
        return []

    def health_check(self) -> bool:
        return True


try:
    register_adapter(ScreenshotAdapter())
except Exception:
    pass
