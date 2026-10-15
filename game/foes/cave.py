"""What lives in the crystal cave.

Crystal monkeys hang from the vines in the roof, swing from one to the next and fling shards.
Crystal golems are small clusters that roll at the player fast, too fast to turn sharply, and leap
when they are close. Miners travel under the floor: one comes up out of a hole, walks about for a
few seconds swinging its pick or throwing it, a rock or a crystal, and digs down again.

A parryable one carries neon green crystals (a miner, a neon lamp and pick); a golden one is gold
where the others are crystal, under a gold crest, crown or hard hat.
"""
from math import atan2, cos, degrees, exp, pi, radians, sin, sqrt
from random import choice, uniform

from panda3d.core import NodePath
from ursina import Entity, Vec3, color

from data import tuning as T
from fx.toon import OUTLINE as INK, barrel, box, build, flat_bands, placed
from game.foes.base import GOLD_SUIT, GOLD_TRIM, GREY, MODEL_SCALE, NEON, OUTLINE, SWING_TIME, Enemy, clone, fused, lob

FUR = color.hsv(285, 0.42, 0.64)          # bright enough to stand off the cave's dark rock
FUR_PALE = color.hsv(290, 0.18, 0.88)
STONE = color.hsv(250, 0.16, 0.66)
STONE_DARK = color.hsv(256, 0.24, 0.48)
PALE = color.hsv(0, 0, 0.96)                # what a green one throws is built pale, to be tinted neon
PALE_SHADE = color.hsv(0, 0, 0.78)
MAGENTA = color.hsv(305, 0.55, 1)
CYAN = color.hsv(185, 0.55, 1)
AMBER = color.hsv(45, 0.6, 1)
VIOLET = color.hsv(265, 0.5, 1)
ROSE = color.hsv(340, 0.5, 1)
DENIM = color.hsv(215, 0.5, 0.6)
SHIRT = color.hsv(15, 0.55, 0.78)
SKIN = color.hsv(26, 0.38, 0.9)
BEARD = color.hsv(30, 0.25, 0.92)
HAT = color.hsv(48, 0.8, 1)
WOOD = color.hsv(30, 0.5, 0.6)
IRON = color.hsv(220, 0.12, 0.62)
BLACK = color.hsv(250, 0.3, 0.14)
DIRT = (0.5, 0.42, 0.36, 1)
HANG = 2.25                 # a monkey's feet are this far under the hand it hangs by, at ordinary size
GOLEM_AIR = 2 * 6.0 / T.ASTRO_GRAVITY
# scratch nodes for turning a body that leans with its vine: tilt first, then the way it faces
FRAME = NodePath('frame')
TILT = FRAME.attachNewNode('tilt')
FACE = TILT.attachNewNode('face')


def gem(radius, z0, z1, x=0.0, y=0.0):
    """A crystal along z: a six-sided shaft coming to a point at z1."""
    neck = z0 + (z1 - z0) * 0.7
    return barrel(radius, z0, neck, x=x, y=y, sides=6) + barrel(radius, neck, z1, x=x, y=y, sides=6,
                                                                 end_radius=radius * 0.15)


def upright(shape, at=(0, 0, 0), lean=0.0, yaw=0.0):
    """A shape built along z, stood on end at `at`, then leaned and turned."""
    return placed(placed(shape, pitch=-90 + lean), at, yaw=yaw)


def shard_model():
    """A splinter of crystal, point toward +z. Built pale: the tint is its colour."""
    return build([(gem(0.16, -0.5, 0.6), color.white)], OUTLINE)


def rock_model(stone=STONE, dark=STONE_DARK):
    return build([(box((0.5, 0.42, 0.46)), stone), (box((0.3, 0.3, 0.56), (0.06, 0.08, 0)), dark)], OUTLINE)


def pick_parts(metal=IRON, wood=WOOD):
    """A pickaxe lying along z, its head at the far end."""
    return [(barrel(0.05, -0.55, 0.5, sides=6), wood),
            (box((0.9, 0.12, 0.14), (0, 0, 0.5)), metal),
            (box((0.2, 0.1, 0.12), (-0.52, -0.05, 0.5)), metal),
            (box((0.2, 0.1, 0.12), (0.52, -0.05, 0.5)), metal)]


def pick_model(metal=IRON, wood=WOOD):
    return build(pick_parts(metal, wood), OUTLINE)


def hole_mesh(steps=18):
    """The hole a miner leaves in the floor, from above: a black pit in a lip of turned earth."""
    def rim(radius):
        return [(sin(2 * pi * i / steps) * radius * (1 + 0.07 * sin(6 * pi * i / steps)),
                 cos(2 * pi * i / steps) * radius * (1 + 0.05 * cos(10 * pi * i / steps)), 0) for i in range(steps)]
    return flat_bands([rim(0.31), rim(0.37), rim(0.47), rim(0.51)],
                      [(0.05, 0.03, 0.08, 1), (0.34, 0.26, 0.2, 1), (0.54, 0.43, 0.33, 1), (*INK, 1)])


# --- crystal monkey ---

def monkey_models(green, gold):
    crystals = [NEON] * 3 if green else [GOLD_SUIT, GOLD_TRIM, GOLD_SUIT] if gold else [MAGENTA, CYAN, AMBER]
    solids = [
        (box((0.7, 0.72, 0.5), (0, 1.12, 0)), FUR),                             # trunk
        (box((0.46, 0.46, 0.1), (0, 1.1, 0.27)), FUR_PALE),                     # chest
        (box((0.56, 0.5, 0.5), (0, 1.74, 0.02)), FUR),                          # head
        (box((0.4, 0.32, 0.14), (0, 1.7, 0.3)), FUR_PALE),                      # face
        (box((0.3, 0.16, 0.2), (0, 1.6, 0.4)), FUR_PALE),                       # muzzle
        (box((0.14, 0.24, 0.1), (-0.36, 1.78, 0)), FUR_PALE),                   # ears
        (box((0.14, 0.24, 0.1), (0.36, 1.78, 0)), FUR_PALE),
        (barrel(0.07, -1.1, -0.2, y=0.84, sides=5), FUR),                       # tail...
        (box((0.14, 0.5, 0.14), (0, 1.06, -1.1)), FUR),                         # ...curling up at the end
    ]
    # crystals growing out of its back and the top of its head
    solids += [(upright(gem(0.13, 0, 0.6), (x, 1.3 + 0.12 * i, -0.24), lean=-40, yaw=x * 60), crystals[i % 3])
               for i, x in enumerate((-0.2, 0, 0.2))]
    solids += [(upright(gem(0.1, 0, 0.42 + 0.14 * (i == 1)), (x, 1.95, 0), lean=-8, yaw=x * 90), crystals[(i + 1) % 3])
               for i, x in enumerate((-0.15, 0, 0.15))]
    if gold:
        solids.append((box((0.62, 0.1, 0.56), (0, 2.0, 0.02)), GOLD_TRIM))      # the band of its crown
    details = [(box((0.09, 0.09, 0.03), (side * 0.11, 1.78, 0.38)), color.white) for side in (-1, 1)]
    details += [(box((0.04, 0.05, 0.035), (side * 0.11, 1.78, 0.39)), BLACK) for side in (-1, 1)]
    details.append((box((0.2, 0.03, 0.03), (0, 1.57, 0.51)), BLACK))
    arm = fused([
        (box((0.2, 0.86, 0.22), (0, -0.38, 0)), FUR),                           # long arms
        (box((0.24, 0.22, 0.26), (0, -0.86, 0)), FUR_PALE),                     # hand
        (box((0.22, 0.1, 0.24), (0, -0.5, 0)), crystals[0]),                    # a band of crystal at the wrist
    ])
    leg = fused([
        (box((0.26, 0.46, 0.3), (0, -0.23, 0)), FUR),
        (box((0.3, 0.2, 0.46), (0, -0.56, 0.06)), FUR_PALE),
    ])
    return {'body': fused(solids, details), 'arm_left': arm, 'arm_right': arm, 'leg': leg}


class Monkey(Enemy):
    kind = 'monkey'
    stripe = MAGENTA
    SCALE = T.MONKEY_SCALE
    DEATH = ('legion', 'crystal')
    HP = T.MONKEY_HP
    SHOULDER = (0.47, 1.42)
    HIP = (0.18, 0.72)
    DOOR = False

    @classmethod
    def models(cls, green, gold):
        return monkey_models(green, gold)

    def __init__(self, game, green, models, gold=False):
        super().__init__(game, green, models, gold)
        self.held = Entity(parent=self.arm_left, model=clone(game.enemies.shot_mesh('shard')), position=(0, -0.95, -0.1),
                           rotation_y=180, scale=0.7, enabled=False)
        self.anchor = None
        self.vine = None
        self.mode = 'hang'

    def spawn(self, x, z, special=None, hp_scale=1.0, size=None):
        super().spawn(x, z, special, hp_scale, size)
        self.ink = NEON if self.green else GOLD_SUIT if self.gold else choice((MAGENTA, CYAN, AMBER, VIOLET, ROSE))
        self.held.color = self.ink
        self.held.enabled = False
        self.hit_cooldown = uniform(0.8, T.MONKEY_THROW_EVERY)
        self.swing_timer = uniform(*T.MONKEY_SWING_EVERY)
        self.climb = 0.0
        self.sway = uniform(0, 6)
        self.facing = None          # its heading as drawn, which comes round to the player smoothly
        self.drawn_age = 0.0
        self.frame_dt = 0.0
        self.limbs = None           # the angles its limbs are drawn at, easing toward their pose
        self.swing_way = (0.0, 0.0)
        self.vine = None
        self.anchor = self.pick_anchor()
        if self.anchor is None:
            # nothing to hang from here: it comes in on foot and stays there
            door = choice(self.game.map.entries)['spot']
            self.x, self.z = door.x, door.z
            self.mode = 'fallen'
            return
        self.mode = 'hang'
        self.aerial = True
        self.hang_from(self.anchor)

    # --- hanging on ---

    def vine_of(self, anchor):
        """The vine whose tip `anchor` is, or None where there are no vines."""
        arena = self.game.map
        return next((vine for point, vine in zip(arena.anchors, arena.vines) if point is anchor), None)

    def hang_point(self, anchor):
        """Where its feet are when it hangs from `anchor` at rest."""
        return Vec3(anchor.x, anchor.y - HANG * self.size * MODEL_SCALE, anchor.z)

    def hold_point(self):
        """Where its feet are, hanging from what it is holding as that is now: a vine that
        swings carries it round with its tip."""
        if self.vine is not None:
            return self.vine.below(HANG * self.size * MODEL_SCALE)
        return self.hang_point(self.anchor)

    def hang_from(self, anchor):
        """Take hold of `anchor` and hang there."""
        self.anchor = anchor
        self.vine = self.vine_of(anchor)
        if self.vine is not None:
            self.vine.holder = self
        at = self.hold_point()
        self.x, self.y, self.z = at.x, at.y, at.z

    def let_go(self, push=(0.0, 0.0)):
        """Leave the vine it holds to swing on its own, shoved `push` (m/s)."""
        vine, self.vine = self.vine, None
        if vine is not None:
            if vine.holder is self:
                vine.holder = None
            vine.kick(*push)

    def pick_anchor(self, near=None):
        """A vine nobody is hanging from, a fair way from the player; with `near`, the closest
        one to there."""
        game = self.game
        player = game.player
        taken = [e.anchor for e in game.enemies.alive if e is not self and getattr(e, 'anchor', None) is not None]
        free = [a for a in game.map.anchors if a not in taken and a is not self.anchor]
        if not free:
            return None
        if near is not None:
            return min(free, key=lambda a: (a.x - near.x) ** 2 + (a.z - near.z) ** 2)
        lo, hi = T.MONKEY_RANGE
        good = [a for a in free if lo * lo < (a.x - player.x) ** 2 + (a.z - player.z) ** 2 < hi * hi]
        if good and self.anchor is not None:
            # not right across the cave in one swing
            close = [a for a in good if (a.x - self.x) ** 2 + (a.z - self.z) ** 2 < 30 * 30]
            good = close or good
        return choice(good or free)

    def swing_to(self, anchor):
        dx, dz = anchor.x - self.x, anchor.z - self.z
        length = sqrt(dx * dx + dz * dz) or 1.0
        self.swing_way = (dx / length, dz / length)
        # it kicks off the vine it leaves, which swings back the other way
        self.let_go((-self.swing_way[0] * T.MONKEY_PUSH_OFF, -self.swing_way[1] * T.MONKEY_PUSH_OFF))
        self.mode = 'swing'
        self.aerial = True
        self.grounded = False
        self.vx = self.vy = self.vz = 0.0
        self.anchor = anchor
        self.swing_from = Vec3(self.x, self.y, self.z)
        self.swing_at = 0.0

    def act(self, dt, nx, nz, distance, player, others):
        game = self.game
        if not self.aerial:
            # on the ground: knocked off its vine, or in a place with none
            if self.mode != 'fallen':
                self.mode = 'fallen'
                self.climb = T.MONKEY_CLIMB
                self.let_go()
                self.anchor = None
            self.climb -= dt
            if self.climb <= 0 and self.wind <= 0:
                anchor = self.pick_anchor(near=self)
                if anchor is not None:
                    game.particles.burst((self.x, self.y + 0.3, self.z), self.ink, count=10, speed=5, size=0.06, life=0.3)
                    self.swing_to(anchor)
                    return 0.0, 0.0
        elif self.mode == 'swing':
            self.swing_at += dt / T.MONKEY_SWING_TIME
            t = min(self.swing_at, 1.0)
            ease = t * t * t * (t * (6 * t - 15) + 10)     # starts and ends gently
            target = self.vine_of(self.anchor)
            end = target.below(HANG * self.size * MODEL_SCALE) if target is not None else self.hang_point(self.anchor)
            at = self.swing_from + (end - self.swing_from) * ease
            self.x, self.z = at.x, at.z
            self.y = at.y - 1.2 * sin(pi * t) * (1 if self.swing_from.y > end.y - 2 else -1)     # dips, or arcs up from the floor
            if t >= 1:
                self.mode = 'hang'
                self.swing_timer = uniform(*T.MONKEY_SWING_EVERY)
                self.squash = 0.15
                self.hang_from(self.anchor)
                if self.vine is not None:
                    # it carries on the way it was going, and the vine swings on under it
                    self.vine.kick(self.swing_way[0] * T.MONKEY_CATCH_KICK, self.swing_way[1] * T.MONKEY_CATCH_KICK)
            return 0.0, 0.0
        else:
            if self.vine is not None:
                self.vine.swing(dt, T.MONKEY_SWAY_STIFFNESS, T.MONKEY_SWAY_DAMPING)
            at = self.hold_point()
            self.x, self.y, self.z = at.x, at.y, at.z
            self.swing_timer -= dt
            if self.swing_timer <= 0 and self.wind <= 0:
                anchor = self.pick_anchor()
                if anchor is not None:
                    self.swing_to(anchor)
                    return 0.0, 0.0
                self.swing_timer = 1.0

        if self.wind > 0:
            self.wind -= dt
            if self.wind <= 0:
                self.fling(player)
        elif self.hit_cooldown <= 0 and distance < 60 and self.sees(player):
            self.wind = T.MONKEY_WINDUP
            self.hit_cooldown = T.MONKEY_THROW_EVERY * uniform(0.8, 1.25)
            self.held.enabled = True
        return 0.0, 0.0

    def fling(self, player):
        self.swing = SWING_TIME
        self.held.enabled = False
        hand = self.centre + Vec3(0, 0.5 * self.size, 0)
        flight = (player.centre - hand).length() / T.SHARD_SPEED
        target = player.centre + Vec3(player.vel.x, 0, player.vel.z) * (flight * T.SHARD_LEAD)
        way = (target - hand).normalized()
        self.game.enemies.throw(self, hand, way * T.SHARD_SPEED, self.ink, kind='shard',
                                damage=T.SHARD_DAMAGE, gravity=2.0, spin=0, sound='chime')
        if self.vine is not None and self.mode == 'hang':
            self.vine.kick(-way.x * T.MONKEY_THROW_KICK, -way.z * T.MONKEY_THROW_KICK)     # the throw rocks it back

    def stagger(self, seconds):
        super().stagger(seconds)
        self.held.enabled = False
        if seconds > 0:
            self.release()      # stunned, it lets go

    def release(self):
        if self.aerial:
            self.let_go()
            self.anchor = None
        super().release()

    def retire(self):
        super().retire()
        self.let_go()
        self.anchor = None

    # --- drawing ---

    def draw(self, nx, nz):
        self.frame_dt = min(max(self.age - self.drawn_age, 0.0), T.MAX_DT)
        self.drawn_age = self.age
        super().draw(nx, nz)
        e = self.entity
        want = -degrees(atan2(nx, nz)) - 180
        if self.facing is None:
            self.facing = want
        self.facing += ((want - self.facing + 180) % 360 - 180) * (1 - exp(-T.MONKEY_TURN * self.frame_dt))
        if not self.aerial:
            e.setH(self.facing)
            return
        # hanging, its body lies along the vine; flying between vines, it leans the way it goes
        if self.mode == 'swing':
            ax, az = -self.swing_way[0] * 0.45, -self.swing_way[1] * 0.45
        elif self.vine is not None:
            ax, az = self.vine.ax, self.vine.az
        else:
            ax = az = 0.0
        TILT.setHpr(0, degrees(az), -degrees(ax))
        FACE.setHpr(self.facing, 0, 0)
        e.setQuat(FACE.getQuat(FRAME))

    def pose(self):
        dt = self.frame_dt
        if not self.aerial:
            if self.grounded:
                speed = sqrt(self.vx * self.vx + self.vz * self.vz)
                swing = sin(self.stride) * min(speed / 6, 1) * 38
            else:
                swing = 22
            want = (swing, -self.arm_pose(swing), -swing, swing)
        elif self.mode == 'hang':
            # one long arm up to the vine, legs trailing and swinging with it
            self.sway += dt * 2.6
            swing = 16 * sin(self.sway)
            want = (-self.arm_pose(swing), 180, -swing, -swing * 0.5)
        else:
            # flying across: both arms reaching for the next vine, legs tucked
            want = (160, 175, -45, -30)
        if self.limbs is None:
            self.limbs = list(want)
        # every limb eases to its pose, the throwing arm fastest, so nothing snaps from one to the next
        quick = 1 - exp(-(30 if self.wind > 0 or self.swing > 0 else 12) * dt)
        slow = 1 - exp(-12 * dt)
        for i, angle in enumerate(want):
            self.limbs[i] += (angle - self.limbs[i]) * (quick if i < 2 else slow)
        left, right, leg_left, leg_right = self.limbs
        # rotation_x as in Enemy.pose, set straight on the node: setP(a) is rotation_x = -a
        self.arm_left.setP(-left)
        self.arm_right.setP(-right)
        self.leg_left.setP(-leg_left)
        self.leg_right.setP(-leg_right)

    def arm_pose(self, swing):
        if self.wind > 0:
            return -200 * (1 - self.wind / T.MONKEY_WINDUP)     # up and over the shoulder
        if self.swing > 0:
            return -40 - 160 * self.swing / SWING_TIME
        return swing


# --- crystal golem ---

def golem_models(green, gold):
    """Built round its own middle, so that it can roll."""
    hues = [NEON] * 5 if green else [GOLD_SUIT, GOLD_TRIM] * 3 if gold else [CYAN, MAGENTA, AMBER, VIOLET, ROSE]
    solids = [(box((0.8, 0.8, 0.8)), STONE_DARK if not gold else GOLD_TRIM),
              (box((0.5, 0.2, 0.12), (0, 0.1, 0.42)), BLACK)]                    # the slot its eyes shine out of
    spikes = ((0, 0, 0, 0.62), (0, 180, 0, 0.5), (62, 40, 0.1, 0.72), (62, 150, 0.0, 0.6), (62, 265, 0.1, 0.68),
              (118, 95, -0.1, 0.64), (118, 215, -0.1, 0.7), (118, 330, -0.1, 0.56), (90, 0, 0.3, 0.5), (90, 180, 0, 0.66))
    for i, (lean, yaw, lift, length) in enumerate(spikes):
        solids.append((upright(gem(0.2, 0.15, 0.3 + length), (0, lift * 0.2, 0), lean=lean, yaw=yaw), hues[i % len(hues)]))
    details = [(box((0.12, 0.1, 0.03), (side * 0.13, 0.1, 0.49)), color.white) for side in (-1, 1)]
    outline = OUTLINE / T.GOLEM_SCALE ** 0.6        # small: a thicker rim, to keep it outlined at a distance
    stub = fused([(box((0.22, 0.4, 0.24), (0, -0.2, 0)), STONE), (gem(0.1, 0, 0.3), hues[0])], (), outline)
    foot = fused([(box((0.26, 0.3, 0.36), (0, -0.15, 0.04)), STONE)], (), outline)
    return {'body': fused(solids, details, outline), 'arm_left': stub, 'arm_right': stub, 'leg': foot}


class Golem(Enemy):
    kind = 'golem'
    stripe = CYAN
    SCALE = T.GOLEM_SCALE
    HEIGHT = 1.5
    CENTRE = 0.75
    MIDDLE = 0.0                # its meshes are built round their middle, so that it can roll
    DEATH = ('stone', 'crystal')
    RADIUS = 1.2
    SHOULDER = (0.55, 0.05)
    HIP = (0.24, -0.45)

    @classmethod
    def models(cls, green, gold):
        return golem_models(green, gold)

    def __init__(self, game, green, models, gold=False):
        super().__init__(game, green, models, gold)

    def spawn(self, x, z, special=None, hp_scale=1.0, size=None):
        super().spawn(x, z, special, hp_scale, size)
        self.way = atan2(-x, -z)        # the way it is rolling: toward the middle to begin with
        self.roll = 0.0
        self.drawn_age = self.age
        self.leaping = False

    def grip(self):
        return 30.0

    def act(self, dt, nx, nz, distance, player, others):
        level = self.level_with(player)
        uphill = self.game.map.way_up(self, player)
        wx, wz = uphill if uphill is not None else (nx, nz)
        # it cannot turn on the spot: the way it rolls comes round to the player a little each frame
        want = atan2(wx, wz)
        off = (want - self.way + pi) % (2 * pi) - pi
        self.way += max(-T.GOLEM_TURN * dt, min(T.GOLEM_TURN * dt, off))
        ahead = abs(off) < 0.5
        if ahead and distance < T.GOLEM_LEAP_AT and level and self.hit_cooldown <= 0:
            self.leaping = True
            self.hit_cooldown = T.GOLEM_COOLDOWN
            fast = min(T.GOLEM_LEAP_SPEED, max(6.0, distance / GOLEM_AIR * 1.3))
            self.hop(nx * fast, nz * fast, 6.0)
            return 0.0, 0.0
        return sin(self.way) * T.GOLEM_SPEED, cos(self.way) * T.GOLEM_SPEED

    def update(self, dt, player, arena, others):
        super().update(dt, player, arena, others)
        if not self.leaping or self.grounded or not self.alive or self.ally:
            return
        to = player.centre - self.centre
        if to.length() < T.GOLEM_REACH + self.radius:
            # it lands its blow in the air and comes off the player like a ball off a wall
            self.leaping = False
            flat = sqrt(to.x * to.x + to.z * to.z) or 1.0
            nx, nz = to.x / flat, to.z / flat
            self.game.sfx.play('chime', volume=0.6, pitch=0.8)
            self.strike(player, T.GOLEM_DAMAGE, nx, nz, T.GOLEM_KNOCK, up=4.0)
            self.vx, self.vz, self.vy = -nx * T.GOLEM_BOUNCE, -nz * T.GOLEM_BOUNCE, 5.0
            self.way = atan2(-nx, -nz)

    def land(self, nx, nz, distance, player):
        self.leaping = False

    def stagger(self, seconds):
        super().stagger(seconds)
        self.leaping = False

    def draw(self, nx, nz):
        super().draw(nx, nz)
        e = self.entity
        e.y = self.y + self.CENTRE * self.size * MODEL_SCALE
        speed = sqrt(self.vx * self.vx + self.vz * self.vz)
        rolling = speed > 4 and self.stun <= 0 and not self.ally
        dt = min(max(self.age - self.drawn_age, 0.0), T.MAX_DT)
        self.drawn_age = self.age
        for limb in (self.arm_left, self.arm_right, self.leg_left, self.leg_right):
            limb.enabled = not rolling
        if rolling:
            # tucked in and turning over, facing the way it goes. A true roll at its speed would
            # spin far too fast for the eye, so it turns over at a pace that can be followed
            self.roll += min(speed * T.GOLEM_ROLL_PER_M, T.GOLEM_ROLL_MAX) * dt
            e.rotation_y = degrees(atan2(self.vx, self.vz)) + 180
            e.rotation_x = -self.roll
            e.rotation_z = T.GOLEM_WOBBLE * sin(radians(self.roll) * 2)     # tumbles, not a wheel
        else:
            self.roll = 0.0
            e.rotation_x = e.rotation_z = 0


# --- miner ---

def miner_models(green, gold):
    hat = GOLD_SUIT if gold else HAT
    lamp = NEON if green else color.white
    body = fused([
        (box((0.8, 0.75, 0.5), (0, 1.15, 0)), SHIRT),               # shirt
        (box((0.84, 0.5, 0.54), (0, 1.02, 0)), DENIM),              # overalls
        (box((0.14, 0.4, 0.56), (-0.24, 1.36, 0)), DENIM),          # their straps
        (box((0.14, 0.4, 0.56), (0.24, 1.36, 0)), DENIM),
        (box((0.6, 0.66, 0.3), (0, 1.2, -0.38)), WOOD),             # sack
        (box((0.44, 0.4, 0.4), (0, 1.76, 0)), SKIN),                # head
        (box((0.46, 0.26, 0.2), (0, 1.62, 0.18)), BEARD),           # beard
        (barrel(0.34, -0.3, 0.3, y=1.98, sides=8), hat),            # hard hat
        (box((0.74, 0.07, 0.8), (0, 1.9, 0.04)), GOLD_TRIM if gold else hat),
        (box((0.18, 0.18, 0.14), (0, 2.06, 0.34)), lamp),           # its lamp
    ], [
        (box((0.08, 0.07, 0.03), (-0.11, 1.8, 0.21)), BLACK),
        (box((0.08, 0.07, 0.03), (0.11, 1.8, 0.21)), BLACK),
        (box((0.1, 0.1, 0.03), (-0.24, 1.2, 0.28)), IRON),          # buttons
        (box((0.1, 0.1, 0.03), (0.24, 1.2, 0.28)), IRON),
    ])
    arm = fused([
        (box((0.24, 0.62, 0.26), (0, -0.25, 0)), SHIRT),
        (box((0.27, 0.2, 0.29), (0, -0.64, 0)), GREY),              # glove
    ])
    leg = fused([
        (box((0.32, 0.56, 0.36), (0, -0.28, 0)), DENIM),
        (box((0.36, 0.26, 0.5), (0, -0.67, 0.05)), BLACK),          # boot
    ])
    # stood on its handle, head up, to be carried
    pick = build([(placed(shape, pitch=-90), tint)
                  for shape, tint in pick_parts(GOLD_SUIT if gold else NEON if green else IRON)], OUTLINE)
    return {'body': body, 'arm_left': arm, 'arm_right': arm, 'leg': leg, 'pick': pick}


class Miner(Enemy):
    kind = 'miner'
    stripe = HAT
    DOOR = False
    DEATH = ('dirt', 'gold')

    @classmethod
    def models(cls, green, gold):
        return miner_models(green, gold)

    def __init__(self, game, green, models, gold=False):
        super().__init__(game, green, models, gold)
        # the pick in its glove, head upward
        self.pick = Entity(parent=self.arm_right, model=clone(models['pick']), position=(0, -0.45, -0.2))
        self.hole = Entity(model=hole_mesh(), rotation_x=90, double_sided=True, enabled=False, ignore=True)
        self.hole_time = 0.0
        self.mode = 'tunnel'

    def spawn(self, x, z, special=None, hp_scale=1.0, size=None):
        super().spawn(x, z, special, hp_scale, size)
        # it starts under the floor, somewhere out by the wall
        a, r = uniform(0, 2 * pi), self.game.map.radius - uniform(8, 14)
        self.x, self.z = sin(a) * r, cos(a) * r
        self.spawning = 0.0
        self.sink = 0.0
        self.timer = 0.0
        self.attack = None
        self.rumble = 0.0
        self.go_under()

    def go_under(self):
        self.mode = 'tunnel'
        self.hidden = True
        self.entity.enabled = False
        self.goal = None
        self.wind = 0.0

    def pick_goal(self, player):
        """Somewhere on the open floor a little way from the player."""
        arena = self.game.map
        for _ in range(12):
            a, r = uniform(0, 2 * pi), uniform(*T.MINER_RANGE)
            x, z = player.x + sin(a) * r, player.z + cos(a) * r
            far = sqrt(x * x + z * z)
            if far > arena.radius - 6 or arena.ground_height(x, z, 20) > 0.05:
                continue
            if any((x - ox) ** 2 + (z - oz) ** 2 < (radius + 2) ** 2 for ox, oz, radius in arena.obstacles):
                continue
            return x, z
        return player.x * 0.5, player.z * 0.5

    def act(self, dt, nx, nz, distance, player, others):
        game = self.game
        if self.mode == 'tunnel':
            if self.goal is None or (self.goal[0] - player.x) ** 2 + (self.goal[1] - player.z) ** 2 > 26 ** 2:
                self.goal = self.pick_goal(player)
            gx, gz = self.goal[0] - self.x, self.goal[1] - self.z
            far = sqrt(gx * gx + gz * gz)
            # the earth heaves along the way it is going
            self.rumble -= dt
            if self.rumble <= 0:
                self.rumble = 0.07
                game.particles.emit((self.x + uniform(-0.3, 0.3), 0.1, self.z + uniform(-0.3, 0.3)),
                                    (uniform(-1, 1), uniform(2, 4), uniform(-1, 1)), DIRT, uniform(0.08, 0.16), 0.5)
            if far < 1.0:
                self.come_up()
                return 0.0, 0.0
            return gx / far * T.MINER_TUNNEL_SPEED * self.quick, gz / far * T.MINER_TUNNEL_SPEED * self.quick
        if self.mode == 'dig':
            self.timer -= dt
            self.sink = 1 - max(self.timer, 0.0) / T.MINER_DIG
            if uniform(0, 1) < 30 * dt:
                game.particles.emit((self.x + uniform(-0.5, 0.5), self.y + 0.1, self.z + uniform(-0.5, 0.5)),
                                    (uniform(-2, 2), uniform(3, 6), uniform(-2, 2)), DIRT, uniform(0.1, 0.18), 0.6)
            if self.timer <= 0:
                self.go_under()
            return 0.0, 0.0

        # above ground
        self.timer -= dt
        level = self.level_with(player)
        if self.wind > 0:
            self.wind -= dt
            if self.wind <= 0:
                self.swing = SWING_TIME
                if self.attack is None:
                    self.hack(nx, nz, distance, level, player)
                else:
                    self.throw(self.attack, player)
            return 0.0, 0.0
        if self.timer <= 0:
            self.mode = 'dig'
            self.timer = T.MINER_DIG
            self.dig_hole()
            return 0.0, 0.0
        if self.hit_cooldown <= 0:
            if distance < T.MINER_REACH * self.reach and level:
                self.attack = None
                self.wind = T.MINER_WINDUP
                self.hit_cooldown = T.MINER_COOLDOWN
                return 0.0, 0.0
            if distance < 45 and self.sees(player):
                self.attack = choice(tuple(T.MINER_THROWS))
                self.wind = T.MINER_WINDUP
                self.hit_cooldown = T.MINER_THROW_EVERY * uniform(0.8, 1.2)
                return 0.0, 0.0
        if distance < T.MINER_REACH * self.reach * 0.8:
            return 0.0, 0.0
        hx, hz = self.steer(nx, nz, dt, others)
        speed = T.MINER_SPEED * self.pace
        return hx * speed, hz * speed

    def come_up(self):
        """Out of the floor in a shower of earth, and into the air."""
        game = self.game
        self.mode = 'surface'
        self.hidden = False
        self.entity.enabled = True
        self.pick.enabled = True        # a new one, if the last was thrown
        self.sink = 0.0
        self.timer = uniform(*T.MINER_SURFACE)
        self.hit_cooldown = T.MINER_EMERGE
        self.y = game.map.ground_height(self.x, self.z, 0.5)
        self.dig_hole()
        self.hop(0.0, 0.0, 9.0)
        game.particles.burst((self.x, self.y + 0.3, self.z), DIRT, count=30, speed=8, size=0.12, life=0.6, up=5, white=0)

    def dig_hole(self):
        self.hole.position = (self.x, self.y + 0.04, self.z)
        self.hole.scale = 2.2 * self.size
        self.hole.enabled = True
        self.hole_time = T.MINER_HOLE_TIME
        away = (self.game.player.centre - self.centre).length()
        self.game.sfx.play('dig', volume=max(0.2, 1 - away / 45))

    def hack(self, nx, nz, distance, level, player):
        self.game.sfx.play('throw', volume=0.4, pitch=0.8)
        if distance < T.MINER_REACH * self.reach * 1.3 and level and player.invulnerable <= 0:
            if self.strike(player, T.MINER_PICK_DAMAGE, nx, nz, 11.0 * self.size):
                self.game.sfx.play('punch')

    def throw(self, what, player):
        damage, speed, gravity = T.MINER_THROWS[what]
        hand = Vec3(self.x, self.y + (self.HEIGHT + 0.3) * self.size, self.z)
        flight = max((player.centre - hand).length() / speed, 0.3)
        target = player.centre + Vec3(player.vel.x, 0, player.vel.z) * (flight * T.MARKER_LEAD)
        tint = NEON if self.green else {'pick': IRON, 'rock': STONE, 'crystal': choice((CYAN, MAGENTA, AMBER))}[what]
        # a green one throws pale things washed neon; a golden one throws its gold pick
        kind = 'shard' if what == 'crystal' else what + ('_pale' if self.green else '_gold' if self.gold and what == 'pick'
                                                          else '')
        self.game.enemies.throw(self, hand, lob(hand, target, speed, gravity), tint,
                                kind=kind, damage=damage, gravity=gravity,
                                scale=1.6 if what == 'crystal' else 1.0, tinted=self.green or what == 'crystal',
                                sound='chime' if what == 'crystal' else 'splat')
        if what == 'pick':
            self.pick.enabled = False       # it has another by the time it has dug down and up again

    def convert(self, role, seconds, **numbers):
        super().convert(role, seconds, **numbers)
        self.mode = 'surface'
        self.sink = 0.0

    def stagger(self, seconds):
        super().stagger(seconds)
        if self.mode == 'dig' and seconds > 0:
            self.mode = 'surface'       # knocked out of its digging: it has to start again
            self.sink = 0.0
            self.timer = 0.5

    def retire(self):
        super().retire()
        self.hole.enabled = False

    def update(self, dt, player, arena, others):
        super().update(dt, player, arena, others)
        if self.hole.enabled:
            self.hole_time -= dt
            if self.hole_time < 1:
                self.hole.scale = max(0.01, 2.2 * self.size * self.hole_time)
            if self.hole_time <= 0:
                self.hole.enabled = False

    def draw(self, nx, nz):
        if self.hidden:
            return
        super().draw(nx, nz)
        if self.mode == 'dig':
            self.entity.y = self.y - self.sink * self.HEIGHT * self.size * MODEL_SCALE

    def arm_pose(self, swing):
        if self.mode == 'dig':
            return -150 + 80 * sin(self.age * 30)       # hacking at the floor
        if self.wind > 0:
            return -200 * (1 - self.wind / T.MINER_WINDUP)
        if self.swing > 0:
            return -40 - 160 * self.swing / SWING_TIME
        return swing


KINDS = (Monkey, Golem, Miner)
SHOTS = {'shard': shard_model, 'rock': rock_model, 'pick': pick_model,
         'rock_pale': lambda: rock_model(PALE, PALE_SHADE), 'pick_pale': lambda: pick_model(PALE, PALE_SHADE),
         'pick_gold': lambda: pick_model(GOLD_SUIT, GOLD_TRIM)}
