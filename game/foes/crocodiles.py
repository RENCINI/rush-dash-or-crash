"""Crocodiles that walk upright: the jungle's answer to astronauts.

The dark green ones are the size of a person and bite like one punches, but from a way off they
crouch and then dash straight through where the player was standing. The light green ones are
small and quick and come on in a string of leaps, biting wherever they land. The red ones keep
their distance, leaping about the clearing and throwing mini crocodiles: one that hits bites and
blows up, and one that misses gets to its feet and runs the player down to blow up beside them.

A parryable one wears a neon green bandana and has neon claws; a golden one wears a golden helmet.
"""
from math import cos, pi, sin, sqrt
from random import choice, uniform

from ursina import Vec3, color

from data import tuning as T
from fx.toon import barrel, box, build
from game.foes.base import GOLD_SUIT, GOLD_TRIM, NEON, OUTLINE, SWING_TIME, Enemy, fused, lob

DARK_GREEN = color.hsv(140, 0.6, 0.42)
DARK_SHADE = color.hsv(145, 0.6, 0.3)
LIGHT_GREEN = color.hsv(92, 0.62, 0.82)
LIGHT_SHADE = color.hsv(104, 0.6, 0.62)
RED = color.hsv(2, 0.72, 0.88)
RED_SHADE = color.hsv(355, 0.75, 0.62)
BELLY = color.hsv(52, 0.3, 0.95)
TOOTH = color.hsv(50, 0.08, 1)
EYE = color.hsv(52, 0.85, 1)
PUPIL = color.hsv(250, 0.4, 0.12)
AIR_TIME = 2 * T.SNAPPER_JUMP / T.ASTRO_GRAVITY
LEAP_TIME = 2 * T.LOBBER_JUMP / T.ASTRO_GRAVITY


def croc_parts(skin, shade, green, gold):
    """(solids, flat details) of the trunk, head and tail, standing at the origin and facing +z."""
    claw = NEON if green else TOOTH
    solids = [
        (box((0.78, 0.8, 0.52), (0, 1.12, 0)), skin),                           # trunk
        (box((0.56, 0.7, 0.1), (0, 1.1, 0.27)), BELLY),                         # pale belly
        (barrel(0.07, -1.5, -0.2, y=0.78, sides=6, end_radius=0.3), skin),      # tail, thick where it joins
        (box((0.52, 0.36, 0.5), (0, 1.74, 0.02)), skin),                        # head
        (box((0.4, 0.2, 0.8), (0, 1.74, 0.62)), skin),                          # upper jaw
        (box((0.36, 0.12, 0.74), (0, 1.56, 0.58)), shade),                      # lower jaw
        (box((0.16, 0.14, 0.18), (-0.17, 1.97, 0.1)), shade),                   # brows the eyes sit under
        (box((0.16, 0.14, 0.18), (0.17, 1.97, 0.1)), shade),
        (box((0.14, 0.1, 0.14), (0, 1.86, 0.98)), shade),                       # nostrils
    ]
    solids += [(box((0.14, 0.16, 0.18), (0, 1.56 - i * 0.24, -0.3)), shade) for i in range(4)]      # ridge down the back
    solids += [(box((0.1, 0.12, 0.14), (0, 0.86, -0.55 - i * 0.26)), shade) for i in range(3)]      # and along the tail
    if green:
        solids += [(box((0.66, 0.16, 0.62), (0, 1.5, 0)), NEON),                # bandana...
                   (box((0.3, 0.3, 0.1), (0, 1.36, 0.3)), NEON),                # ...knotted at the throat
                   (box((0.84, 0.13, 0.58), (0, 0.8, 0)), NEON)]                # and a belt
    if gold:
        solids += [(barrel(0.33, -0.26, 0.3, y=2.0, sides=8), GOLD_SUIT),       # helmet
                   (box((0.72, 0.08, 0.66), (0, 1.94, 0.04)), GOLD_TRIM),
                   (box((0.1, 0.22, 0.44), (0, 2.34, 0)), GOLD_TRIM)]           # its crest
    details = [(box((0.1, 0.1, 0.03), (side * 0.17, 1.96, 0.2)), EYE) for side in (-1, 1)]
    details += [(box((0.04, 0.09, 0.035), (side * 0.17, 1.96, 0.215)), PUPIL) for side in (-1, 1)]
    # teeth down both sides of the snout, and across the front
    details += [(box((0.03, 0.09, 0.07), (side * 0.2, 1.6, 0.35 + i * 0.16)), TOOTH) for side in (-1, 1) for i in range(4)]
    details += [(box((0.07, 0.09, 0.03), (x, 1.6, 1.02)), TOOTH) for x in (-0.12, 0, 0.12)]
    return solids, details, claw


def croc_models(skin, shade, green, gold):
    solids, details, claw = croc_parts(skin, shade, green, gold)
    arm = fused([
        (box((0.22, 0.56, 0.24), (0, -0.22, 0)), skin),
        (box((0.24, 0.16, 0.3), (0, -0.56, 0.02)), shade),                      # hand
    ], [(box((0.05, 0.12, 0.05), (x, -0.68, 0.14)), claw) for x in (-0.08, 0, 0.08)])
    leg = fused([
        (box((0.32, 0.5, 0.36), (0, -0.25, 0)), skin),
        (box((0.36, 0.26, 0.56), (0, -0.67, 0.08)), shade),                     # foot
    ], [(box((0.07, 0.1, 0.08), (x, -0.74, 0.38)), claw) for x in (-0.11, 0, 0.11)])
    return {'body': fused(solids, details), 'arm_left': arm, 'arm_right': arm, 'leg': leg}


def mini_model():
    """A mini crocodile in the air, curled up with its jaws open: nose toward +z."""
    solids, details, claw = croc_parts(RED, RED_SHADE, False, False)
    limbs = [(box((0.24, 0.3, 0.5), (side * 0.48, y, 0.2)), RED_SHADE) for side in (-1, 1) for y in (0.9, 1.4)]
    # built round its own middle, so it tumbles about that
    return build([([(corners - (0, 1.2, 0), normal) for corners, normal in shape], tint)
                  for shape, tint in solids + limbs], OUTLINE)


class Croc(Enemy):
    """Dark green: bites up close, and dashes from further off."""

    kind = 'croc'
    stripe = DARK_GREEN
    SKIN = (DARK_GREEN, DARK_SHADE)
    SHOULDER = (0.5, 1.42)

    @classmethod
    def models(cls, green, gold):
        return croc_models(*cls.SKIN, green, gold)

    def spawn(self, x, z, special=None, hp_scale=1.0, size=None):
        super().spawn(x, z, special, hp_scale, size)
        self.mode = 'run'           # 'crouch', 'dash' and 'winded' follow one another
        self.timer = 0.0
        self.dash_timer = uniform(*T.CROC_DASH_EVERY)
        self.dash_way = (0.0, 0.0)
        self.bitten = False

    def grip(self):
        return 60.0 if self.mode == 'dash' else T.ASTRO_ACCEL

    def act(self, dt, nx, nz, distance, player, others):
        level = self.level_with(player)
        game = self.game
        if self.mode == 'crouch':
            # low on its haunches, eyes flashing: this is the moment to step aside
            self.timer -= dt
            self.squash = -0.28
            if (self.timer * 12) % 2 > 1:
                self.flash = 0.03
            if self.timer <= 0:
                self.mode = 'dash'
                self.timer = T.CROC_DASH_TIME
                # straight at where the player will be if they keep going as they are: standing
                # still or running in a line gets bitten, a change of direction does not
                ahead = distance / T.CROC_DASH_SPEED * T.CROC_DASH_LEAD
                tx, tz = player.x + player.vel.x * ahead - self.x, player.z + player.vel.z * ahead - self.z
                length = sqrt(tx * tx + tz * tz) or 1.0
                self.dash_way = (tx / length, tz / length)
                self.bitten = False
                game.sfx.play('dash', volume=0.5, pitch=0.7)
            return 0.0, 0.0
        if self.mode == 'dash':
            self.timer -= dt
            if not self.bitten and distance < T.CROC_DASH_HIT * self.reach and level:
                self.bitten = True
                self.swing = SWING_TIME
                game.sfx.play('snap')
                self.strike(player, T.CROC_DASH_DAMAGE, self.dash_way[0], self.dash_way[1], T.CROC_DASH_KNOCK)
            if uniform(0, 1) < 40 * dt:
                game.particles.emit((self.x, self.y + 0.2, self.z), (uniform(-1, 1), uniform(1, 3), uniform(-1, 1)),
                                    (0.75, 0.7, 0.5, 1), uniform(0.08, 0.16), 0.4)
            if self.timer <= 0 or self.mode != 'dash':
                self.mode = 'winded'
                self.timer = T.CROC_WINDED
                return 0.0, 0.0
            return self.dash_way[0] * T.CROC_DASH_SPEED, self.dash_way[1] * T.CROC_DASH_SPEED
        if self.mode == 'winded':
            self.timer -= dt
            if self.timer <= 0:
                self.mode = 'run'
                self.dash_timer = uniform(*T.CROC_DASH_EVERY)
            return 0.0, 0.0

        self.dash_timer -= dt
        if self.wind > 0:
            self.wind -= dt
            if self.wind <= 0:
                self.bite(nx, nz, distance, level, player)
            return 0.0, 0.0
        if distance < T.CROC_REACH * self.reach and level:
            if self.hit_cooldown <= 0:
                self.wind = T.CROC_WINDUP
            return 0.0, 0.0
        uphill = game.map.way_up(self, player)
        if uphill is not None:
            nx, nz = uphill
        elif self.dash_timer <= 0 and T.CROC_DASH_RANGE[0] < distance < T.CROC_DASH_RANGE[1] and level:
            self.mode = 'crouch'
            self.timer = T.CROC_CROUCH
            game.sfx.play('growl', volume=max(0.3, 1 - distance / 30))
            return 0.0, 0.0
        hx, hz = self.steer(nx, nz, dt, others)
        speed = T.CROC_SPEED * self.pace
        return hx * speed, hz * speed

    def bite(self, nx, nz, distance, level, player):
        self.hit_cooldown = T.CROC_COOLDOWN
        self.swing = SWING_TIME
        self.game.sfx.play('snap', volume=0.8)
        if distance < T.CROC_BITE_REACH * self.reach and level and player.invulnerable <= 0:
            self.strike(player, T.CROC_BITE, nx, nz, T.CROC_KNOCK * self.size)

    def stagger(self, seconds):
        super().stagger(seconds)
        self.mode = 'run'
        self.dash_timer = uniform(*T.CROC_DASH_EVERY)

    def arm_pose(self, swing):
        if self.mode == 'crouch':
            return 50          # drawn back
        if self.mode == 'dash' or self.swing > 0:
            return -95         # claws out in front
        if self.wind > 0:
            return 60 * (1 - self.wind / T.CROC_WINDUP)
        return swing

    def pose(self):
        super().pose()
        if self.mode in ('crouch', 'dash'):
            self.arm_left.rotation_x = self.arm_right.rotation_x     # both arms, not one


class Snapper(Croc):
    """Light green: small, and never still. It comes on in leaps and bites where it lands."""

    kind = 'snapper'
    stripe = LIGHT_GREEN
    SKIN = (LIGHT_GREEN, LIGHT_SHADE)
    SCALE = T.SNAPPER_SCALE

    def spawn(self, x, z, special=None, hp_scale=1.0, size=None):
        super().spawn(x, z, special, hp_scale, size)
        self.wait = uniform(0, T.SNAPPER_HOP)
        self.zig = choice((-1, 1))

    def act(self, dt, nx, nz, distance, player, others):
        self.snap_at(nx, nz, distance, player)
        self.wait -= dt
        if self.wait > 0:
            return 0.0, 0.0
        uphill = self.game.map.way_up(self, player)
        if uphill is not None:
            nx, nz = uphill
            speed = T.SNAPPER_SPEED
        elif distance < T.SNAPPER_SPEED * AIR_TIME:
            speed = max(2.0, (distance - 0.8) / AIR_TIME)       # the last leap comes down on the player
        else:
            # one side of the straight line and then the other, so it is not an easy shot
            self.zig = -self.zig
            wx, wz = nx - nz * self.zig * T.SNAPPER_ZIGZAG, nz + nx * self.zig * T.SNAPPER_ZIGZAG
            length = sqrt(wx * wx + wz * wz)
            nx, nz = wx / length, wz / length
            speed = T.SNAPPER_SPEED
        self.hop(nx * speed, nz * speed, T.SNAPPER_JUMP)
        return 0.0, 0.0

    def land(self, nx, nz, distance, player):
        self.wait = T.SNAPPER_HOP
        if self.stun <= 0 and not self.ally:
            self.snap_at(nx, nz, distance, player)

    def snap_at(self, nx, nz, distance, player):
        if self.hit_cooldown > 0 or distance > T.SNAPPER_REACH * self.reach or not self.level_with(player):
            return
        self.hit_cooldown = 0.7
        self.swing = SWING_TIME
        self.game.sfx.play('snap', volume=0.6, pitch=1.4)
        if player.invulnerable <= 0:
            self.strike(player, T.SNAPPER_BITE, nx, nz, T.SNAPPER_KNOCK, up=3.0)

    def arm_pose(self, swing):
        return -95 if self.swing > 0 or not self.grounded else swing


class Lobber(Croc):
    """Red: it leaps from place to place round the clearing and throws mini crocodiles."""

    kind = 'lobber'
    stripe = RED
    SKIN = (RED, RED_SHADE)

    def spawn(self, x, z, special=None, hp_scale=1.0, size=None):
        super().spawn(x, z, special, hp_scale, size)
        self.leap_timer = uniform(0.3, T.LOBBER_LEAP_EVERY)
        self.hit_cooldown = uniform(1.0, T.LOBBER_THROW_EVERY)

    def act(self, dt, nx, nz, distance, player, others):
        game = self.game
        if self.wind > 0:
            self.wind -= dt
            if self.wind <= 0:
                self.throw(player)
            return 0.0, 0.0
        if self.hit_cooldown <= 0 and distance < 50:
            minis = sum(1 for e in game.enemies.alive if e.kind == 'mini')
            if minis < T.MINI_CAP:
                self.wind = T.LOBBER_WINDUP
                self.hit_cooldown = T.LOBBER_THROW_EVERY * uniform(0.8, 1.25)
                return 0.0, 0.0
        self.leap_timer -= dt
        if self.leap_timer <= 0:
            self.leap_timer = T.LOBBER_LEAP_EVERY * uniform(0.8, 1.2)
            # somewhere else round the player, neither close nor out of throwing range
            a, r = uniform(0, 2 * pi), uniform(*T.LOBBER_RANGE)
            tx, tz = player.x + sin(a) * r, player.z + cos(a) * r
            edge = game.map.radius - 5
            far = sqrt(tx * tx + tz * tz)
            if far > edge:
                tx, tz = tx * edge / far, tz * edge / far
            vx, vz = (tx - self.x) / LEAP_TIME, (tz - self.z) / LEAP_TIME
            fast = sqrt(vx * vx + vz * vz)
            if fast > 24:
                vx, vz = vx * 24 / fast, vz * 24 / fast
            self.hop(vx, vz, T.LOBBER_JUMP)
        return 0.0, 0.0

    def throw(self, player):
        self.swing = SWING_TIME
        game = self.game
        hand = Vec3(self.x, self.y + (self.HEIGHT + 0.3) * self.size, self.z)
        flight = max((player.centre - hand).length() / T.MINI_SPEED, 0.3)
        target = player.centre + Vec3(player.vel.x, 0, player.vel.z) * (flight * T.MARKER_LEAD)
        game.enemies.throw(self, hand, lob(hand, target, T.MINI_SPEED, T.MINI_GRAVITY), NEON if self.green else RED,
                           kind='mini', damage=T.MINI_BITE + T.MINI_BLAST, gravity=T.MINI_GRAVITY, spin=540,
                           scale=T.MINI_SCALE, tinted=self.green, sound='snap', on_hit=self.mini_hit,
                           on_land=self.mini_land)

    def mini_hit(self, shot, point):
        """It got its teeth in: the bite and the blast were one hit, and here is the bang."""
        self.game.explode(point, T.MINI_BLAST_RADIUS, T.MINI_ENEMY_DAMAGE, RED, player_knock=10.0, quiet=True)
        self.game.blasts.show(point, T.MINI_BLAST_RADIUS, RED, life=0.3)
        self.game.sfx.play('explode', volume=0.7, pitch=1.5)

    def mini_land(self, shot, point):
        """It missed: it gets up where it fell and goes after the player on foot."""
        game = self.game
        if abs(point.x) + abs(point.z) > 2 * game.map.radius:
            return
        mini = game.enemies.spawn('mini', point.x, point.z, green=shot.green)
        if mini is not None:
            mini.y = game.map.ground_height(point.x, point.z, point.y + 0.5)

    def arm_pose(self, swing):
        if self.wind > 0:
            return -200 * (1 - self.wind / T.LOBBER_WINDUP)     # up and over the shoulder
        if self.swing > 0:
            return -40 - 160 * self.swing / SWING_TIME
        return swing

    def pose(self):
        Enemy.pose(self)


class Mini(Snapper):
    """A thrown mini crocodile that missed. It leaps after the player like a snapper, and goes off
    beside them, when it is killed, or when its time is up: whichever comes first."""

    kind = 'mini'
    stripe = RED
    SKIN = (RED, RED_SHADE)
    SCALE = T.MINI_SCALE
    DROPS = False

    def spawn(self, x, z, special=None, hp_scale=1.0, size=None):
        super().spawn(x, z, None, hp_scale, size)
        self.hp = self.max_hp = T.MINI_HP * hp_scale
        self.fuse = T.MINI_FUSE
        self.spawning = 0.0
        self.pause = 0.3            # getting up
        self.squash = -0.4

    def update(self, dt, player, arena, others):
        super().update(dt, player, arena, others)
        if not self.alive or self.ally:
            return
        self.fuse -= dt
        # it ticks: flashing, faster as the time runs out
        if (self.fuse * (2 + 6 * (1 - self.fuse / T.MINI_FUSE))) % 1 > 0.7:
            self.flash = 0.03
        near = (player.centre - self.centre).length() < T.MINI_TRIGGER and self.pause <= 0
        if self.fuse <= 0 or near:
            self.game.enemies.damage(self, self.hp + 1)

    def snap_at(self, nx, nz, distance, player):
        """It does not bite. It is the bomb."""

    def died(self):
        game = self.game
        centre = self.centre
        game.explode(centre, T.MINI_BLAST_RADIUS, T.MINI_ENEMY_DAMAGE, RED, player_knock=10.0, quiet=True,
                     self_damage=T.MINI_BLAST_DAMAGE)
        game.blasts.show(centre, T.MINI_BLAST_RADIUS, RED, life=0.3)
        game.sfx.play('explode', volume=0.7, pitch=1.5)


KINDS = (Croc, Snapper, Lobber, Mini)
SHOTS = {'mini': mini_model}
