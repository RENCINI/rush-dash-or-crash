"""The chain and the score on the HUD (the numbers are game/chain.py's).

The badge at the top shows the chain tier. It slams in when the tier goes up, drains its bar as
the window to keep it runs out, catches fire from FLAMES_FROM, and shatters when the chain is
lost. The score sits at the top right, rolling up to its real value. Every kill throws its points
up off the enemy, and they fly up into the score with the style bonuses they earned beneath them."""
from math import cos, pi, sin
from random import uniform

from panda3d.core import Point2, Point3
from ursina import Entity, Vec3, camera, color, scene, time

from data import tuning as T
from fx.toon import build, plate
from ui.font import Label

GOLD = color.hsv(46, 0.75, 1)
STYLE = color.hsv(190, 0.55, 1)
STEEL = color.hsv(230, 0.1, 0.72)
BADGE_X, BADGE_Y = 0.0, 0.432
BADGE_W, BADGE_H = 0.13, 0.062
BAR_W, BAR_H = 0.11, 0.009
SCORE_X, SCORE_Y = 0.86, 0.447
FLYERS = 10
POP_TIME, FLY_TIME = 0.32, 0.42
# the badge's colour by tier: cool to hot, never the parry green; at the top it runs through them all
TIER_HUES = (200, 190, 212, 245, 278, 305, 330, 352, 18, 34, 48)


def tier_colour(tier, clock=0.0):
    if tier >= T.CHAIN_TOP:
        hue = (clock * 300) % 280
        return color.hsv(hue + 80 if hue >= 80 else hue, 0.65, 1)     # round the wheel, skipping the greens
    return color.hsv(TIER_HUES[min(tier, len(TIER_HUES) - 1)], 0.72, 1)


def on_screen(point):
    """Where a point in the arena is on the HUD, or None if it is behind the camera."""
    seen = camera.getRelativePoint(scene, Point3(*point))
    flat = Point2()
    if not camera.lens.project(seen, flat):
        return None
    return Vec3(flat.x * camera.aspect_ratio / 2, flat.y / 2, 0)


def lozenge(w, h, cut):
    """A wide plate with its corners cut off, seen from the front."""
    return [(-w / 2 + cut, -h / 2), (w / 2 - cut, -h / 2), (w / 2, -h / 2 + cut), (w / 2, h / 2 - cut),
            (w / 2 - cut, h / 2), (-w / 2 + cut, h / 2), (-w / 2, h / 2 - cut), (-w / 2, -h / 2 + cut)]


class ScoreHud(Entity):
    def __init__(self, hud):
        super().__init__(parent=hud, ignore=True)     # the HUD ticks it; the engine need not look at any of it
        self.hud = hud
        self.game = hud.game
        self.clock = 0.0

        self.badge = Entity(parent=self, position=(BADGE_X, BADGE_Y, -0.05), enabled=False)
        self.plate = Entity(parent=self.badge, model=build([(plate(lozenge(BADGE_W, BADGE_H, 0.016), 0.02), (1, 1, 1))],
                                                            0.005))
        self.multiplier = Label(parent=self.badge, text='', origin=(0, 0), position=(0, 0.002, -0.03), scale=2.5,
                                letters=True, color=color.white)
        self.word = Label(parent=self.badge, text='CHAIN', origin=(0, 0), position=(0, BADGE_H / 2 + 0.012, -0.03),
                          scale=0.7, color=STEEL)
        bar = [(0, -BAR_H / 2), (BAR_W, -BAR_H / 2), (BAR_W, BAR_H / 2), (0, BAR_H / 2)]
        Entity(parent=self.badge, position=(-BAR_W / 2, -BADGE_H / 2 - 0.016, 0),
               model=build([(plate([(x * 1.0 - 0.003 * (i in (0, 3)) + 0.003 * (i in (1, 2)), y * 1.6)
                                    for i, (x, y) in enumerate(bar)], 0.01), color.hsv(250, 0.35, 0.25))], 0.003))
        self.timer = Entity(parent=self.badge, position=(-BAR_W / 2, -BADGE_H / 2 - 0.016, -0.02),
                            model=build([(plate(bar, 0.01), (1, 1, 1))], 0))
        self.tier = 0
        self.slam = 0.0             # 1 just as the tier goes up
        self.flame_timer = 0.0

        Label(parent=self, text='SCORE', origin=(0.5, 0), position=(SCORE_X, SCORE_Y + 0.031), scale=0.75, color=STEEL)
        self.score = Label(parent=self, text='0', origin=(0.5, 0), position=(SCORE_X, SCORE_Y), scale=1.9, color=GOLD)
        self.shown_score = 0.0
        self.score_pop = 0.0
        self.tick_timer = 0.0

        self.flyers = []
        for _ in range(FLYERS):
            points = Label(parent=self, text='', origin=(0, 0), scale=1.7, color=GOLD, enabled=False)
            styles = Label(parent=self, text='', origin=(0, 0), scale=0.85, color=STYLE, enabled=False)
            self.flyers.append({'points': points, 'styles': styles, 'age': 0.0, 'live': False, 'value': 0,
                                'start': Vec3(0, 0, 0)})
        self.flyer_cursor = 0
        self.landed = 0             # points that have reached the counter; the rest are in the air

    # --- events ---

    def reset(self):
        """A level starting: no chain, no score, nothing in the air."""
        self.tier = 0
        self.badge.enabled = False
        self.shown_score = 0.0
        self.landed = 0
        self.score.text = '0'
        for flyer in self.flyers:
            flyer['live'] = False
            flyer['points'].enabled = flyer['styles'].enabled = False

    def kill(self, point, value, styles):
        """A kill worth `value` points at `point` in the arena."""
        flyer = self.flyers[self.flyer_cursor]
        self.flyer_cursor = (self.flyer_cursor + 1) % FLYERS
        if flyer['live']:
            self.landed += flyer['value']       # one still flying is pushed home
        start = on_screen(point) or Vec3(0, 0.1, 0)
        start.x = max(-0.8, min(0.8, start.x))
        start.y = max(-0.4, min(0.3, start.y))
        # kills that come close together stack their points instead of piling them on one spot
        for other in self.flyers:
            close = abs(other['start'].x - start.x) < 0.1 and abs(other['start'].y - start.y) < 0.05
            if other['live'] and other['age'] < POP_TIME and close:
                start.y = other['start'].y + 0.055
        flyer.update(live=True, age=0.0, value=value, start=start)
        flyer['points'].text = f'+{value:,}'
        flyer['points'].enabled = True
        flyer['styles'].text = '  '.join(styles)
        flyer['styles'].enabled = bool(styles)

    def chain_up(self, tier):
        self.tier = tier
        self.badge.enabled = True
        self.multiplier.text = f'X{tier}'
        self.slam = 1.0
        colour = tier_colour(tier, self.clock)
        at = self.badge.getPos(camera.ui)
        self.hud.sparks.spray(at, 'rush' if tier >= T.CHAIN_TOP else 'gold', count=10 + 2 * tier, speed=0.35,
                              size=0.004, life=0.5, gravity=0.5)
        self.plate.color = colour

    def chain_lost(self):
        """The badge bursts into red pixels and is gone."""
        if not self.badge.enabled:
            return
        at = self.badge.getPos(camera.ui)
        for i in range(14):
            a = 2 * pi * i / 14
            self.hud.sparks.spray(at + Vec3(cos(a) * BADGE_W * 0.45, sin(a) * BADGE_H * 0.45, 0), 'hurt', count=3,
                                  speed=0.45, size=0.005, life=0.7, gravity=0.8)
        self.hud.shatter(self.multiplier, 'hurt', count=5, speed=0.5)
        self.badge.enabled = False
        self.tier = 0

    # --- frame ---

    def tick(self, dt):
        self.clock += dt
        chain = self.game.chain
        if self.badge.enabled:
            self.update_badge(dt, chain)
        self.update_flyers(dt)
        self.update_score(dt, chain)

    def update_badge(self, dt, chain):
        self.slam = max(0.0, self.slam - dt * 3.2)
        s = self.slam
        jolt = s * s
        self.badge.scale = 1 + 1.3 * jolt - 0.12 * sin(s * pi * 3) * s
        self.badge.rotation_z = sin(self.clock * 47) * 9 * jolt
        shake = 0.004 * jolt + (0.0015 if chain.tier >= T.FLAMES_FROM else 0)
        self.badge.position = (BADGE_X + uniform(-shake, shake), BADGE_Y + uniform(-shake, shake), -0.05)
        colour = tier_colour(chain.tier, self.clock)
        self.plate.color = color.white if s > 0.75 else colour
        self.timer.scale_x = max(chain.fraction, 0.001)
        self.timer.color = colour if chain.fraction > 0.3 or sin(self.clock * 30) > 0 else color.white
        if chain.tier >= T.FLAMES_FROM:
            self.multiplier.wave(self.clock, height=0.6, speed=10)
            self.flame_timer -= dt
            if self.flame_timer <= 0:
                self.flame_timer = max(0.012, 0.06 - 0.008 * (chain.tier - T.FLAMES_FROM))
                at = self.badge.getPos(camera.ui) + Vec3(uniform(-BADGE_W, BADGE_W) * 0.45, BADGE_H * 0.4, 0)
                self.hud.sparks.spray(at, 'dragon', count=1, speed=0.05, size=0.0045, life=0.45, gravity=-0.35, up=0.12)
        elif s <= 0:
            self.multiplier.settle()

    def update_flyers(self, dt):
        target = Vec3(SCORE_X - 0.05, SCORE_Y, 0)
        for flyer in self.flyers:
            if not flyer['live']:
                continue
            flyer['age'] += dt
            age = flyer['age']
            points, styles = flyer['points'], flyer['styles']
            start = flyer['start']
            if age < POP_TIME:
                t = age / POP_TIME
                grow = 1 + 0.6 * sin(pi * min(t * 1.6, 1))
                spot = start + Vec3(0, 0.05 * (1 - (1 - t) ** 2), 0)
                points.scale = 1.7 * grow
            else:
                t = min((age - POP_TIME) / FLY_TIME, 1.0)
                lift = start + Vec3(0, 0.05, 0)
                pull = t * t
                spot = lift + (target - lift) * pull + Vec3(0, 0.08 * sin(pi * t), 0)
                points.scale = 1.7 * (1 - 0.45 * t)
                if t >= 1:
                    flyer['live'] = False
                    points.enabled = styles.enabled = False
                    self.landed += flyer['value']
                    self.score_pop = 1.0
                    self.hud.sparks.spray(target, 'gold', count=6, speed=0.22, size=0.0035, life=0.45, up=0.08)
                    continue
            points.position = (spot.x, spot.y, -0.1)
            styles.position = (spot.x, spot.y - 0.035, -0.1)
            styles.enabled = bool(styles.text) and age < POP_TIME + FLY_TIME * 0.5

    def update_score(self, dt, chain):
        real = min(self.landed, chain.score)
        if abs(self.shown_score - real) >= 1:
            step = max(600.0, abs(real - self.shown_score) * 10) * dt
            self.shown_score += max(-step, min(step, real - self.shown_score))
            self.tick_timer -= dt
            if self.tick_timer <= 0:
                self.tick_timer = 0.05
                self.game.sfx.play('tick', volume=0.25, pitch=1.3 + min(chain.tier, 10) * 0.05)
        else:
            self.shown_score = real
        text = f'{round(self.shown_score):,}'
        if text != self.score.text:
            self.score.text = text
        self.score_pop = max(0.0, self.score_pop - dt * 5)
        self.score.scale = 1.9 * (1 + 0.3 * self.score_pop)
