"""Title and pause menu, built from the same outlined cartoon solids as the weapons."""
from math import exp, sin
from random import choice, uniform

from PIL import Image
from ursina import Entity, Texture, Vec2, Vec3, camera, clamp, color, mouse, time

from data import controls
from data import tuning as T
from data.controls import ACTIONS, GROUPS, SENSITIVITY_RANGE, key_name
from data.levels import LEVELS
from data.settings import DEFAULT_NAME, clean_name
from fx.toon import barrel, blocks, box, build, plate
from game.weapons import CREAM, DARK
from ui.font import Label
from ui.hud import INK, player_colour

CARD = color.hsv(250, 0.35, 0.24)
SLOT = color.hsv(250, 0.4, 0.13)
WHITE = (1, 1, 1)       # solids built white take their colour from the entity's tint
# the title as rows of cubes, each letter with its hue
TITLE = (
    (('XXX.', 'X.X.', 'XXX.', 'X.XX', 'X..X'), 185),
    (('X.X', 'X.X', 'X.X', 'X.X', 'XXX'), 52),
    (('XXX', 'X..', 'XXX', '..X', 'XXX'), 325),
    (('X.X', 'X.X', 'XXX', 'X.X', 'X.X'), 275),
)
CLASSIC_HUES = (178, 8, 282, 38)    # four of the weapons' own colours, for the first swatch
# (hue, name); None keeps each weapon's own paint
PAINTS = ((None, 'CLASSIC'), (0, 'RED'), (28, 'ORANGE'), (52, 'YELLOW'), (78, 'LIME'), (185, 'CYAN'),
          (222, 'BLUE'), (282, 'PURPLE'), (325, 'PINK'))

# layout in UI units: the screen is 1 tall and x is 0 at its centre
TITLE_Y, TITLE_CUBE, TITLE_GAP = 0.355, 0.038, 0.032
ROW_NAME, ROW_PAINT, ROW_VOLUME, ROW_PLAY = 0.15, 0.04, -0.07, -0.3
LABEL_X = -0.46
FIELD_X, FIELD_WIDTH, FIELD_HEIGHT = 0.07, 0.5, 0.07
SWATCH_X, SWATCH_STEP, SWATCH_SIZE = -0.155, 0.058, 0.044
TRACK_X, TRACK_LENGTH = -0.18, 0.4      # left end of the volume slider
PLAY_X, PLAY_WIDTH, PLAY_HEIGHT = -0.16, 0.34, 0.1
CONTROLS_X, CONTROLS_WIDTH = 0.19, 0.28
ROW_UPGRADES, UPGRADES_X, UPGRADES_WIDTH, UPGRADES_HEIGHT = -0.42, 0.0, 0.3, 0.07
STAGE_X, ERASE_X = -0.36, 0.36         # either side of it: which level to play, and deleting the save
SURE_TIME = 3.0                         # how long DELETE SAVE waits for its second click
DANGER = color.hsv(0, 0.7, 1)
GOLD = color.hsv(46, 0.75, 1)
EFFECTS_X = 0.42                        # the effects switch, beside DEFAULTS on the controls page
ENTRANCE = 0.32                         # seconds for the board to slam in when the menu opens


def stripes_texture(size=64):
    """Hard-edged diagonal bands for the backdrop, scrolled slowly behind the board."""
    image = Image.new('RGBA', (size, size))
    pixels = image.load()
    for y in range(size):
        for x in range(size):
            pixels[x, y] = (255, 255, 255, 255 if (x + y) % 32 < 12 else 0)
    return Texture(image, filtering=None)


def overshoot(t):
    """0 to 1, a little past and back: something slamming into place."""
    t = min(max(t, 0.0), 1.0) - 1
    return 1 + 2.70158 * t ** 3 + 1.70158 * t ** 2

# the controls page: a sensitivity slider over three columns of key slots
ROW_AIM, ROW_HEADER, ROW_KEYS, KEY_STEP = 0.195, 0.125, 0.075, 0.049
AIM_X, AIM_LENGTH = -0.4, 0.5
COLUMN_X = (-0.67, -0.2, 0.25)          # where each group's labels start
KEY_OFFSET, KEY_WIDTH, KEY_HEIGHT = 0.3, 0.17, 0.038
ROW_DONE, DONE_X, DEFAULTS_X, SMALL_WIDTH, SMALL_HEIGHT = -0.41, -0.14, 0.14, 0.24, 0.07
HINT = 'CLICK A KEY, THEN PRESS THE NEW ONE'
NOTE_TIME = 3.0
TEXT_Z = -0.02                          # in front of every solid on the board


def toy(parent, *parts, outline=0.008, **kwargs):
    """One outlined piece made of (shape, colour) pairs."""
    return Entity(parent=parent, model=build(parts, outline), **kwargs)


def capital(rows):
    """A block capital from rows of text where X is a cube, centred on the origin."""
    width, height = len(rows[0]), len(rows)
    return blocks({(i - width / 2, height / 2 - 1 - j) for j, row in enumerate(rows) for i, mark in enumerate(row)
                   if mark == 'X'}, depth=1.6)


class Menu(Entity):
    """Name, colour and volume, the button that starts or resumes the match, and a second
    page for the controls. The match is paused underneath for as long as this is open.
    The save can be deleted here, and once every level is cleared, the level to play picked."""

    def __init__(self, game):
        super().__init__(parent=camera.ui, z=-5, ignore_paused=True)
        self.game = game
        self.settings = game.settings
        self.is_open = False
        self.started = False        # False on the title screen, which ESC can't dismiss
        self.page = 'main'          # or 'controls'
        self.typing = False
        self.dragging = None        # the slider being dragged: 'volume' or 'sensitivity'
        self.armed = None           # the button being held down
        self.waiting = None         # the action whose new key is awaited
        self.note_time = 0.0
        self.hover = None
        self.clock = 0.0
        self.shown_name = None
        self.buttons = {}           # name -> (entity, page, x, y, width, height)
        self.labels = {}            # name -> its Text
        self.glitter = 0.0
        self.sparks = game.hud.sparks
        self.sure = 0.0             # DELETE SAVE was clicked once: seconds left to click it again.
                                    # Below 0 it has just deleted, and says so until this is back at 0

        self.screen = Entity(parent=self, enabled=False)
        Entity(parent=self.screen, model='quad', scale=(4, 2), z=1, color=color.Color(INK[0], INK[1], INK[2], 0.6))
        # bands drifting across the dark, over the blurred arena (see fx/postfx.py)
        self.stripes = Entity(parent=self.screen, model='quad', texture=stripes_texture(), scale=(4, 2), z=0.9,
                              color=color.Color(1, 1, 1, 0.05))
        self.opened = 0.0           # seconds since it opened, for the board to slam in
        self.shake = 0.0
        self.firework = 0.0
        self.board = Entity(parent=self.screen)     # leans toward the mouse
        self.main = Entity(parent=self.board)
        self.controls = Entity(parent=self.board, enabled=False)
        self.build_title()
        self.build_card()
        self.build_controls()
        self.play_text = self.add_button('play', 'PLAY', PLAY_X, ROW_PLAY, PLAY_WIDTH, PLAY_HEIGHT, arrow=True)
        self.add_button('controls', 'CONTROLS', CONTROLS_X, ROW_PLAY, CONTROLS_WIDTH, PLAY_HEIGHT)
        # the upgrade shop opens between levels, so it is offered on the title screen only
        self.upgrades = Entity(parent=self.main)
        self.add_button('upgrades', 'UPGRADES', UPGRADES_X, ROW_UPGRADES, UPGRADES_WIDTH, UPGRADES_HEIGHT,
                        parent=self.upgrades)
        # which level to play is offered once the game is beaten
        self.stage = Entity(parent=self.main)
        self.add_button('stage', 'MODE: ENDLESS', STAGE_X, ROW_UPGRADES, UPGRADES_WIDTH, UPGRADES_HEIGHT,
                        parent=self.stage)
        self.add_button('erase', 'DELETE SAVE', ERASE_X, ROW_UPGRADES, UPGRADES_WIDTH, UPGRADES_HEIGHT)
        self.add_button('done', 'DONE', DONE_X, ROW_DONE, SMALL_WIDTH, SMALL_HEIGHT)
        self.add_button('defaults', 'DEFAULTS', DEFAULTS_X, ROW_DONE, SMALL_WIDTH, SMALL_HEIGHT)
        self.add_button('effects', self.effects_label(), EFFECTS_X, ROW_DONE, SMALL_WIDTH, SMALL_HEIGHT)
        self.footer = Label(parent=self.screen, text='', origin=(0, 0), position=(0, -0.44), scale=0.8,
                           color=color.hsv(230, 0.08, 0.78))
        # big news: the game beaten
        self.headline = Label(parent=self.screen, text='', origin=(0, 0), position=(0, -0.205, -0.1), scale=2.4,
                              letters=True, color=GOLD, enabled=False)
        self.refresh()

    # --- building ---

    def build_title(self):
        self.letters = []
        widths = [len(rows[0]) * TITLE_CUBE for rows, _ in TITLE]
        x = -(sum(widths) + TITLE_GAP * (len(TITLE) - 1)) / 2
        for (rows, hue), width in zip(TITLE, widths):
            self.letters.append(toy(self.board, (capital(rows), WHITE), outline=0.2, scale=TITLE_CUBE,
                                    position=(x + width / 2, TITLE_Y), color=color.hsv(hue, 0.62, 1)))
            x += width + TITLE_GAP

    def build_card(self):
        board = self.main
        toy(board, (box((1.06, 0.42, 0.04), (0, 0.04, 0.09)), CARD))
        for label, y in (('NAME', ROW_NAME), ('COLOR', ROW_PAINT), ('VOLUME', ROW_VOLUME)):
            Label(parent=board, text=label, origin=(-0.5, 0), position=(LABEL_X, y, TEXT_Z), scale=1.3)

        self.field = toy(board, (box((FIELD_WIDTH, FIELD_HEIGHT, 0.03)), WHITE),
                         position=(FIELD_X, ROW_NAME, 0.04), color=CREAM)
        left, right = FIELD_X - FIELD_WIDTH / 2, FIELD_X + FIELD_WIDTH / 2
        self.name_text = Label(parent=board, text='', origin=(-0.5, 0), position=(left + 0.02, ROW_NAME, TEXT_Z),
                               scale=1.5, color=INK, style='flat')
        self.name_hint = Label(parent=board, text='CLICK TO EDIT', origin=(0.5, 0), scale=0.7,
                              position=(right - 0.015, ROW_NAME, TEXT_Z),
                              color=color.hsv(40, 0.2, 0.55))

        self.swatches = [toy(board, (box((SWATCH_SIZE, SWATCH_SIZE, 0.03)), WHITE), outline=0.006,
                             position=(SWATCH_X + i * SWATCH_STEP, ROW_PAINT, 0.04), color=player_colour(hue))
                         for i, (hue, _) in enumerate(PAINTS)]
        quarter = SWATCH_SIZE / 4
        tiles = [(box((quarter * 2, quarter * 2, 0.01), (x * quarter, y * quarter, -0.018)), color.hsv(hue, 0.62, 1))
                 for (x, y), hue in zip(((-1, 1), (1, 1), (-1, -1), (1, -1)), CLASSIC_HUES)]
        Entity(parent=self.swatches[0], model=build(tiles, 0))
        self.paint_name = Label(parent=board, text='', origin=(-0.5, 0), scale=0.9,
                               position=(SWATCH_X + len(PAINTS) * SWATCH_STEP - 0.01, ROW_PAINT, TEXT_Z))

        toy(board, (box((TRACK_LENGTH + 0.02, 0.022, 0.02), (TRACK_X + TRACK_LENGTH / 2, ROW_VOLUME, 0.05)), SLOT),
            outline=0.006)
        # the lit part of the track is one unit long from its left end, and stretched to the level
        self.level = Entity(parent=board, model=build([(box((1, 0.012, 0.03), (0.5, 0, 0)), WHITE)], 0),
                            position=(TRACK_X, ROW_VOLUME, 0.05))
        self.knob = toy(board, (barrel(0.027, -0.02, 0.02, sides=12), CREAM), position=(TRACK_X, ROW_VOLUME, 0.03))
        self.volume_text = Label(parent=board, text='', origin=(-0.5, 0), scale=1.1,
                                position=(TRACK_X + TRACK_LENGTH + 0.05, ROW_VOLUME, TEXT_Z))

    def build_controls(self):
        page = self.controls
        toy(page, (box((1.44, 0.6, 0.04), (0, -0.045, 0.09)), CARD))
        Label(parent=page, text='SENSITIVITY', origin=(-0.5, 0), position=(COLUMN_X[0], ROW_AIM, TEXT_Z), scale=1.1)
        toy(page, (box((AIM_LENGTH + 0.02, 0.022, 0.02), (AIM_X + AIM_LENGTH / 2, ROW_AIM, 0.05)), SLOT),
            outline=0.006)
        self.aim_level = Entity(parent=page, model=build([(box((1, 0.012, 0.03), (0.5, 0, 0)), WHITE)], 0),
                                position=(AIM_X, ROW_AIM, 0.05))
        self.aim_knob = toy(page, (barrel(0.024, -0.02, 0.02, sides=12), CREAM), position=(AIM_X, ROW_AIM, 0.03))
        self.aim_text = Label(parent=page, text='', origin=(-0.5, 0), scale=1.1,
                             position=(AIM_X + AIM_LENGTH + 0.05, ROW_AIM, TEXT_Z))
        self.note = Label(parent=page, text=HINT, origin=(0.5, 0), position=(0.68, ROW_AIM, TEXT_Z), scale=0.7,
                         color=color.hsv(230, 0.08, 0.78))

        self.slots = {}     # action id -> (x, y, box, text)
        for x, group in zip(COLUMN_X, GROUPS):
            Label(parent=page, text=group, origin=(-0.5, 0), position=(x, ROW_HEADER, TEXT_Z), scale=0.8,
                 color=color.hsv(230, 0.08, 0.74))
            for row, action in enumerate(a for a in ACTIONS if a.group == group):
                y = ROW_KEYS - row * KEY_STEP
                Label(parent=page, text=action.label, origin=(-0.5, 0), position=(x, y, TEXT_Z), scale=0.9)
                slot = toy(page, (box((KEY_WIDTH, KEY_HEIGHT, 0.03)), WHITE), outline=0.005,
                           position=(x + KEY_OFFSET, y, 0.04), color=CREAM)
                text = Label(parent=page, text='', origin=(0, 0), position=(x + KEY_OFFSET, y, TEXT_Z), scale=0.85,
                            color=INK)
                self.slots[action.id] = (x + KEY_OFFSET, y, slot, text)

    def add_button(self, name, label, x, y, width, height, arrow=False, parent=None):
        """A chunky button over a dark socket that stays put as it is pushed in. Returns its label."""
        page = 'main' if name in ('play', 'controls', 'upgrades', 'stage', 'erase') else 'controls'
        parent = parent or (self.main if page == 'main' else self.controls)
        toy(parent, (box((width + 0.03, height / 2, 0.07), (x, y - height * 0.45, 0.05)), DARK))
        button = toy(parent, (box((width, height, 0.06)), WHITE), outline=0.006, position=(x, y))
        if arrow:
            shape = plate([(-0.14, -0.022), (-0.14, 0.022), (-0.105, 0)], 0.012, z=-0.034)
            Entity(parent=button, model=build([(shape, INK)], 0))
        size = min(22 * height, 50 * width / len(label))       # as tall as the button allows, or as wide
        self.buttons[name] = (button, page, x, y, width, height)
        # dark letters on a light button: flat, as blocks in the dark ink would blur together
        self.labels[name] = Label(parent=button, text=label, origin=(0, 0), position=(0.02 if arrow else 0, 0, -0.05),
                                  scale=size, color=INK, style='flat', letters=True)
        return self.labels[name]

    def relabel(self, name, label):
        """Change what a button says, at the size that fits it."""
        _, _, _, _, width, height = self.buttons[name]
        self.labels[name].text = label
        self.labels[name].scale = min(22 * height, 50 * width / len(label))

    # --- opening and closing ---

    def effects_label(self):
        return 'EFFECTS: ON' if self.settings.effects else 'EFFECTS: OFF'

    def open(self, news=None, headline=None):
        """`news` is a line for the foot of the screen, in place of the usual one; `headline` is big
        news across the middle, in gold, under fireworks."""
        self.is_open = True
        self.screen.enabled = True
        self.opened = 0.0
        self.play_text.text = 'RESUME' if self.started else 'PLAY'
        self.upgrades.enabled = not self.started
        self.footer.text = news or (self.where() + '   ESC  back to the match' if self.started else '')
        self.headline.text = headline or ''
        self.headline.enabled = bool(headline)
        self.show_stage()
        self.show_page('main')
        self.game.pause(True)

    def where(self):
        """The match under way, for the foot of the pause menu."""
        game = self.game
        director = game.director
        if not director.running:
            return ''
        chain = f'   CHAIN X{game.chain.tier}' if game.chain.tier else ''
        return (f'LEVEL {director.level}   ROUND {director.round + 1}/{len(director.rounds)}   '
                f'SCORE {game.chain.score:,}{chain}')

    def close(self):
        self.show_page('main')
        self.settings.save()
        self.started = True
        self.is_open = False
        self.screen.enabled = False
        self.game.pause(False)
        self.game.begin()

    def open_shop(self):
        """Hand the screen to the upgrade shop; the match stays frozen and the shop reopens this."""
        self.settings.save()
        self.is_open = False
        self.screen.enabled = False
        self.game.shop.open(after_level=False)

    def show_page(self, page):
        if self.typing:
            self.stop_typing()
        self.page = page
        self.dragging = self.armed = self.waiting = None
        self.disarm()
        self.main.enabled = self.footer.enabled = page == 'main'
        self.controls.enabled = page == 'controls'
        self.say(HINT)
        self.refresh()

    # --- changing settings ---

    def refresh(self):
        """Put the current settings on the controls."""
        low, high = SENSITIVITY_RANGE
        aim = (self.settings.sensitivity - low) / (high - low)
        self.aim_level.scale_x = max(aim, 0.001) * AIM_LENGTH
        self.aim_knob.x = AIM_X + aim * AIM_LENGTH
        self.aim_text.text = str(round(self.settings.sensitivity))
        for action, (_, _, _, text) in self.slots.items():
            text.text = 'PRESS A KEY' if action == self.waiting else key_name(self.settings.keys[action])
        volume = self.settings.volume
        self.level.scale_x = max(volume, 0.001) * TRACK_LENGTH
        self.knob.x = TRACK_X + volume * TRACK_LENGTH
        self.volume_text.text = f'{round(volume * 100)}%'
        self.paint_name.text = next((name for hue, name in PAINTS if hue == self.settings.hue), '')
        self.name_hint.enabled = not self.typing

    def pick(self, index):
        self.settings.hue = PAINTS[index][0]
        self.settings.save()
        self.game.apply_settings()
        self.game.sfx.play('switch')
        self.refresh()

    def slide(self, x):
        """Set the slider being dragged from where the mouse is along its track."""
        if self.dragging == 'volume':
            self.settings.volume = round(clamp((x - TRACK_X) / TRACK_LENGTH, 0, 1), 2)
            self.game.sfx.volume = self.settings.volume
        else:
            low, high = SENSITIVITY_RANGE
            self.settings.sensitivity = round(low + clamp((x - AIM_X) / AIM_LENGTH, 0, 1) * (high - low))
            controls.apply(self.settings.keys, self.settings.sensitivity)
        self.refresh()

    def say(self, message):
        """Show a line beside the sensitivity slider; anything but the hint fades back to it."""
        self.note.text = message
        self.note_time = 0.0 if message == HINT else NOTE_TIME

    def capture(self, key):
        """Bind the key just pressed to the waiting action. A key already in use swaps over."""
        key = controls.binding_for(key)
        if key is None:
            return
        keys = self.settings.keys
        action = next(a for a in ACTIONS if a.id == self.waiting)
        other = next((a for a in ACTIONS if keys[a.id] == key and a is not action), None)
        old = keys[action.id]
        self.waiting = None
        if key == 'escape':
            self.say(HINT)
        elif key == T.KEY_SPAWN_MANY:
            self.say(f'{key_name(key)} IS KEPT FOR FILLING THE ARENA')
        elif (action.hold and key.startswith('scroll')) or (other and other.hold and old.startswith('scroll')):
            self.say(f"THE WHEEL CAN'T BE HELD DOWN FOR {(action if action.hold else other).label}")
        else:
            keys[action.id] = key
            if other:
                keys[other.id] = old
            self.say(f'SWAPPED WITH {other.label}' if other else HINT)
            self.settings.save()
            self.game.apply_settings()
            self.game.sfx.play('switch')
        self.refresh()

    def restore_defaults(self):
        self.settings.keys = dict(controls.DEFAULT_KEYS)
        self.settings.sensitivity = controls.DEFAULT_SENSITIVITY
        self.settings.save()
        self.game.apply_settings()
        self.say('BACK TO THE DEFAULTS')
        self.refresh()

    def show_stage(self):
        """The button that picks the level, there once every level has been cleared."""
        self.stage.enabled = self.game.director.beaten
        pick = self.game.director.pick
        self.relabel('stage', 'MODE: ENDLESS' if pick is None else f'MODE: LEVEL {pick + 1}')

    def next_stage(self):
        """Endless, then each level in turn. A match under way starts over on what was picked."""
        progress = self.game.progress
        picks = [None, *range(len(LEVELS))]
        now = progress.replay if progress.replay in picks else None
        progress.replay = picks[(picks.index(now) + 1) % len(picks)]
        progress.save()
        self.game.director.changed = True
        self.show_stage()

    def disarm(self):
        self.sure = 0.0
        self.relabel('erase', 'DELETE SAVE')

    def erase(self):
        """The first click asks, shaking and red; the second within a few seconds deletes."""
        if self.sure <= 0:
            self.sure = SURE_TIME
            self.relabel('erase', 'SURE? CLICK AGAIN')
            self.shake = 0.6
            self.game.sfx.play('deny')
            self.burst('erase', 'hurt', 3)
            return
        self.game.erase()
        self.sure = -SURE_TIME
        self.relabel('erase', 'SAVE DELETED')
        self.shake = 1.0
        self.burst('erase', 'hurt', 8)
        self.show_stage()

    def burst(self, name, look, count):
        """Pixels from a button's letters."""
        for point in self.labels[name].points():
            self.sparks.spray(point + Vec3(0, 0, -0.1), look, count=count, speed=0.2, size=0.0035, life=0.45, up=0.08)

    def click(self, name):
        """A button was pressed and let go."""
        self.game.sfx.play('switch')
        if name in self.labels:
            self.burst(name, 'rush', 3)
        if name != 'erase' and self.sure > 0:
            self.disarm()
        if name == 'play':
            self.close()
        elif name == 'upgrades':
            self.open_shop()
        elif name == 'stage':
            self.next_stage()
        elif name == 'erase':
            self.erase()
        elif name == 'defaults':
            self.restore_defaults()
        elif name == 'effects':
            self.settings.effects = not self.settings.effects
            self.settings.save()
            self.game.apply_settings()
            self.relabel('effects', self.effects_label())
        else:
            self.show_page('controls' if name == 'controls' else 'main')

    def set_name(self, text):
        self.settings.name = clean_name(text)
        self.game.hud.set_player(self.settings.name, self.settings.hue)

    def stop_typing(self):
        self.typing = False
        self.set_name(self.settings.name.strip() or DEFAULT_NAME)
        self.settings.save()
        self.refresh()

    # --- input ---

    def target_at(self, x, y):
        """The control under a point in UI units: a button's name, 'name', 'volume', 'sensitivity',
        a swatch's index or an action's id."""
        for name, (_, page, bx, by, width, height) in self.buttons.items():
            if (name == 'upgrades' and self.started) or (name == 'stage' and not self.stage.enabled):
                continue
            if page == self.page and abs(x - bx) <= width / 2 and abs(y - by) <= height / 2:
                return name
        if self.page == 'controls':
            if abs(y - ROW_AIM) <= 0.03 and -0.03 <= x - AIM_X <= AIM_LENGTH + 0.03:
                return 'sensitivity'
            for action, (sx, sy, _, _) in self.slots.items():
                if abs(x - sx) <= KEY_WIDTH / 2 and abs(y - sy) <= KEY_STEP / 2:
                    return action
            return None
        if abs(x - FIELD_X) <= FIELD_WIDTH / 2 and abs(y - ROW_NAME) <= FIELD_HEIGHT / 2:
            return 'name'
        if abs(y - ROW_VOLUME) <= 0.035 and -0.03 <= x - TRACK_X <= TRACK_LENGTH + 0.03:
            return 'volume'
        if abs(y - ROW_PAINT) <= SWATCH_STEP / 2:
            index = round((x - SWATCH_X) / SWATCH_STEP)
            if 0 <= index < len(PAINTS):
                return index
        return None

    def press(self, x, y):
        target = self.target_at(x, y)
        if self.typing and target != 'name':
            self.stop_typing()
        if target in self.buttons:
            self.armed = target
        elif target == 'name':
            self.typing = True
            self.refresh()
        elif target in ('volume', 'sensitivity'):
            self.dragging = target
            self.slide(x)
        elif target in self.slots:
            self.waiting = target
            self.say(HINT)
            self.game.sfx.play('bar_tick', volume=0.5, pitch=1.6)
            self.refresh()
        elif target is not None:
            self.pick(target)

    def release(self, x, y):
        if self.dragging:
            if self.dragging == 'volume':
                self.game.sfx.play('kill')      # a sample of the new level
            self.dragging = None
            self.settings.save()
        if self.armed:
            name, self.armed = self.armed, None
            # acting on release means the click isn't still held when the weapons wake up
            if self.target_at(x, y) == name:
                self.click(name)

    def input(self, key):
        if self.game.shop.is_open:
            return      # the shop has the screen, and its own ESC
        if self.is_open and self.waiting:
            self.capture(key)       # every key, ESC and the mouse included, goes to the slot
            return
        if key == 'escape':
            if not self.is_open:
                self.open()
            elif self.typing:
                self.stop_typing()
            elif self.page == 'controls':
                self.show_page('main')
            elif self.started:
                self.close()
            return
        if not self.is_open:
            return
        if key == 'left mouse down':
            self.press(mouse.x, mouse.y)
        elif key == 'left mouse up':
            self.release(mouse.x, mouse.y)
        elif key == 'enter' and self.page == 'main':
            if self.typing:
                self.stop_typing()
            else:
                self.close()
        elif key in ('backspace', 'backspace hold') and self.typing:
            self.set_name(self.settings.name[:-1])

    def text_input(self, key):
        """Ursina calls this with each character typed, whatever the keyboard layout."""
        if self.is_open and self.typing:
            self.set_name(self.settings.name + key)

    # --- frame ---

    def update(self):
        if not self.is_open:
            return
        dt = min(time.dt_unscaled, 0.05)    # real time: the match's hitstop must not slow the menu
        self.clock += dt
        self.opened += dt
        clock = self.clock
        self.stripes.set_shader_input('texture_scale', Vec2(6, 3))
        self.stripes.set_shader_input('texture_offset', Vec2(clock * 0.05, 0))
        # the board slams in when the menu opens, and shakes when something is refused
        self.shake = max(0.0, self.shake - dt * 3)
        jolt = 0.012 * self.shake ** 2
        self.screen.position = (uniform(-jolt, jolt), uniform(-jolt, jolt), 0)
        if self.opened < ENTRANCE * 2:
            self.board.scale = overshoot(self.opened / ENTRANCE)
        if self.headline.enabled:
            self.headline.drop_in(self.opened) if self.opened < 1.0 else self.headline.wave(clock, height=1.2, speed=6)
            self.firework -= dt
            if self.firework <= 0:
                self.firework = uniform(0.18, 0.4)
                at = Vec3(uniform(-0.7, 0.7), uniform(-0.1, 0.4), -0.2)
                self.sparks.spray(at, 'rush', count=26, speed=0.45, size=0.005, life=0.8, gravity=0.5)
        x, y = mouse.x, mouse.y
        if self.dragging:
            self.slide(x)
        if self.sure:
            before = self.sure
            self.sure -= dt if before > 0 else -dt
            if self.sure * before <= 0:
                self.disarm()
        hover = self.target_at(x, y)
        if hover != self.hover:
            self.hover = hover
            if hover is not None:
                self.game.sfx.play('bar_tick', volume=0.25, pitch=1.3)
                if hover in self.buttons:
                    self.burst(hover, 'white', 2)

        follow = 1 - exp(-16 * dt)
        rainbow = color.hsv((clock * 50) % 360, 0.62, 1)
        accent = rainbow if self.settings.hue is None else player_colour(self.settings.hue)
        board = self.board
        board.rotation_y += (x * 8 - board.rotation_y) * follow * 0.4
        board.rotation_x += (y * 8 - board.rotation_x) * follow * 0.4

        for i, letter in enumerate(self.letters):
            phase = clock * 2.4 - i * 0.8
            drop = max(0.0, 1 - (self.opened - i * 0.07) / 0.25)     # each letter falls in after the last
            letter.y = TITLE_Y + 0.012 * sin(phase) + 0.5 * drop * drop
            letter.rotation_z = 4 * sin(phase * 0.8)
            letter.rotation_y = 14 * sin(phase * 0.45)
        # the title glitters
        self.glitter -= dt
        if self.glitter <= 0 and self.page == 'main':
            self.glitter = 0.06
            letter = choice(self.letters)
            at = letter.getPos(camera.ui) + Vec3(uniform(-0.05, 0.05), uniform(-0.08, 0.08), -0.1)
            self.sparks.spray(at, choice(('rush', 'white', 'gold')), count=1, speed=0.06, size=0.004, life=0.7,
                              gravity=-0.05, up=0.04)

        for name, (button, page, _, by, _, height) in self.buttons.items():
            if page != self.page:
                continue
            size = (1.07 if hover == name else 1.0) + 0.015 * sin(clock * 4)
            button.scale = button.scale_x + (size - button.scale_x) * follow
            button.y = by - (height * 0.16 if self.armed == name else 0)
            button.color = (accent if name in ('play', 'done') else DANGER if name == 'erase' and self.sure > 0
                            else color.white if hover == name else CREAM)
            words = self.labels[name]
            if hover == name:
                words.wave(clock, height=1.0, speed=10)     # its letters ripple under the mouse
            else:
                words.settle()

        if self.page == 'controls':
            self.animate_controls(dt, hover, accent, follow)
            return

        caret = '_' if self.typing and clock % 0.8 < 0.5 else ''
        if self.settings.name + caret != self.shown_name:
            self.shown_name = self.settings.name + caret
            self.name_text.text = self.shown_name
        self.field.color = color.white if self.typing or hover == 'name' else CREAM

        for i, swatch in enumerate(self.swatches):
            chosen = PAINTS[i][0] == self.settings.hue
            size = 1.3 if chosen else 1.12 if hover == i else 1.0
            swatch.scale = swatch.scale_x + (size - swatch.scale_x) * follow
            swatch.z = 0.02 if chosen else 0.04     # the chosen one overlaps its neighbours
            swatch.rotation_z = 6 * sin(clock * 5) if chosen else 0

        self.level.color = accent
        grabbed = 1.2 if self.dragging == 'volume' or hover == 'volume' else 1.0
        self.knob.scale = self.knob.scale_x + (grabbed - self.knob.scale_x) * follow

    def animate_controls(self, dt, hover, accent, follow):
        if self.note_time > 0:
            self.note_time -= dt
            if self.note_time <= 0:
                self.say(HINT)
        self.aim_level.color = accent
        grabbed = 1.2 if self.dragging == 'sensitivity' or hover == 'sensitivity' else 1.0
        self.aim_knob.scale = self.aim_knob.scale_x + (grabbed - self.aim_knob.scale_x) * follow
        for action, (_, _, slot, _) in self.slots.items():
            if action == self.waiting:
                slot.color = accent if self.clock % 0.5 < 0.3 else color.white
            else:
                slot.color = color.white if hover == action else CREAM
            size = 1.08 if action in (self.waiting, hover) else 1.0
            slot.scale = slot.scale_x + (size - slot.scale_x) * follow
