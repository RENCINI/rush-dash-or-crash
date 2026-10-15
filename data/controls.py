"""The actions the controls menu can rebind. Their defaults are the keys in data/tuning.py;
`apply` overwrites those at run time, so the game goes on reading its keys from there.

A key is stored the way Ursina's held_keys names it: 'space', 'left mouse', 'scroll up'."""
from collections import namedtuple

from data import tuning as T

# where: the name in tuning, and which entry if that is a tuple. hold: the action reads the key
# as held down, so the mouse wheel can't drive it.
Action = namedtuple('Action', 'id label group where index hold')

ACTIONS = (
    Action('forward', 'FORWARD', 'MOVEMENT', 'KEY_FORWARD', None, True),
    Action('backward', 'BACK', 'MOVEMENT', 'KEY_BACK', None, True),
    Action('left', 'LEFT', 'MOVEMENT', 'KEY_LEFT', None, True),
    Action('right', 'RIGHT', 'MOVEMENT', 'KEY_RIGHT', None, True),
    Action('jump', 'JUMP', 'MOVEMENT', 'KEY_JUMP', None, False),
    Action('dash', 'DASH', 'MOVEMENT', 'KEY_DASH', None, False),
    Action('slide', 'SLIDE', 'MOVEMENT', 'KEYS_SLIDE', 0, True),
    Action('slide_alt', 'SLIDE (ALT)', 'MOVEMENT', 'KEYS_SLIDE', 1, True),
    Action('fire', 'FIRE', 'COMBAT', 'KEY_FIRE', None, True),
    Action('scope', 'SCOPE', 'COMBAT', 'KEY_SCOPE', None, True),
    Action('katana', 'KATANA', 'COMBAT', 'KEY_KATANA', None, False),
    Action('reload', 'RELOAD', 'COMBAT', 'KEY_RELOAD', None, False),
    Action('respawn', 'RESPAWN', 'COMBAT', 'KEY_RESPAWN', None, False),
    *[Action(f'weapon_{i + 1}', f'WEAPON {i + 1}', 'WEAPONS', 'KEYS_WEAPON', i, False) for i in range(5)],
    Action('weapon_next', 'NEXT WEAPON', 'WEAPONS', 'KEY_NEXT_WEAPON', None, False),
    Action('weapon_previous', 'PREV WEAPON', 'WEAPONS', 'KEY_PREVIOUS_WEAPON', None, False),
)
GROUPS = ('MOVEMENT', 'COMBAT', 'WEAPONS')
SENSITIVITY_RANGE = (5, 100)

SHORT_NAMES = {'left mouse': 'LEFT CLICK', 'right mouse': 'RIGHT CLICK', 'middle mouse': 'MIDDLE CLICK',
               'scroll up': 'WHEEL UP', 'scroll down': 'WHEEL DOWN', 'left control': 'L CTRL',
               'right control': 'R CTRL', 'left shift': 'L SHIFT', 'right shift': 'R SHIFT', 'left alt': 'L ALT',
               'right alt': 'R ALT'}


def bound(action):
    """The key tuning holds for an action right now."""
    value = getattr(T, action.where)
    return value if action.index is None else value[action.index]


DEFAULT_KEYS = {action.id: bound(action) for action in ACTIONS}
DEFAULT_SENSITIVITY = T.MOUSE_SENSITIVITY


def apply(keys, sensitivity):
    """Write a full set of bindings and the mouse sensitivity into tuning."""
    for action in ACTIONS:
        if action.index is None:
            setattr(T, action.where, keys[action.id])
        else:
            entries = list(getattr(T, action.where))
            entries[action.index] = keys[action.id]
            setattr(T, action.where, tuple(entries))
    T.MOUSE_SENSITIVITY = sensitivity


def pressed(key, binding):
    """True if an input event is the press of a bound key. Mouse buttons arrive as 'left mouse down'."""
    return key == binding or key == binding + ' down'


def binding_for(key):
    """The key to store for an input event, or None if the event isn't a fresh press."""
    # shift, control and alt each arrive twice; only the left or right one names the key
    if key.endswith(' hold') or key in ('double click', 'shift', 'control', 'alt'):
        return None
    if key.endswith(' mouse down'):
        return key[:-len(' down')]
    if key.endswith(' up') and key not in ('scroll up', 'page up'):
        return None
    return key


def key_name(key):
    return SHORT_NAMES.get(key, key.upper())
