"""What the player picks on the menu, kept between runs in settings.json."""
import json
from pathlib import Path

from data import tuning as T
from data.controls import DEFAULT_KEYS, DEFAULT_SENSITIVITY, SENSITIVITY_RANGE

SETTINGS_FILE = Path(__file__).resolve().parent.parent / 'settings.json'
NAME_LENGTH = 12
DEFAULT_NAME = 'PLAYER'


def clean_name(text):
    """Capitals only, no longer than the HUD has room for. < and > would be read as text tags."""
    return ''.join(c for c in text.upper() if c.isprintable() and c not in '<>')[:NAME_LENGTH]


class Settings:
    def __init__(self, path=SETTINGS_FILE):
        self.path = Path(path)
        self.name = DEFAULT_NAME
        self.hue = None                 # None keeps each weapon's own paint
        self.volume = T.MASTER_VOLUME   # 0-1
        self.keys = dict(DEFAULT_KEYS)  # action id -> key, see data/controls.py
        self.sensitivity = DEFAULT_SENSITIVITY
        self.effects = True             # the full-screen effects: see fx/postfx.py
        self.load()

    def load(self):
        try:
            saved = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return
        if not isinstance(saved, dict):
            return
        name, hue, volume = saved.get('name'), saved.get('hue'), saved.get('volume')
        if isinstance(name, str) and clean_name(name).strip():
            self.name = clean_name(name).strip()
        if isinstance(hue, (int, float)) and not isinstance(hue, bool):
            self.hue = hue % 360
            if self.hue == T.GREEN_HUE:
                self.hue = 78       # the old GREEN paint is LIME now: green is kept for what can be parried
        if isinstance(volume, (int, float)) and not isinstance(volume, bool):
            self.volume = min(max(float(volume), 0.0), 1.0)
        keys, sensitivity = saved.get('keys'), saved.get('sensitivity')
        if isinstance(keys, dict):
            for action, key in keys.items():
                if action in self.keys and isinstance(key, str) and key:
                    self.keys[action] = key
            for action in DEFAULT_KEYS:
                # an action added since the file was saved takes its key back from whatever had it
                if action not in keys:
                    for other, key in self.keys.items():
                        if other != action and key == DEFAULT_KEYS[action]:
                            self.keys[other] = DEFAULT_KEYS[other]
        if isinstance(sensitivity, (int, float)) and not isinstance(sensitivity, bool):
            self.sensitivity = min(max(sensitivity, SENSITIVITY_RANGE[0]), SENSITIVITY_RANGE[1])
        if isinstance(saved.get('effects'), bool):
            self.effects = saved['effects']

    def save(self):
        saved = {'name': self.name, 'hue': self.hue, 'volume': round(self.volume, 2),
                 'sensitivity': self.sensitivity, 'keys': self.keys, 'effects': self.effects}
        try:
            self.path.write_text(json.dumps(saved, indent=2), encoding='utf-8')
        except OSError:
            pass    # a folder that can't be written to just means nothing is remembered
