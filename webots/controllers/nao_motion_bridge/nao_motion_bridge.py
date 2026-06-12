"""Motion bridge for the official NAO Saturday demo.

The supervisor decides high-level locomotion intent and writes it to the shared
motion state file. This controller turns that intent into official Webots NAO
motion playback so the robot uses its built-in walking and turning motions
instead of being manually posed.
"""

from __future__ import annotations

import json
from pathlib import Path

try:
    from controller import Motion, Robot
except ImportError as exc:
    raise RuntimeError("This controller must be run by Webots.") from exc


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MOTION_STATE_PATH = PROJECT_ROOT / "data" / "raw" / "webots_motion_state.json"
MOTION_ROOT = PROJECT_ROOT / "webots" / "motions" / "nao"
CONTROLLER_VERSION = "2026-06-12-nao-motion-bridge-v4"
MOTION_FILES = {
    "walk_forward": "Forwards50.motion",
    "turn_left": "TurnLeft40.motion",
    "turn_right": "TurnRight40.motion",
    "hand_wave": "HandWave.motion",
    "support": "WipeForehead.motion",
}


class NaoMotionBridge(Robot):
    def __init__(self) -> None:
        super().__init__()
        self.time_step = int(self.getBasicTimeStep())
        self.motions = self._load_motions()
        self.current_motion_name: str | None = None
        self.current_motion: Motion | None = None
        self.current_loop = False
        self.last_state_signature: tuple[str, str, bool, int] | None = None
        print(f"nao_motion_bridge version: {CONTROLLER_VERSION}")
        print(f"nao_motion_bridge motions: {sorted(self.motions)}")

    def _load_motions(self) -> dict[str, Motion]:
        motions: dict[str, Motion] = {}
        for name, filename in MOTION_FILES.items():
            motion_path = MOTION_ROOT / filename
            if not motion_path.exists():
                raise RuntimeError(f"Missing NAO motion file: {motion_path}")
            motions[name] = Motion(str(motion_path))
        return motions

    def read_motion_state(self) -> dict:
        if not MOTION_STATE_PATH.exists():
            return {"state": "idle", "motion": "idle", "loop": False}
        try:
            return json.loads(MOTION_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"state": "idle", "motion": "idle", "loop": False}

    def stop_current_motion(self) -> None:
        if self.current_motion is not None:
            try:
                self.current_motion.stop()
            except Exception:
                pass
        self.current_motion_name = None
        self.current_motion = None
        self.current_loop = False

    def start_motion(self, motion_name: str, loop: bool) -> None:
        if motion_name == "idle":
            if self.current_motion_name is not None:
                print("nao_motion_bridge motion: idle")
            self.stop_current_motion()
            return

        motion = self.motions.get(motion_name)
        if motion is None:
            print(f"WARNING: unknown NAO motion requested: {motion_name}")
            return

        self.stop_current_motion()
        motion.setLoop(loop)
        motion.play()
        self.current_motion_name = motion_name
        self.current_motion = motion
        self.current_loop = loop
        print(f"nao_motion_bridge motion: {motion_name} loop={loop}")

    def run(self) -> None:
        while self.step(self.time_step) != -1:
            state = self.read_motion_state()
            state_name = str(state.get("state", "idle"))
            motion_name = str(state.get("motion", "idle"))
            loop = bool(state.get("loop", False))
            sequence = int(state.get("sequence", 0))
            state_signature = (state_name, motion_name, loop, sequence)
            if state_signature != self.last_state_signature:
                self.last_state_signature = state_signature
                print(
                    f"nao_motion_bridge state: {state_name} motion={motion_name} "
                    f"loop={loop} sequence={sequence}"
                )
                self.start_motion(motion_name, loop)


if __name__ == "__main__":
    NaoMotionBridge().run()
