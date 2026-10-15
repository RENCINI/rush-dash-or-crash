"""The tally that closes a level, before the upgrade shop.

Each line of the level's score counts up in turn, ticking faster and higher as it goes: kills,
kill points, style points, the best chain and the time. The points are added up, then the best
chain comes down on them as a multiplier, with flames and a shake, and the final score rolls up
under it and slams down. A click skips to the end; another goes on to the shop. The match is
frozen underneath, so all of this runs on real time."""
from math import sin
from random import uniform

from ursina import Entity, Vec3, camera, color, time

from data import tuning as T
from fx.toon import build, plate
from ui.font import Label
from ui.score import GOLD, lozenge, tier_colour

INK = color.Color(0.08, 0.07, 0.15, 1)
STEEL = color.hsv(225, 0.25, 0.75)
CARD = color.hsv(238, 0.55, 0.2)
LINE_X, VALUE_X = -0.33, 0.33
TOP = 0.2
STEP = 0.062
ROW_TIME = T.TALLY_TIME * 0.42     # a line counts up in this long
GAP = 0.18                  # between one line finishing and the next starting


def clock_text(seconds):
    seconds = int(seconds)
    return f'{seconds // 60}:{seconds % 60:02d}'


class Tally(Entity):
    def __init__(self, game):
        super().__init__(parent=camera.ui, z=-7, ignore_paused=True)
        self.game = game
        self.is_open = False
        self.screen = Entity(parent=self, enabled=False)
        Entity(parent=self.screen, model='quad', scale=(4, 2), color=color.Color(0.05, 0.04, 0.1, 0.72), z=1)
        Entity(parent=self.screen, model=build([(plate(lozenge(0.92, 0.82, 0.05), 0.04), CARD)], 0.008), z=0.5)
        self.title = Label(parent=self.screen, text='', origin=(0, 0), position=(0, 0.33, -0.05), scale=2.8,
                           letters=True)
        self.subtitle = Label(parent=self.screen, text='', origin=(0, 0), position=(0, 0.275, -0.05), scale=0.9,
                              color=STEEL)
        self.names, self.values = [], []
        for i in range(5):
            y = TOP - i * STEP
            self.names.append(Label(parent=self.screen, text='', origin=(-0.5, 0), position=(LINE_X, y, -0.05),
                                    scale=1.15, color=STEEL))
            self.values.append(Label(parent=self.screen, text='', origin=(0.5, 0), position=(VALUE_X, y, -0.05),
                                     scale=1.5))
        Entity(parent=self.screen, model='quad', scale=(VALUE_X - LINE_X, 0.004), position=(0, TOP - 4.55 * STEP, -0.04),
               color=STEEL)
        self.total = Label(parent=self.screen, text='', origin=(0.5, 0), position=(VALUE_X, TOP - 5.3 * STEP, -0.05),
                           scale=1.9, color=GOLD)
        Label(parent=self.screen, text='POINTS', origin=(-0.5, 0), position=(LINE_X, TOP - 5.3 * STEP, -0.05),
              scale=1.15, color=STEEL)
        self.mult = Label(parent=self.screen, text='', origin=(0, 0), position=(0, -0.205, -0.08), scale=3.2,
                          letters=True)
        self.final = Label(parent=self.screen, text='', origin=(0, 0), position=(0, -0.3, -0.06), scale=3.6,
                           letters=True, color=GOLD)
        self.prompt = Label(parent=self.screen, text='', origin=(0, 0), position=(0, -0.375, -0.05), scale=0.9,
                            color=STEEL)
        self.clock = 0.0

    # --- opening and closing ---

    def open(self, stats):
        """`stats`: the level and its name, kills, kill points, style points, best chain, time."""
        self.is_open = True
        self.screen.enabled = True
        self.stats = stats
        self.clock = 0.0
        self.step = 0           # which line is counting: 0-4 the lines, 5 the total, 6 the multiplier, 7 the score
        self.step_age = -0.5    # a breath before the first
        self.ticked = 0.0
        self.shake = 0.0
        self.done = False
        self.multiplier = 1 + T.TALLY_CHAIN_STEP * stats['best']
        self.points = stats['base'] + stats['style']
        self.score = round(self.points * self.multiplier)
        self.title.text = f"LEVEL {stats['level']} CLEAR"
        self.subtitle.text = stats['name']
        self.lines = [('KILLS', stats['kills'], str), ('KILL POINTS', stats['base'], lambda n: f'{n:,}'),
                      ('STYLE POINTS', stats['style'], lambda n: f'+{n:,}'), ('BEST CHAIN', stats['best'], lambda n: f'X{n}'),
                      ('TIME', stats['time'], clock_text)]
        for name, value in zip(self.names, self.values):
            name.text = value.text = ''
        self.total.text = self.mult.text = self.final.text = self.prompt.text = ''
        self.game.sfx.play('round_clear')

    def close(self):
        self.is_open = False
        self.screen.enabled = False
        self.game.tally_closed(self.score)

    def finish(self):
        """Everything shown at once: the player clicked through."""
        for i, (name, value, shown) in enumerate(self.lines):
            self.names[i].text = name
            self.values[i].text = shown(value)
        self.total.text = f'{self.points:,}'
        self.mult.text = f'X{self.multiplier:.1f}'
        self.final.text = f'{self.score:,}'
        self.step = 8
        self.land()

    def land(self):
        self.done = True
        self.shake = 1.0
        self.game.sfx.play('slam')
        self.game.postfx.pulse('flash', 0.3, 0.15)
        sparks = self.game.hud.sparks
        for point in self.final.points():
            sparks.spray(point, 'gold', count=4, speed=0.35, size=0.005, life=0.7, gravity=0.6)
        self.prompt.text = 'CLICK TO GO ON TO THE SHOP'

    def input(self, key):
        if not self.is_open:
            return
        if key in ('left mouse down', 'space', 'enter', 'escape'):
            if self.done:
                self.close()
            else:
                self.finish()

    # --- frame ---

    def update(self):
        if not self.is_open:
            return
        dt = time.dt_unscaled
        self.clock += dt
        self.title.drop_in(self.clock)
        self.step_age += dt
        sparks = self.game.hud.sparks
        if self.step < 5:
            name, value, shown = self.lines[self.step]
            self.names[self.step].text = name
            t = min(max(self.step_age / ROW_TIME, 0.0), 1.0)
            self.values[self.step].text = shown(round(value * t) if isinstance(value, int) else value * t)
            self.count_ticks(t, dt)
            if t >= 1 and self.step_age >= ROW_TIME + GAP:
                sparks.spray(self.values[self.step].getPos(camera.ui) + Vec3(-0.03, 0, 0), 'white', count=6,
                             speed=0.2, size=0.0035, life=0.4)
                self.next_step()
        elif self.step == 5:
            t = min(max(self.step_age / ROW_TIME, 0.0), 1.0)
            self.total.text = f'{round(self.points * t):,}'
            self.count_ticks(t, dt)
            if t >= 1 and self.step_age >= ROW_TIME + GAP:
                self.next_step()
                self.mult.text = f'X{self.multiplier:.1f}'
                self.mult.color = tier_colour(self.stats['best'])
                self.game.sfx.play('mult')
                self.shake = 0.7
        elif self.step == 6:
            self.mult.drop_in(self.step_age, height=14)
            if self.step_age >= 0.6:
                self.next_step()
        elif self.step == 7:
            t = min(max(self.step_age / (ROW_TIME * 1.6), 0.0), 1.0)
            self.final.text = f'{round(self.score * (1 - (1 - t) ** 2)):,}'
            self.count_ticks(t, dt, fast=True)
            if t >= 1:
                self.step = 8
                self.land()
        # the multiplier burns once it is down
        if self.step >= 6 and self.stats['best'] >= T.FLAMES_FROM and uniform(0, 1) < 0.6:
            points = self.mult.points()
            if points:
                at = points[int(uniform(0, len(points)))]
                sparks.spray(at + Vec3(0, 0.02, 0), 'dragon', count=1, speed=0.05, size=0.005, life=0.5,
                             gravity=-0.35, up=0.15)
        if self.done:
            self.final.wave(self.clock, height=0.8, speed=7)
            self.prompt.color = color.Color(STEEL[0], STEEL[1], STEEL[2], 0.55 + 0.45 * abs(sin(self.clock * 4)))
        self.shake = max(0.0, self.shake - dt * 3)
        jolt = 0.012 * self.shake ** 2
        self.screen.position = (uniform(-jolt, jolt), uniform(-jolt, jolt), 0)

    def next_step(self):
        self.step += 1
        self.step_age = 0.0
        self.ticked = 0.0

    def count_ticks(self, t, dt, fast=False):
        """Ticks that come quicker and higher as the count runs on."""
        if t >= 1:
            return
        self.ticked -= dt
        if self.ticked <= 0:
            self.ticked = (0.035 if fast else 0.075) * (1 - 0.6 * t)
            pitch = 1.0 + 0.12 * self.step + (0.8 if fast else 0.4) * t
            self.game.sfx.play('tick', volume=0.45, pitch=pitch)
