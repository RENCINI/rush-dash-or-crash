"""Astronauts in white suits: brawlers run in and punch, throwers hang back and lob giant marker pens.

They come in all sizes: a big one has more health, a longer reach and a bigger body to hit, and
a small one is quicker. None of them jumps like the player. They hop, and a brawler leaps forward
to land a punch, but to reach a catwalk they have to run up its gangway.
"""
from math import sqrt
from random import choice, uniform

from ursina import Entity, Vec3, color

from data import tuning as T
from fx.toon import barrel, box, build
from game.foes.base import (BLUE, GOLD, GOLD_SUIT, GOLD_TRIM, GREEN, GREY, MODEL_SCALE, OUTLINE, RED, SWING_TIME,
                            Enemy, clone, fused)

AIR_TIME = 2 * T.ASTRO_JUMP / T.ASTRO_GRAVITY      # of a hop on level ground

# suit paint: soft like the weapons
SUIT = color.hsv(40, 0.05, 0.98)
PACK = color.hsv(215, 0.1, 0.8)
INK_HUES = (0, 28, 215, 285, 325)       # green ink is kept for the pens that can be parried


def suit_models(stripe, visor, SUIT=SUIT, gloves=False, quiver=False):
    """The pieces of one astronaut, standing at the origin and facing +z. Limbs hang from their pivots.
    `SUIT` repaints the cloth: the golden ones wear gold. A brawler wears big boxing `gloves`; a
    thrower carries a `quiver` of pens on its back, so the two are told apart a long way off."""
    pens = []
    if quiver:
        pens = [(box((0.5, 0.42, 0.24), (0, 1.32, -0.6)), stripe)]          # the quiver, on the pack
        caps = ((-0.15, color.hsv(330, 0.6, 1)), (0.0, color.hsv(28, 0.7, 1)), (0.15, color.hsv(275, 0.55, 1)))
        pens += [(box((0.13, 0.5, 0.13), (x, 1.7, -0.6)), tint) for x, tint in caps]
    body = fused(pens + [
        (box((0.8, 0.75, 0.5), (0, 1.15, 0)), SUIT),                # torso
        (box((0.84, 0.12, 0.54), (0, 0.84, 0)), stripe),            # belt
        (box((0.66, 0.9, 0.3), (0, 1.27, -0.38)), PACK),            # life-support pack
        (box((0.36, 0.26, 0.12), (0, 1.22, 0.3)), GREY),            # chest controls
        (box((0.5, 0.12, 0.46), (0, 1.58, 0)), GREY),               # neck ring
        (barrel(0.36, -0.3, 0.3, y=1.92, sides=8), SUIT),           # helmet
        (barrel(0.27, 0.3, 0.37, y=1.92, sides=8), visor),
    ], [
        (box((0.08, 0.08, 0.03), (-0.08, 1.25, 0.37)), RED),
        (box((0.08, 0.08, 0.03), (0.08, 1.25, 0.37)), BLUE),
        (box((0.14, 0.05, 0.02), (-0.08, 2.02, 0.375)), color.white),      # glint on the visor
    ])
    arm = [
        (box((0.24, 0.62, 0.26), (0, -0.25, 0)), SUIT),
        (box((0.26, 0.1, 0.28), (0, -0.3, 0)), stripe),
        (box((0.4, 0.34, 0.42), (0, -0.7, 0.03)) if gloves else box((0.27, 0.2, 0.29), (0, -0.64, 0)),
         stripe if gloves else GREY),                               # glove
    ]
    # the flag on the left shoulder, seen from that side: canton toward the front
    flag = [
        (box((0.02, 0.08, 0.09), (-0.142, -0.02, 0.065)), BLUE),
        (box((0.02, 0.027, 0.13), (-0.142, 0.005, -0.045)), RED),
        (box((0.02, 0.027, 0.13), (-0.142, -0.048, -0.045)), RED),
        (box((0.02, 0.027, 0.22), (-0.142, -0.1, 0)), RED),
    ]
    leg = fused([
        (box((0.32, 0.56, 0.36), (0, -0.28, 0)), SUIT),
        (box((0.34, 0.1, 0.38), (0, -0.36, 0)), stripe),
        (box((0.36, 0.26, 0.5), (0, -0.67, 0.05)), GREY),           # boot
    ])
    return {
        'body': body,
        'arm_left': fused(arm + [(box((0.03, 0.16, 0.24), (-0.125, -0.05, 0)), color.white)], flag),
        'arm_right': fused(arm),
        'leg': leg,
    }


def marker_model():
    """A felt-tip pen as long as a person's leg, nib toward +z. Built pale: the tint is the ink."""
    pale, mid, deep = color.white, color.hsv(0, 0, 0.82), color.hsv(0, 0, 0.6)
    return build([
        (barrel(0.14, -0.35, 0.5, sides=8), pale),                  # body
        (barrel(0.146, -0.1, 0.2, sides=8), mid),                   # label
        (barrel(0.165, -0.78, -0.33, sides=8), deep),               # cap, pushed on the back end
        (box((0.05, 0.05, 0.36), (0, 0.19, -0.55)), deep),          # clip
        (barrel(0.11, 0.5, 0.6, sides=8), mid),
        (barrel(0.09, 0.6, 0.8, sides=8, end_radius=0.03), pale),   # nib
    ], OUTLINE)


class Astronaut(Enemy):
    GLOVES = QUIVER = False

    @classmethod
    def models(cls, green, gold):
        if gold:
            return suit_models(GOLD_TRIM, color.white, GOLD_SUIT, cls.GLOVES, cls.QUIVER)
        return suit_models(GREEN if green else cls.stripe, GREEN if green else GOLD, SUIT, cls.GLOVES, cls.QUIVER)


class Brawler(Astronaut):
    """Runs at the player, draws an arm back and punches; from further off it may leap in."""

    kind = 'brawler'
    stripe = RED
    leaping = False
    GLOVES = True

    def spawn(self, x, z, special=None, hp_scale=1.0, size=None):
        super().spawn(x, z, special, hp_scale, size)
        self.leaping = False

    def act(self, dt, nx, nz, distance, player, others):
        level = self.level_with(player)
        speed = T.BRAWLER_SPEED * self.pace
        if self.wind > 0:
            self.wind -= dt
            if self.wind <= 0:
                self.punch(nx, nz, distance, level, player)
            return 0.0, 0.0
        if distance < T.BRAWLER_REACH * self.reach and level:
            if self.hit_cooldown <= 0:
                self.wind = T.BRAWLER_WINDUP
            return 0.0, 0.0
        uphill = self.game.map.way_up(self, player)
        if uphill is not None:
            nx, nz = uphill
        elif self.hop_timer <= 0:
            if T.LEAP_RANGE[0] < distance < T.LEAP_RANGE[1] and level:
                # a leap that comes down just short of the player, with a punch on landing
                self.leaping = True
                fast = min(T.LEAP_SPEED, (distance - 1.0) / AIR_TIME)
                self.hop(nx * fast, nz * fast)
            else:
                self.hop(self.vx, self.vz)      # a skip in its stride
            return 0.0, 0.0
        hx, hz = self.steer(nx, nz, dt, others)
        return hx * speed, hz * speed

    def land(self, nx, nz, distance, player):
        if self.leaping:
            self.leaping = False
            if self.stun <= 0 and self.hit_cooldown <= 0:
                self.punch(nx, nz, distance, self.level_with(player), player)

    def punch(self, nx, nz, distance, level, player):
        self.hit_cooldown = T.BRAWLER_COOLDOWN
        self.swing = SWING_TIME
        sfx = self.game.sfx
        sfx.play('throw', volume=0.35, pitch=1.6)
        if distance < T.BRAWLER_PUNCH_REACH * self.reach and level and player.invulnerable <= 0:
            knock = T.BRAWLER_KNOCK * self.size
            player.take_damage(T.BRAWLER_DAMAGE, Vec3(nx * knock, 6, nz * knock),
                               source=self, green=self.green)
            if self.stun <= 0:      # not parried
                sfx.play('punch')

    def arm_pose(self, swing):
        if self.wind > 0:
            return 60 * (1 - self.wind / T.BRAWLER_WINDUP)      # drawn back
        if self.swing > 0:
            return -95      # straight out
        return swing


class Thrower(Astronaut):
    """Keeps its distance, circling, and lobs a marker pen every few seconds."""

    kind = 'thrower'
    stripe = BLUE
    QUIVER = True
    DEATH = ('suit', 'ink')

    def __init__(self, game, green, models, gold=False):
        super().__init__(game, green, models, gold)
        # the pen it is about to throw, in the glove
        self.held = Entity(parent=self.arm_right, model=clone(game.enemies.shot_mesh('marker')), position=(0, -0.72, -0.1),
                           rotation_y=180, scale=1 / MODEL_SCALE, enabled=False)

    def spawn(self, x, z, special=None, hp_scale=1.0, size=None):
        super().spawn(x, z, special, hp_scale, size)
        self.hit_cooldown = uniform(0.8, T.THROWER_INTERVAL)
        self.strafe = choice((-1, 1))
        self.strafe_timer = uniform(1.5, 3.5)
        self.ink = color.hsv(T.GREEN_HUE if self.green else choice(INK_HUES), 0.8, 1)
        self.held.color = self.ink
        self.held.enabled = False

    def act(self, dt, nx, nz, distance, player, others):
        if self.wind > 0:
            self.wind -= dt
            if self.wind <= 0:
                self.throw(distance, player)
            return 0.0, 0.0
        if self.hit_cooldown <= 0 and distance < T.THROWER_RANGE:
            self.wind = T.THROWER_WINDUP
            self.hit_cooldown = T.THROWER_INTERVAL * uniform(0.8, 1.25)
            self.held.enabled = True
            return 0.0, 0.0
        self.strafe_timer -= dt
        if self.strafe_timer <= 0:
            self.strafe_timer = uniform(1.5, 3.5)
            self.strafe = -self.strafe
        if distance > T.THROWER_FAR:
            gx, gz = nx, nz
        elif distance < T.THROWER_NEAR:
            gx, gz = -nx, -nz
        else:
            gx, gz = -nz * self.strafe, nx * self.strafe
        hx, hz = self.steer(gx, gz, dt, others)
        speed = T.THROWER_SPEED * self.pace
        if self.hop_timer <= 0:
            self.hop(hx * speed * 1.5, hz * speed * 1.5)    # a hop the way it was going, to be harder to hit
            return 0.0, 0.0
        return hx * speed, hz * speed

    def throw(self, distance, player):
        self.swing = SWING_TIME
        self.held.enabled = False
        hand = Vec3(self.x, self.y + (self.HEIGHT + 0.3) * self.size, self.z)
        # aim where the player will be if they keep some of their speed, then solve the arc
        flight = max(distance / T.MARKER_SPEED, 0.3)
        to = player.centre + Vec3(player.vel.x, 0, player.vel.z) * (flight * T.MARKER_LEAD) - hand
        flight = max(sqrt(to.x * to.x + to.z * to.z) / T.MARKER_SPEED, 0.3)
        velocity = Vec3(to.x / flight, to.y / flight + 0.5 * T.MARKER_GRAVITY * flight, to.z / flight)
        self.game.enemies.throw(self, hand, velocity, self.ink)

    def stagger(self, seconds):
        super().stagger(seconds)
        self.held.enabled = False

    def arm_pose(self, swing):
        if self.wind > 0:
            return -200 * (1 - self.wind / T.THROWER_WINDUP)    # up and over the shoulder
        if self.swing > 0:
            return -40 - 160 * self.swing / SWING_TIME          # whipped forward
        return swing


KINDS = (Brawler, Thrower)
SHOTS = {'marker': marker_model}
