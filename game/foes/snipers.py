"""Snipers: they climb somewhere high, stand still and take their time over one shot.

A laser shows who is being aimed at, pale blue at first and red for the last few seconds. When the
time is up the shot is instant along the laser: only something solid in the way, or a dash at that
moment, saves the player. The plain one is a soldier with a black rifle; the elite, in tech blue
with goggles and gadgets, kills with one shot. Neither can be parried, and neither is put off its
aim by being hurt: it has to be killed.
"""
from math import sqrt
from random import choice

from ursina import Entity, Vec3, color, raycast

from data import tuning as T
from fx.toon import barrel, box, build, burst_mesh, streak_mesh
from game.foes.base import GOLD_SUIT, GOLD_TRIM, GREY, MODEL_SCALE, OUTLINE, Enemy, about_face, clone, fused

OLIVE = color.hsv(40, 0.36, 0.6)            # sand-coloured camouflage: green is kept for parrying
LEAF = color.hsv(26, 0.45, 0.42)            # and a cape of dead brown leaves
MUD = color.hsv(32, 0.45, 0.32)
SKIN = color.hsv(26, 0.38, 0.9)
BLACK = color.hsv(230, 0.2, 0.16)
STEEL = color.hsv(220, 0.12, 0.4)
TECH = color.hsv(205, 0.78, 0.95)
NAVY = color.hsv(222, 0.6, 0.38)
CYAN = color.hsv(185, 0.7, 1)
AMBER = color.hsv(35, 0.85, 1)
LASER_COLD = (0.45, 0.85, 1.0)      # light blue...
LASER_HOT = (1.0, 0.12, 0.1)        # ...to red, over the last seconds
MUZZLE = (0.25, 1.42, 1.75)         # the end of the rifle, in the body's own space: left, up, forward


def rifle_model(gold=False, tech=False):
    """Held across the chest and pointed at the player: a long barrel, a scope and a stock."""
    metal = GOLD_SUIT if gold else BLACK
    trim = GOLD_TRIM if gold else (CYAN if tech else STEEL)
    x, y = MUZZLE[0], MUZZLE[1]
    return build(about_face([
        (box((0.12, 0.2, 0.75), (x, y - 0.03, 0.55)), metal),                   # body
        (box((0.1, 0.24, 0.42), (x, y - 0.1, 0.02)), metal),                    # stock
        (barrel(0.045, 0.9, MUZZLE[2], x=x, y=y, sides=6), metal),              # barrel
        (barrel(0.07, MUZZLE[2] - 0.22, MUZZLE[2], x=x, y=y, sides=6), trim),   # muzzle brake
        (barrel(0.075, 0.3, 0.85, x=x, y=y + 0.17, sides=6), metal),            # scope
        (barrel(0.085, 0.82, 0.9, x=x, y=y + 0.17, sides=6), trim),
        (box((0.07, 0.3, 0.12), (x, y - 0.26, 0.5)), metal),                    # magazine
    ]), OUTLINE)


def soldier_models(gold):
    """A soldier in camouflage, helmet low over the eyes."""
    helmet = GOLD_SUIT if gold else OLIVE
    body = fused([
        (box((0.8, 0.75, 0.5), (0, 1.15, 0)), OLIVE),               # jacket
        (box((0.84, 0.44, 0.56), (0, 1.26, 0)), LEAF),              # vest
        (box((0.84, 0.12, 0.54), (0, 0.84, 0)), MUD),               # belt
        (box((0.6, 0.6, 0.26), (0, 1.25, -0.36)), MUD),             # pack
        (box((0.4, 0.36, 0.38), (0, 1.76, 0)), SKIN),               # head
        (barrel(0.34, -0.3, 0.3, y=1.98, sides=8), helmet),         # helmet
        (box((0.74, 0.07, 0.74), (0, 1.86, 0.02)), GOLD_TRIM if gold else LEAF),    # its brim
    ], [
        (box((0.3, 0.07, 0.03), (0, 1.8, 0.2)), BLACK),             # eyes in shadow
        (box((0.2, 0.16, 0.03), (-0.2, 1.3, 0.29)), MUD),           # camouflage
        (box((0.22, 0.12, 0.03), (0.16, 1.14, 0.29)), OLIVE),
        (box((0.16, 0.1, 0.03), (0.2, 1.38, 0.29)), MUD),
        (box((0.18, 0.12, 0.03), (-0.1, 2.02, 0.31)), LEAF if not gold else GOLD_TRIM),
    ])
    arm = fused([
        (box((0.24, 0.62, 0.26), (0, -0.25, 0)), OLIVE),
        (box((0.26, 0.16, 0.28), (0, -0.12, 0)), LEAF),
        (box((0.27, 0.2, 0.29), (0, -0.64, 0)), BLACK),             # glove
    ])
    leg = fused([
        (box((0.32, 0.56, 0.36), (0, -0.28, 0)), OLIVE),
        (box((0.34, 0.16, 0.38), (0, -0.2, 0)), MUD),
        (box((0.36, 0.26, 0.5), (0, -0.67, 0.05)), BLACK),          # boot
    ])
    return {'body': body, 'arm_left': arm, 'arm_right': arm, 'leg': leg, 'rifle': rifle_model(gold)}


def elite_models(gold):
    """Tech blue from head to foot: goggles that glow, an aerial, and a belt full of gadgets."""
    helmet = GOLD_SUIT if gold else NAVY
    body = fused([
        (box((0.8, 0.75, 0.5), (0, 1.15, 0)), TECH),                # suit
        (box((0.86, 0.34, 0.56), (0, 1.34, 0)), NAVY),              # chest plate
        (box((0.86, 0.14, 0.56), (0, 0.84, 0)), NAVY),              # belt
        (box((0.2, 0.2, 0.16), (-0.3, 0.84, 0.32)), CYAN),          # gadgets on it
        (box((0.16, 0.24, 0.16), (0.02, 0.82, 0.32)), AMBER),
        (box((0.2, 0.16, 0.16), (0.32, 0.84, 0.32)), GREY),
        (box((0.56, 0.7, 0.28), (0, 1.3, -0.38)), NAVY),            # power pack
        (box((0.12, 0.5, 0.12), (-0.18, 1.3, -0.55)), CYAN),
        (box((0.12, 0.5, 0.12), (0.18, 1.3, -0.55)), CYAN),
        (box((0.42, 0.4, 0.4), (0, 1.78, 0)), helmet),              # head, fully covered
        (barrel(0.33, -0.28, 0.28, y=1.98, sides=8), helmet),
        (box((0.5, 0.17, 0.14), (0, 1.84, 0.24)), CYAN),            # goggles
        (box((0.05, 0.5, 0.05), (0.3, 2.3, -0.1)), GREY),           # aerial
        (box((0.1, 0.1, 0.1), (0.3, 2.58, -0.1)), AMBER),
        (box((0.5, 0.16, 0.5), (0.5, 1.56, 0)), NAVY),              # shoulder plates
        (box((0.5, 0.16, 0.5), (-0.5, 1.56, 0)), NAVY),
    ], [
        (box((0.16, 0.1, 0.03), (-0.13, 1.84, 0.32)), color.white),     # lenses
        (box((0.16, 0.1, 0.03), (0.13, 1.84, 0.32)), color.white),
        (box((0.3, 0.05, 0.03), (0, 1.36, 0.29)), CYAN),
        (box((0.08, 0.08, 0.03), (0.24, 1.22, 0.29)), AMBER),
    ])
    arm = fused([
        (box((0.24, 0.62, 0.26), (0, -0.25, 0)), TECH),
        (box((0.28, 0.2, 0.3), (0, -0.4, 0)), NAVY),                # wrist computer
        (box((0.27, 0.2, 0.29), (0, -0.64, 0)), BLACK),
    ], [(box((0.12, 0.08, 0.02), (0, -0.4, 0.16)), CYAN)])
    leg = fused([
        (box((0.32, 0.56, 0.36), (0, -0.28, 0)), TECH),
        (box((0.36, 0.18, 0.4), (0, -0.2, 0)), NAVY),               # knee plate
        (box((0.36, 0.26, 0.5), (0, -0.67, 0.05)), NAVY),
    ])
    return {'body': body, 'arm_left': arm, 'arm_right': arm, 'leg': leg, 'rifle': rifle_model(gold, tech=True)}


class Sniper(Enemy):
    kind = 'sniper'
    stripe = OLIVE
    HP = T.SNIPER_HP
    DEATH = ('khaki', 'dirt')
    PARRY = False
    DOOR = False
    DAMAGE = T.SNIPER_DAMAGE

    @classmethod
    def models(cls, green, gold):
        return soldier_models(gold)

    def __init__(self, game, green, models, gold=False):
        super().__init__(game, green, models, gold)
        self.rifle = Entity(parent=self.entity, model=clone(models['rifle']), ignore=True)
        # the laser is its own thing in the world, not a part of the body, which turns and squashes:
        # an outlined beam, and an outlined star turning where it lands
        self.laser = Entity(model=streak_mesh(tail=1.0, rim=0.6), color=color.white, enabled=False, ignore=True)
        self.dot = Entity(model=burst_mesh(6, 0.45), billboard=True, double_sided=True, color=color.white, scale=0.18,
                          enabled=False, ignore=True)
        self.perch = None

    def spawn(self, x, z, special=None, hp_scale=1.0, size=None):
        super().spawn(x, z, special, hp_scale, size)
        self.aim = 0.0              # seconds the laser has been on the player
        self.rest = 0.6             # until it starts to aim
        self.beep = 0.0
        self.shot_flash = 0.0
        self.perch = self.pick_perch()
        if self.perch is not None:
            self.x, self.y, self.z = self.perch.x, self.perch.y, self.perch.z
            self.aerial = True      # whatever it stands on is not ground the arena knows about
        else:
            door = choice(self.game.map.entries)['spot']
            self.x, self.z = door.x, door.z

    def pick_perch(self):
        """A high spot nobody has taken, as far as can be had from the player."""
        game = self.game
        player = game.player
        taken = [e.perch for e in game.enemies.alive if e is not self and getattr(e, 'perch', None) is not None]
        free = [spot for spot in game.map.perches if spot not in taken]
        away = [spot for spot in free
                if (spot.x - player.x) ** 2 + (spot.z - player.z) ** 2 > T.SPAWN_MIN_DISTANCE ** 2]
        return choice(away or free) if free else None

    @property
    def muzzle(self):
        """Where the rifle ends, in the world."""
        dx, dz = self.game.player.x - self.x, self.game.player.z - self.z
        d = sqrt(dx * dx + dz * dz) or 1.0
        nx, nz = dx / d, dz / d
        k = MODEL_SCALE * self.size
        # the body faces the player; its own left is across that
        return Vec3(self.x + (nx * MUZZLE[2] + nz * MUZZLE[0]) * k, self.y + MUZZLE[1] * k,
                    self.z + (nz * MUZZLE[2] - nx * MUZZLE[0]) * k)

    def act(self, dt, nx, nz, distance, player, others):
        if self.rest > 0:
            self.rest -= dt
            self.show_laser(None)
            return 0.0, 0.0
        self.aim += dt
        left = T.SNIPER_AIM - self.aim
        game = self.game
        game.hud.threat(self, max(0.0, 1 - left / T.SNIPER_WARN), left)
        # the lock ticks, faster and faster once the laser has turned
        self.beep -= dt
        if self.beep <= 0:
            hot = left < T.SNIPER_WARN
            self.beep = max(0.1, left / T.SNIPER_WARN * 0.5) if hot else 1.0
            away = (player.centre - self.centre).length()
            game.sfx.play('lock', volume=(0.75 if hot else 0.3) * max(0.4, 1 - away / 150), pitch=1.5 if hot else 1.0)
        if left <= 0:
            self.fire(player)
        self.show_laser(player)
        return 0.0, 0.0

    def aim_point(self, player):
        """(end of the laser, whether that is the player): it stops at whatever is in the way."""
        start = self.muzzle
        to = player.centre - start
        distance = to.length()
        if distance < 0.5:
            return player.centre, True
        hit = raycast(start, to / distance, distance=distance - 0.5, ignore=(player,))
        if hit.hit:
            return start + to / distance * hit.distance, False
        return player.centre, True

    def fire(self, player):
        game = self.game
        self.aim = 0.0
        self.rest = T.SNIPER_REST
        self.beep = 0.0
        self.shot_flash = 0.12
        self.swing = 0.2
        end, clear = self.aim_point(player)
        start = self.muzzle
        away = (player.centre - start).length()
        game.sfx.play('snipe', volume=max(0.5, 1 - away / 200))
        game.pixels.scatter(start, 'spark', count=16, speed=9, size=0.06, life=0.25, gravity=4, up=0)
        game.pixels.scatter(end, 'spark', count=12, speed=6, size=0.06, life=0.3, gravity=8, up=1)
        self.flash_laser(start, end)
        # a dash made just now carries the player out from under it
        dodged = player.dash_timer > T.DASH_TIME - T.SNIPER_DODGE
        if not clear or dodged or player.invulnerable > 0:
            if clear and dodged:
                game.popups.show(player.centre + player.forward * 2, 'DODGED!', color.white, size=1.5)
            game.particles.burst(end, (1, 0.8, 0.5), count=16, speed=7, size=0.06, life=0.3, white=0.5)
            return
        aim = (end - start).normalized()
        player.take_damage(self.DAMAGE, Vec3(aim.x * T.SNIPER_KNOCK, 3, aim.z * T.SNIPER_KNOCK), source=self)
        game.juice.shake(0.6)

    def show_laser(self, player):
        if self.shot_flash > 0:
            return
        if player is None:
            self.laser.enabled = self.dot.enabled = False
            return
        end, _ = self.aim_point(player)
        left = T.SNIPER_AIM - self.aim
        heat = min(1.0, max(0.0, 1 - left / T.SNIPER_WARN))
        pulse = 1 + 0.6 * heat * abs((self.age * (4 + 10 * heat)) % 2 - 1)
        tint = tuple(c + (h - c) * heat for c, h in zip(LASER_COLD, LASER_HOT))
        self.draw_laser(self.muzzle, end, (0.03 + 0.05 * heat) * pulse, tint)

    def flash_laser(self, start, end):
        self.draw_laser(start, end, 0.22, (1, 1, 0.85))

    def draw_laser(self, start, end, width, tint):
        laser, dot = self.laser, self.dot
        along = end - start
        length = along.length()
        laser.enabled = dot.enabled = True
        laser.position = start
        laser.look_at(end)
        laser.scale = (width, width, length)
        laser.color = dot.color = color.Color(tint[0], tint[1], tint[2], 1)
        dot.position = end
        dot.scale = width * 5
        dot.rotation_z = self.age * 240

    def update(self, dt, player, arena, others):
        self.shot_flash -= dt
        super().update(dt, player, arena, others)
        if self.ally or not (self.aerial or self.grounded):
            # knocked off its perch or turned: the aim is lost with it
            self.laser.enabled = self.dot.enabled = False

    def shove(self, vx, vy, vz):
        if not self.aerial:
            super().shove(vx, vy, vz)       # on its perch it is braced, and nothing moves it

    def retire(self):
        super().retire()
        self.laser.enabled = self.dot.enabled = False
        self.perch = None

    def pose(self):
        if self.ally or not (self.aerial or self.grounded):
            self.rifle.enabled = not self.ally
            return super().pose()
        # both hands on the rifle, feet planted
        self.rifle.enabled = True
        self.leg_left.rotation_x = self.leg_right.rotation_x = 0
        self.arm_left.rotation_x = 80
        self.arm_right.rotation_x = 62 if self.swing <= 0 else 50
        self.rifle.z = 0.12 if self.swing > 0 else 0.0      # the kick


class Elite(Sniper):
    kind = 'elite'
    stripe = TECH
    HP = T.ELITE_HP
    DEATH = ('ink', 'frost')
    DAMAGE = T.ELITE_DAMAGE

    @classmethod
    def models(cls, green, gold):
        return elite_models(gold)


KINDS = (Sniper, Elite)
SHOTS = {}
