"""What every enemy is: a body that runs, falls, gets shoved and gets hurt, and the things they throw.

A species is a subclass of `Enemy` in one of the modules beside this one. It says how big it is and
where its limbs hang, builds its own meshes in `models`, and decides what to do each frame in `act`.
Add a species by writing the class and listing it in its module's `KINDS`.

Green ones can be parried by the katana (see game/katana.py): they throb, and wear something neon
green. Some are special: a glowing one drops chips; a golden one drops chips and a key
(game/pickups.py). Any of them can be set on fire, poisoned or chilled, and a few weapons turn
one into an ally that fights or heals for the player for a while.
"""
from math import atan2, cos, degrees, pi, sin, sqrt
from random import choice, uniform

from panda3d.core import TransparencyAttrib
from ursina import Entity, Mesh, Vec3, color, raycast

from data import tuning as T
from fx.shaders import Look
from fx.toon import barrel, box, build, burst_mesh, dashed_ring, halo_mesh, loft, placed
from ui.font import Label

OUTLINE = 0.03
MODEL_SCALE = 0.9
BODY_RADIUS = 0.45          # kept clear of the wall and the pillars
SPAWN_TIME = 0.35
SWING_TIME = 0.2            # the arm stays out this long after a punch or a throw
DEATH_TIME = 2 / 60         # a killed body stays two frames, white, before it bursts
STAR_SPIN = 260             # degrees a second the stars round a stunned head go round

GREY = color.hsv(220, 0.14, 0.5)
GOLD = color.hsv(42, 0.75, 1)
RED = color.hsv(355, 0.7, 0.92)
BLUE = color.hsv(218, 0.68, 0.92)
GREEN = color.hsv(T.GREEN_HUE, 0.7, 0.95)
NEON = color.hsv(T.GREEN_HUE, 0.85, 1)      # what a parryable enemy wears, whatever its own colour
GOLD_SUIT = color.hsv(46, 0.72, 1)
GOLD_TRIM = color.hsv(28, 0.85, 0.95)
GLOW_HALO = color.hsv(185, 0.55, 1)
GOLD_HALO = color.hsv(46, 0.8, 1)
BOSS_HALO = color.hsv(345, 0.75, 1)
SPARKLE_EVERY = 0.05
# the colour a converted enemy is washed in, and its halo: a healer is pink, not the gold of a golden one
ALLY_TINTS = {'fighter': (0.62, 0.4, 1.0), 'healer': (1.0, 0.7, 0.86)}
ALLY_HALOS = {'fighter': color.hsv(275, 0.7, 1), 'healer': color.hsv(330, 0.45, 1)}
FROST = color.hsv(195, 0.45, 1)
FIRE = (1, 0.55, 0.15, 1)
VENOM = (0.7, 0.36, 1, 1)                   # purple: green is kept for what can be parried
# what the toon shader washes a body in (fx/shaders.py): rgb, then how strongly
FIRE_TINT = (1.0, 0.5, 0.12)
VENOM_TINT = (0.66, 0.3, 1.0)
COLD_TINT = (0.6, 0.86, 1.0)
ICE_TINT = (0.88, 0.97, 1.0)
GLOW_TINT = (0.35, 0.95, 1.0)
BOSS_TINT = (1.0, 0.3, 0.45)
GOLD_TONE = (1.0, 0.76, 0.2)
ICE = (0.72, 0.92, 1.0)
STAR = color.Color(1.0, 0.9, 0.3, 1)


def about_face(parts):
    return [(placed(shape, yaw=180), colour) for shape, colour in parts]


def fused(parts, details=(), outline=OUTLINE):
    """Outlined solids, plus small flat details that would drown in an outline of their own.
    Bodies are drawn facing +z but baked facing -z: shading is fixed in the mesh, and an enemy
    always faces the player, so its front has to be the side the light falls on. A small kind
    passes a thicker `outline`, so that drawn small its rim still shows."""
    mesh = build(about_face(parts), outline)
    if not details:
        return mesh
    flat = build(about_face(details), 0)
    return Mesh(vertices=mesh.vertices + flat.vertices, colors=mesh.colors + flat.colors, mode='triangle', static=True)


def clone(mesh):
    """A mesh belongs to one entity, so every enemy gets its own copy."""
    return Mesh(vertices=mesh.vertices, colors=mesh.colors, mode='triangle', static=True)


def overshoot(t):
    """0 to 1, going a little past 1 and back: something popping into being."""
    t = min(max(t, 0.0), 1.0) - 1
    return 1 + 2.70158 * t ** 3 + 1.70158 * t ** 2


def ice_model(height):
    """A block of ice round a body `height` tall: a faceted crystal, wider at the middle."""
    def ring(radius, y, sides=6):
        return [(sin(2 * pi * (i + 0.5) / sides) * radius, y, cos(2 * pi * (i + 0.5) / sides) * radius)
                for i in range(sides)]
    return build([(loft([ring(0.58, 0.0), ring(0.72, height * 0.55), ring(0.52, height * 1.05),
                         [(0.0, height * 1.2, 0.0)]]), ICE)], OUTLINE)


def crown_model():
    """A miniboss's crown: a gold band with five points and a red gem under each, standing on its head."""
    ruby = color.hsv(350, 0.8, 0.95)
    parts = [(placed(barrel(0.34, -0.09, 0.09, sides=10), pitch=-90), GOLD_SUIT)]
    for i in range(5):
        a = 2 * pi * i / 5
        x, z = sin(a) * 0.3, cos(a) * 0.3
        across, out = (cos(a), -sin(a)), (sin(a), cos(a))
        foot = [(x + across[0] * u * 0.09 + out[0] * v * 0.05, 0.06, z + across[1] * u * 0.09 + out[1] * v * 0.05)
                for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        parts.append((loft([foot, [(x, 0.4, z)]]), GOLD_SUIT))
        parts.append((box((0.08, 0.08, 0.08), (sin(a) * 0.35, -0.01, cos(a) * 0.35)), ruby))
    return build(parts, OUTLINE)


class Enemy:
    """Plain object; the manager (game/enemies.py) drives it."""

    kind = ''
    stripe = RED                # sparks and confetti
    SCALE = 1.0                 # times the size every enemy draws for itself
    HP = 1.0                    # times what its size would give it
    HEIGHT = 2.0                # of one of ordinary size
    CENTRE = 1.0                # middle of the body above the feet
    RADIUS = T.ASTRO_HIT_RADIUS     # sphere round the middle, for bullets, blasts and blades
    SHOULDER = (0.53, 1.5)      # x and y of the arm pivots
    HIP = (0.2, 0.8)
    PARRY = True                # can come in green
    DOOR = True                 # comes in through one of the map's entries
    DROPS = True                # can be the glowing or the golden one

    @classmethod
    def models(cls, green, gold):
        """{'body', 'arm_left', 'arm_right', 'leg'}: the pieces of one, standing at the origin."""
        raise NotImplementedError

    def __init__(self, game, green, models, gold=False):
        self.game = game
        self.green = green      # green ones can be parried, and hit harder when they are not
        self.gold = gold        # always spawned as the golden special
        self.colour = GOLD_SUIT if gold else GREEN if green else self.stripe
        self.alive = False
        self.special = None     # 'glow' or 'gold': what each drops is in Session.drop
        self.ally = None        # 'fighter' or 'healer' once a weapon has turned it
        # nothing an enemy is made of updates itself (the manager moves it), so the engine skips it all
        self.entity = Entity(model=clone(models['body']), enabled=False, ignore=True)
        # the meshes face -z (see `fused`), so the enemy's own left is +x
        self.arm_left = self.limb(models['arm_left'], self.SHOULDER[0], self.SHOULDER[1])
        self.arm_right = self.limb(models['arm_right'], -self.SHOULDER[0], self.SHOULDER[1])
        self.leg_left = self.limb(models['leg'], self.HIP[0], self.HIP[1])
        self.leg_right = self.limb(models['leg'], -self.HIP[0], self.HIP[1])
        middle = self.middle
        # a glow in hard steps behind a special one, and a ring of dashes turning under its feet
        self.halo = Entity(parent=self.entity, model=halo_mesh(), billboard=True, y=middle + 0.15, z=0.3,
                           enabled=False, ignore=True)
        self.halo.setTransparency(TransparencyAttrib.MAlpha)
        self.halo.setDepthWrite(False)
        self.halo.setBin('transparent', 5)
        self.ring = Entity(parent=self.entity, model=dashed_ring(), double_sided=True, enabled=False, ignore=True,
                           y=middle - self.HEIGHT / 2 + 0.06)
        self.look = Look(self.entity)       # the toon shader's flash and tints, on the whole body
        self.stars = None       # round its head while stunned, made the first time
        self.shell = None       # the ice it stands frozen in, made the first time
        self.crown = None       # a miniboss's, made the first time
        self.tag = None         # the words over an ally's head, made the first time it is turned
        self.size = 1.0
        self.hidden = False
        self.aerial = False
        self.boss = None        # the Boss it is, for a miniboss
        self.might = 1.0        # times the damage its blows and throws do
        self.quick = 1.0        # times as fast as its kind thinks and acts

    MIDDLE = None               # where the middle of the body is in its own meshes, if not CENTRE
    DEATH = ('suit', 'hurt')    # the pixel looks it bursts into: its body, and a touch of its colour

    @property
    def middle(self):
        return self.CENTRE if self.MIDDLE is None else self.MIDDLE

    def limb(self, mesh, x, y):
        return Entity(parent=self.entity, model=clone(mesh), position=(x, y, 0), ignore=True)

    def death_looks(self):
        if self.special == 'gold':
            return 'gold', 'white'
        if self.green:
            return self.DEATH[0], 'neon'
        return self.DEATH

    def spawn(self, x, z, special=None, hp_scale=1.0, size=None):
        self.alive = True
        self.special = 'gold' if self.gold else special
        self.ally = None
        self.boss = None
        self.might = self.quick = 1.0
        self.x, self.y, self.z = x, 0.0, z
        self.vx = self.vy = self.vz = 0.0
        self.size = size or uniform(*(T.GOLD_SIZE if self.gold else T.ASTRO_SIZE)) * self.SCALE
        self.radius = self.RADIUS * self.size
        self.reach = (1 + self.size) / 2        # arms grow with the body, but not as fast
        self.pace = self.size ** -0.5           # small ones are quicker
        self.hp = self.max_hp = (T.ASTRO_HP * hp_scale * (T.GOLD_HP if self.gold else 1) * self.HP
                                 * self.size ** 1.5)
        self.hop_timer = uniform(*T.HOP_EVERY)
        self.burn = self.burn_time = 0.0        # damage a second, and how long is left
        self.poison = self.poison_time = 0.0
        self.slow = self.slow_time = 0.0        # share of its speed lost to cold, and how long is left
        self.iced = False                       # already frozen solid once in this chill
        self.sparkle = 0.0
        self.grounded = True
        self.hidden = False     # out of reach of everything: a miner under the ground
        self.aerial = False     # held up by something other than the ground: no running, no falling
        self.pause = SPAWN_TIME + uniform(0, 0.3)
        self.spawning = SPAWN_TIME
        self.flash = 0.0
        self.squash = 0.0
        self.squash_speed = 0.0     # squash springs back past still and settles
        self.dead_time = 0.0        # the moment a killed body is still seen, white
        self.fx_timer = 0.0         # until the next pixel of fire or poison comes off it
        self.hit_cooldown = 0.0     # until the next blow or throw
        self.wind = 0.0             # counts down to the blow while the arm is drawn back
        self.swing = 0.0
        self.stun = 0.0
        self.age = 0.0
        self.stride = uniform(0, 6)
        self.rethink = 0.0
        self.heading = (0.0, 0.0)
        self.look.forget()
        self.entity.enabled = True
        if self.tag is not None:
            self.tag.enabled = False
        if self.crown is not None:
            self.crown.enabled = False
        self.mark(GOLD_HALO if self.gold else GLOW_HALO if self.special else None)

    @property
    def centre(self):
        return Vec3(self.x, self.y + self.CENTRE * self.size, self.z)

    def ignite(self, per_second, seconds):
        """Set on fire. A hotter or longer fire replaces the one already burning."""
        self.burn = max(self.burn if self.burn_time > 0 else 0.0, per_second)
        self.burn_time = max(self.burn_time, seconds)

    def envenom(self, per_second, seconds):
        self.poison = max(self.poison if self.poison_time > 0 else 0.0, per_second)
        self.poison_time = max(self.poison_time, seconds)

    def chill(self, slow, seconds, freeze=False):
        """Slow it down. With `freeze`, one that was already slowed stands frozen for a moment, once."""
        again = self.slow_time > 0
        self.slow = min(0.9, max(self.slow if again else 0.0, slow))
        self.slow_time = max(self.slow_time, seconds)
        if freeze and again and not self.iced:
            self.iced = True
            self.stagger(T.FREEZE_TIME)
            self.game.popups.show(self.centre + Vec3(0, 1.2 * self.size, 0), 'FROZEN!', FROST, size=1.4)

    def mark(self, tint, halo=True, ring=1.6):
        """Show a special one by a halo behind it and a ring under it in `tint`, or neither (None)."""
        self.halo.enabled = tint is not None and halo
        self.ring.enabled = tint is not None
        if tint is not None:
            self.halo.color = tint
            self.ring.color = tint
            self.ring.scale = ring

    def make_boss(self, boss):
        """Turn this giant into a miniboss: `boss.hp` times the health its size gave it, as fast
        as `boss.speed` times one of ordinary size, its blows and throws `boss.power` as hard.
        It wears a crown, and a wide red ring turns under it."""
        self.boss = boss
        self.special = None
        self.mark(BOSS_HALO, halo=False, ring=2.1)
        if self.crown is None:
            self.crown = Entity(parent=self.entity, model=crown_model(), y=self.middle + self.HEIGHT / 2 + 0.12,
                                ignore=True)
        self.crown.enabled = True
        self.pace = self.quick = boss.speed
        self.might = boss.power
        self.hp = self.max_hp = self.max_hp * boss.hp

    def convert(self, role, seconds, heal=0.0, punch=T.ALLY_DAMAGE, reach=T.ALLY_HEAL_RADIUS):
        """Change sides. The manager moves it out of the enemies: see Enemies.convert."""
        self.stagger(0)
        self.release()
        self.ally = role
        self.ally_time = seconds
        self.heal_rate = heal
        self.heal_reach = reach
        self.ally_damage = punch
        if self.tag is None:
            self.tag = Label(parent=self.entity, text='', origin=(0, 0), y=self.HEIGHT + 0.9, scale=14, billboard=True)
        self.tag.enabled = True
        self.tag_shown = None
        self.special = None
        self.hp = self.max_hp
        self.burn_time = self.poison_time = self.slow_time = 0.0
        self.pause = self.hit_cooldown = 0.0
        self.mark(ALLY_HALOS[role])

    def release(self):
        """Let go of whatever is holding it up: from here on it is on foot like anyone else."""
        if self.aerial:
            self.aerial = False
            self.grounded = False

    def retire(self):
        """Dead, dismissed or cleared away: hide whatever it owns besides its body."""
        self.entity.enabled = False

    def died(self):
        """Killed, and already counted: whatever its death sets off."""

    def update(self, dt, player, arena, others):
        """`player` is whoever it is after: for an ally, the enemy it hunts or the player it follows."""
        self.flash -= dt
        self.hit_cooldown -= dt
        self.hop_timer -= dt
        self.slow_time -= dt
        if self.slow_time <= 0:
            self.iced = False
        self.spawning -= dt
        self.stun -= dt
        self.swing -= dt
        self.age += dt
        # a squash springs back, a little past still, and settles
        self.squash_speed += (-T.SQUASH_SPRING * self.squash - T.SQUASH_DAMPING * self.squash_speed) * dt
        self.squash += self.squash_speed * dt

        dx, dz = player.x - self.x, player.z - self.z
        distance = sqrt(dx * dx + dz * dz) or 0.001
        nx, nz = dx / distance, dz / distance

        if self.aerial:
            self.pause -= dt
            if self.pause <= 0 and self.stun <= 0:
                self.act(dt * self.quick, nx, nz, distance, player, others)
        elif self.grounded:
            self.pause -= dt
            wish = (0.0, 0.0)
            if self.pause <= 0 and self.stun <= 0:
                act = self.assist if self.ally else self.act
                wish = act(dt * self.quick, nx, nz, distance, player, others)
                if self.slow_time > 0:
                    wish = (wish[0] * (1 - self.slow), wish[1] * (1 - self.slow))
        if self.aerial:
            pass
        elif self.grounded:     # still, unless acting was a jump
            turn = min(1.0, self.grip() * dt)
            self.vx += (wish[0] - self.vx) * turn
            self.vz += (wish[1] - self.vz) * turn
            self.x += self.vx * dt
            self.z += self.vz * dt
            self.keep_in_bounds(arena)
            ground = arena.ground_height(self.x, self.z, self.y + 0.5)
            if ground < self.y - 0.6:
                self.grounded = False       # ran off an edge
            else:
                self.y = ground
            self.stride += sqrt(self.vx * self.vx + self.vz * self.vz) * dt * 1.6
        else:
            self.vy -= T.ASTRO_GRAVITY * dt
            self.x += self.vx * dt
            self.y += self.vy * dt
            self.z += self.vz * dt
            self.keep_in_bounds(arena)
            ground = arena.ground_height(self.x, self.z, self.y + 0.5)
            if self.vy <= 0 and self.y <= ground:
                self.y = ground
                self.vy = 0.0
                self.vx *= 0.5
                self.vz *= 0.5
                self.grounded = True
                self.squash = -0.3
                self.land(nx, nz, distance, player)

        if self.special == 'gold' and not self.hidden:
            self.sparkle -= dt
            if self.sparkle <= 0:
                self.sparkle = SPARKLE_EVERY
                a, h = uniform(0, 2 * pi), uniform(0.2, self.HEIGHT + 0.2) * self.size
                wide = 0.7 * self.size
                self.game.particles.emit((self.x + sin(a) * wide, self.y + h, self.z + cos(a) * wide),
                                         (0, uniform(0.5, 2), 0), choice(((1, 0.85, 0.3, 1), (1, 1, 1, 1))),
                                         uniform(0.04, 0.09), uniform(0.3, 0.6), gravity=0)
        if (self.burn_time > 0 or self.poison_time > 0) and not self.hidden:
            # fire licks up off it, poison bubbles off it, a pixel at a time
            self.fx_timer -= dt
            if self.fx_timer <= 0:
                self.fx_timer = T.STATUS_PIXEL_EVERY
                wide, tall = 0.45 * self.size, self.HEIGHT * self.size * MODEL_SCALE
                at = (self.x + uniform(-wide, wide), self.y + uniform(0.2, 0.9) * tall, self.z + uniform(-wide, wide))
                look = 'flame' if self.burn_time > 0 else 'poison'
                self.game.pixels.emit(at, (uniform(-0.3, 0.3), uniform(1.5, 3.2), uniform(-0.3, 0.3)), look,
                                      uniform(0.06, 0.11) * max(self.size, 0.7), uniform(0.4, 0.7),
                                      0 if look == 'flame' else 2, 7, gravity=-1.5, drag=1.0)
        self.draw(nx, nz)

    def grip(self):
        """How fast its velocity turns to where it wants to go."""
        return T.ASTRO_ACCEL

    def act(self, dt, nx, nz, distance, player, others):
        """Decide what to do this frame. Returns the velocity to run at."""
        return 0.0, 0.0

    def hop(self, vx, vz, up=T.ASTRO_JUMP):
        """Leave the ground at (vx, vz). An ordinary hop is the same height for all: none of them
        can jump far up."""
        self.vx, self.vz = vx, vz
        self.vy = up
        self.grounded = False
        self.squash = 0.3
        self.hop_timer = uniform(*T.HOP_EVERY)

    def land(self, nx, nz, distance, player):
        """Back on the ground after a hop, a fall or a shove."""

    def assist(self, dt, nx, nz, distance, target, others):
        """An ally's turn: punch the enemy it was sent after, or keep close to the player and,
        if it is a healer, mend them."""
        game = self.game
        player = game.player
        if target is player:
            if self.ally == 'healer' and distance < self.heal_reach and player.hp < T.PLAYER_HP:
                player.heal(self.heal_rate * dt)
                if uniform(0, 1) < 12 * dt:
                    game.particles.emit(player.centre + Vec3(uniform(-0.5, 0.5), -0.6, uniform(-0.5, 0.5)),
                                        (0, 2.5, 0), (0.6, 1, 0.5, 1), 0.07, 0.6, gravity=0)
            if distance < T.ALLY_FOLLOW:
                return 0.0, 0.0
        elif distance < T.ALLY_REACH * self.reach + target.radius - T.ASTRO_HIT_RADIUS:
            if self.hit_cooldown <= 0:
                self.hit_cooldown = T.ALLY_COOLDOWN
                self.swing = SWING_TIME
                # an ally's punch is seen in the ally's own colour, so it is not taken for a shot
                at = target.centre
                tint = ALLY_HALOS[self.ally]
                game.enemies.damage(target, self.ally_damage, (nx * 8, 4, nz * 8))
                game.popups.show(at + Vec3(0, 0.6, 0), str(round(self.ally_damage)), tint, size=1.5)
                game.particles.burst(at, tint, count=18, speed=9, size=0.08, life=0.4, white=0.3)
                game.sfx.play('punch', volume=0.8)
            return 0.0, 0.0
        hx, hz = self.steer(nx, nz, dt, others)
        return hx * T.ALLY_SPEED, hz * T.ALLY_SPEED

    def level_with(self, player):
        return -T.PLAYER_HEIGHT < self.y - player.y < self.HEIGHT * self.size

    def sees(self, player, origin=None):
        """Nothing solid between it and the player."""
        origin = origin or self.centre
        to = player.centre - origin
        distance = to.length()
        if distance < 1.0:
            return True
        hit = raycast(origin, to / distance, distance=distance - 0.6, ignore=(player,))
        return not hit.hit

    def strike(self, player, damage, nx, nz, knock, up=6.0):
        """Land a blow on the player, which a green one may have parried."""
        player.take_damage(damage * self.might, Vec3(nx * knock, up, nz * knock), source=self, green=self.green)
        return self.stun <= 0

    def steer(self, nx, nz, dt, others):
        """The way to run: along (nx, nz), but away from close neighbours so the pack spreads
        out. Looking at everyone is slow, so it is done a few times a second."""
        self.rethink -= dt
        if self.rethink <= 0:
            self.rethink = uniform(0.1, 0.18)
            for other in others:
                if other is self:
                    continue
                ox, oz = self.x - other.x, self.z - other.z
                gap = ox * ox + oz * oz
                if 0.0001 < gap < 9:
                    nx += ox / gap * 1.5
                    nz += oz / gap * 1.5
            length = sqrt(nx * nx + nz * nz) or 1.0
            self.heading = (nx / length, nz / length)
        return self.heading

    def keep_in_bounds(self, arena):
        r = sqrt(self.x * self.x + self.z * self.z)
        limit = arena.radius - BODY_RADIUS - 0.2
        if r > limit:
            self.x *= limit / r
            self.z *= limit / r
        for ox, oz, radius in arena.obstacles:
            dx, dz = self.x - ox, self.z - oz
            d = sqrt(dx * dx + dz * dz)
            reach = radius + BODY_RADIUS
            if 0.0001 < d < reach:
                self.x = ox + dx / d * reach
                self.z = oz + dz / d * reach

    def stagger(self, seconds):
        """Parried: no running and no attacking for a while."""
        self.stun = seconds
        self.wind = 0.0
        self.vx = self.vz = 0.0

    def shove(self, vx, vy, vz):
        self.release()
        self.vx += vx
        self.vz += vz
        self.vy = max(self.vy, 0.0) + vy
        self.grounded = False

    def arm_pose(self, swing):
        """Angle of the arm that punches or throws; `swing` is where running would put it."""
        return swing

    def draw(self, nx, nz):
        e = self.entity
        grow = 1.0 if self.spawning <= 0 else max(0.05, overshoot(1 - self.spawning / SPAWN_TIME))
        stretch = 1 + self.squash + (0 if self.grounded or self.aerial else max(-0.12, min(0.2, self.vy * 0.02)))
        wide = 1 / sqrt(max(stretch, 0.3))
        size = MODEL_SCALE * grow * self.size
        # straight onto the Panda3D node: Ursina's setters cost several times as much, forty times a frame
        e.setScale(size * wide, size * stretch, size * wide)
        e.setPos(self.x, self.y, self.z)
        e.setH(-degrees(atan2(nx, nz)) - 180)       # rotation_y: the face looks at the player
        self.pose()
        self.paint()

    def pose(self):
        if self.grounded:
            speed = sqrt(self.vx * self.vx + self.vz * self.vz)
            swing = sin(self.stride) * min(speed / 6, 1) * 38
        else:
            swing = 22      # legs apart in the air
        # limb angles are positive toward the back; the turned mesh needs them the other way.
        # setP(a) is rotation_x = -a, without Ursina's overhead (see draw)
        self.leg_left.setP(swing)
        self.leg_right.setP(-swing)
        self.arm_left.setP(-swing)
        self.arm_right.setP(self.arm_pose(swing))

    def paint(self):
        """The toon shader's inputs for this body (see fx/shaders.py), and what hangs about it."""
        look = self.look
        dying = self.dead_time > 0
        # a hit: two frames of white, then a moment half white; coming in, it starts white too
        if dying or self.flash > 0.035:
            flash = 1.0
        elif self.flash > 0:
            flash = 0.55
        elif self.spawning > SPAWN_TIME * 0.45:
            flash = 0.7
        else:
            flash = 0.0
        look.set('flash', flash)
        frozen = self.iced and self.stun > 0
        on = sin(self.age * 12) > 0         # tints step between two strengths, never glide
        if self.ally:
            wash = ALLY_TINTS[self.ally]
            status = (*wash, 0.2 if self.ally_time < 3 and sin(self.age * 22) > 0 else 0.5)    # blinks before it goes
        elif frozen:
            status = (*ICE_TINT, 0.8)
        elif self.burn_time > 0:
            status = (*FIRE_TINT, 0.72 if sin(self.age * 26) > 0 else 0.48)
        elif self.poison_time > 0:
            status = (*VENOM_TINT, 0.5 if on else 0.36)
        elif self.slow_time > 0:
            status = (*COLD_TINT, 0.55)
        elif self.boss is not None:
            status = (*BOSS_TINT, 0.16)
        elif self.special == 'glow':
            status = (*GLOW_TINT, 0.55 if sin(self.age * 5) > 0 else 0.3)
        else:
            status = (0.0, 0.0, 0.0, 0.0)
        look.set('status', *status)
        gold = self.special == 'gold' and not self.ally
        # gold under a tint would go muddy: with a fire, poison or cold on it, the tint shows instead
        shine = (0.85 if sin(self.age * 6) > 0 else 0.7) if status[3] == 0 else 0.3
        look.set('gold', *((*GOLD_TONE, shine) if gold else (0.0, 0.0, 0.0, 0.0)))
        look.set('dull', 0.45 if self.stun > 0 and not frozen and not dying else 0.0)
        # a green one's green parts flare, and only those: it says "parry me" without hiding anything
        look.set('neon', 0.6 if self.green and not self.ally and sin(self.age * 7) > 0.2 else 0.0)
        if self.halo.enabled:
            self.halo.scale = 3.3 if sin(self.age * 5) > 0 else 3.0
        if self.ring.enabled:
            self.ring.setHpr(self.age * 70, -90, 0)
        self.paint_stun(frozen)

    def paint_stun(self, frozen):
        """Stars round its head while it is stunned; ice round it while it is frozen."""
        stunned = self.stun > 0 and not frozen and self.dead_time <= 0
        if stunned and self.stars is None:
            self.stars = Entity(parent=self.entity, y=self.middle + self.HEIGHT / 2 + 0.3, ignore=True)
            for i in range(3):
                Entity(parent=self.stars, model=burst_mesh(5, 0.45), billboard=True, double_sided=True, color=STAR,
                       scale=0.16, position=(sin(i * 2.09) * 0.42, 0, cos(i * 2.09) * 0.42), ignore=True)
        if self.stars is not None:
            self.stars.enabled = stunned
            if stunned:
                self.stars.setH(self.age * STAR_SPIN)
        if frozen and self.shell is None:
            self.shell = Entity(parent=self.entity, model=ice_model(self.HEIGHT), y=self.middle - self.HEIGHT / 2,
                                color=color.Color(1, 1, 1, 0.6), ignore=True)
            self.shell.setTransparency(TransparencyAttrib.MAlpha)
            self.shell.setDepthWrite(False)
            self.shell.setBin('transparent', 4)
        if self.shell is not None:
            self.shell.enabled = frozen

class Shot:
    """Something thrown. It is one of `game.projectiles`, so a green one can be parried by the
    katana, which turns it `friendly` and sends it after whoever threw it."""

    def __init__(self, kind, mesh):
        self.kind = kind
        self.entity = Entity(model=mesh, enabled=False, ignore=True)
        self.look = Look(self.entity)
        self.live = False

    def launch(self, owner, position, velocity, ink, damage=T.MARKER_DAMAGE, gravity=T.MARKER_GRAVITY,
               knock=T.MARKER_KNOCK, spin=620, scale=1.0, tinted=True, sound='splat', on_hit=None, on_land=None):
        """`spin` is degrees a second end over end; without it the shot flies nose first.
        `on_hit(shot, point)` and `on_land(shot, point)` are told when it reaches the player or
        anything else, after its own damage and splash."""
        self.live = True
        self.owner = owner
        self.pos = Vec3(*position)
        self.vel = Vec3(*velocity)
        self.ink = ink
        self.green = owner.green
        self.friendly = False
        self.target = None
        self.damage = damage
        self.gravity = gravity
        self.knock = knock
        self.spin = spin
        self.sound = sound
        self.on_hit, self.on_land = on_hit, on_land
        self.life = T.MARKER_LIFE
        self.tumble = uniform(0, 360)
        self.entity.color = ink if tinted else color.white
        self.entity.scale = self.size = scale
        self.age = 0.0
        self.trail = 0.0
        self.entity.position = self.pos
        self.entity.enabled = True

    def reflect(self, speed, damage):
        """Parried. The katana has set `target` to the thrower, or None if they are gone."""
        self.damage = damage
        self.life = T.MARKER_LIFE
        self.on_hit = self.on_land = None
        back = self.target.centre - self.pos if self.target is not None else -self.vel
        self.vel = back.normalized() * speed

    def update(self, dt, game):
        """Returns False once it has landed."""
        self.life -= dt
        if self.friendly:
            # a parried shot flies flat out and follows the thrower wherever they run
            if self.target is not None and self.target.alive:
                self.vel = (self.target.centre - self.pos).normalized() * self.vel.length()
        else:
            self.vel.y -= self.gravity * dt
        step = self.vel * dt
        length = step.length()
        if length < 1e-5 or self.life <= 0:
            return self.finish()
        direction = step / length

        wall = raycast(self.pos, direction, distance=length + 0.1)
        reach = wall.distance if wall.hit else length
        if self.friendly:
            hits = game.enemies.ray_hits(self.pos, direction, reach)
            if hits:
                distance, enemy = hits[0]
                point = self.pos + direction * distance
                killed = game.enemies.damage(enemy, self.damage, (direction.x * 8, 5, direction.z * 8))
                game.on_hit(enemy, self.damage, point, killed)
                return self.splat(game, point)
        else:
            player = game.player
            body = Vec3(player.x, player.y + min(max(self.pos.y - player.y, 0.3), T.PLAYER_HEIGHT - 0.3), player.z)
            along = min(max((body - self.pos).dot(direction), 0.0), reach)
            point = self.pos + direction * along
            if (body - point).length() < T.MARKER_HIT_RADIUS:
                self.pos = point
                player.take_damage(self.damage, Vec3(direction.x * self.knock, 4, direction.z * self.knock),
                                   source=self, green=self.green)
                if self.friendly:       # parried just as it landed
                    return True
                if self.on_hit is not None:
                    self.on_hit(self, point)
                return self.splat(game, point, size=0.03)      # this close to the eye, big drops fill the screen
        if wall.hit:
            point = self.pos + direction * reach
            if self.on_land is not None and not self.friendly:
                self.on_land(self, point)
            return self.splat(game, point)

        self.pos += step
        e = self.entity
        e.position = self.pos
        self.age += dt
        # a green one throbs and leaves a neon trail, so it is plain it can be sent back; one that
        # was sent back trails sparks all the way home
        if self.green or self.friendly:
            beat = sin(self.age * 18) > 0
            self.look.set('neon', 0.7 if beat and not self.friendly else 0.0)
            e.scale = self.size * (1.15 if beat else 1.0)
            self.trail -= dt
            if self.trail <= 0:
                self.trail = 0.03
                game.pixels.emit(self.pos, (uniform(-0.5, 0.5), uniform(-0.2, 0.6), uniform(-0.5, 0.5)),
                                 'spark' if self.friendly else 'neon', 0.07 * self.size, 0.35, 1, 5, drag=2.0)
        e.rotation_y = degrees(atan2(self.vel.x, self.vel.z))
        if self.friendly or not self.spin:
            e.rotation_x = -degrees(atan2(self.vel.y, sqrt(self.vel.x ** 2 + self.vel.z ** 2)))    # nose first
        else:
            self.tumble += self.spin * dt
            e.rotation_x = self.tumble      # end over end
        return True

    def splat(self, game, point, size=0.11):
        game.particles.burst(point, self.ink, count=22, speed=7, size=size, life=0.7, up=2.5, white=0)
        if size > 0.05:     # not in the player's face
            game.pixels.scatter(point, 'neon' if self.green else 'white', count=10, speed=4, size=0.06, life=0.4,
                                gravity=10, up=2)
        away = (game.player.centre - point).length()
        game.sfx.play(self.sound, volume=max(0.15, min(1.0, 1.2 - away / 40)), pitch=uniform(0.85, 1.15))
        return self.finish()

    def finish(self):
        self.live = False
        self.entity.enabled = False
        return False


def lob(start, target, speed, gravity):
    """The velocity that throws something from `start` to land on `target`, covering the ground
    between at `speed`."""
    to = target - start
    flight = max(sqrt(to.x * to.x + to.z * to.z) / speed, 0.3)
    return Vec3(to.x / flight, to.y / flight + 0.5 * gravity * flight, to.z / flight)
