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

from ursina import Entity, Mesh, Vec3, color, raycast

from data import tuning as T
from fx.toon import build, placed
from ui.font import Label

OUTLINE = 0.03
MODEL_SCALE = 0.9
BODY_RADIUS = 0.45          # kept clear of the wall and the pillars
SPAWN_TIME = 0.35
SWING_TIME = 0.2            # the arm stays out this long after a punch or a throw
FLASH, DAZED = 3.0, 0.45    # brightness of a body that was just hit, or is stunned

GREY = color.hsv(220, 0.14, 0.5)
GOLD = color.hsv(42, 0.75, 1)
RED = color.hsv(355, 0.7, 0.92)
BLUE = color.hsv(218, 0.68, 0.92)
GREEN = color.hsv(T.GREEN_HUE, 0.7, 0.95)
NEON = color.hsv(T.GREEN_HUE, 0.85, 1)      # what a parryable enemy wears, whatever its own colour
GOLD_SUIT = color.hsv(46, 0.72, 1)
GOLD_TRIM = color.hsv(28, 0.85, 0.95)
GLOW_HALO = color.hsv(185, 0.55, 1, 0.6)
GOLD_HALO = color.hsv(46, 0.8, 1, 0.7)
SPARKLE_EVERY = 0.05
# the colour a converted enemy is washed in, and its halo
ALLY_TINTS = {'fighter': (0.62, 0.4, 1.0), 'healer': (1.0, 0.95, 0.5)}
ALLY_HALOS = {'fighter': color.hsv(275, 0.7, 1, 0.6), 'healer': color.hsv(52, 0.6, 1, 0.7)}
FROST = color.hsv(195, 0.45, 1)
FIRE = (1, 0.55, 0.15, 1)
VENOM = (0.5, 1, 0.3, 1)


def about_face(parts):
    return [(placed(shape, yaw=180), colour) for shape, colour in parts]


def fused(parts, details=()):
    """Outlined solids, plus small flat details that would drown in an outline of their own.
    Bodies are drawn facing +z but baked facing -z: shading is fixed in the mesh, and an enemy
    always faces the player, so its front has to be the side the light falls on."""
    mesh = build(about_face(parts), OUTLINE)
    if not details:
        return mesh
    flat = build(about_face(details), 0)
    return Mesh(vertices=mesh.vertices + flat.vertices, colors=mesh.colors + flat.colors, mode='triangle', static=True)


def clone(mesh):
    """A mesh belongs to one entity, so every enemy gets its own copy."""
    return Mesh(vertices=mesh.vertices, colors=mesh.colors, mode='triangle', static=True)


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
        self.entity = Entity(model=clone(models['body']), enabled=False)
        # the meshes face -z (see `fused`), so the enemy's own left is +x
        self.arm_left = self.limb(models['arm_left'], self.SHOULDER[0], self.SHOULDER[1])
        self.arm_right = self.limb(models['arm_right'], -self.SHOULDER[0], self.SHOULDER[1])
        self.leg_left = self.limb(models['leg'], self.HIP[0], self.HIP[1])
        self.leg_right = self.limb(models['leg'], -self.HIP[0], self.HIP[1])
        self.halo = Entity(parent=self.entity, model='quad', texture=game.enemies.halo_texture, billboard=True,
                           y=self.CENTRE + 0.15, enabled=False, ignore=True)
        self.halo.setDepthWrite(False)
        self.halo.setBin('transparent', 5)
        self.tag = None         # the words over an ally's head, made the first time it is turned
        self.size = 1.0
        self.hidden = False
        self.aerial = False
        self.boss = None        # the Boss it is, for a miniboss
        self.might = 1.0        # times the damage its blows and throws do
        self.quick = 1.0        # times as fast as its kind thinks and acts

    def limb(self, mesh, x, y):
        return Entity(parent=self.entity, model=clone(mesh), position=(x, y, 0))

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
        self.hit_cooldown = 0.0     # until the next blow or throw
        self.wind = 0.0             # counts down to the blow while the arm is drawn back
        self.swing = 0.0
        self.stun = 0.0
        self.age = 0.0
        self.stride = uniform(0, 6)
        self.rethink = 0.0
        self.heading = (0.0, 0.0)
        self.tint = None
        self.entity.enabled = True
        if self.tag is not None:
            self.tag.enabled = False
        self.halo.enabled = self.special is not None
        if self.special:
            self.halo.color = GOLD_HALO if self.gold else GLOW_HALO

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

    def make_boss(self, boss):
        """Turn this giant into a miniboss: `boss.hp` times the health its size gave it, as fast
        as `boss.speed` times one of ordinary size, its blows and throws `boss.power` as hard."""
        self.boss = boss
        self.special = None
        self.halo.enabled = False
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
        self.tint = None
        self.halo.color = ALLY_HALOS[role]
        self.halo.enabled = True

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
        self.squash *= max(0.0, 1 - 12 * dt)

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
        grow = 1.0 if self.spawning <= 0 else max(0.05, 1 - self.spawning / SPAWN_TIME)
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
        if self.flash > 0:
            tint = FLASH
        elif self.stun > 0:
            tint = DAZED
        elif self.green:
            tint = 0.85 + 0.3 * abs(sin(self.age * 7))     # green ones throb so they read as "parry me"
        else:
            tint = 1.0
        r = g = b = tint
        if self.ally:
            wash = ALLY_TINTS[self.ally]
            fading = 0.5 if self.ally_time < 3 and sin(self.age * 22) > 0 else 1.0     # blinks before it goes
            r, g, b = tint * wash[0] * fading, tint * wash[1] * fading, tint * wash[2] * fading
        elif self.special == 'gold':
            r = g = b = tint * (0.9 + 0.25 * abs(sin(self.age * 6)))
        elif self.special == 'glow':
            r = tint * (0.55 + 0.45 * abs(sin(self.age * 5)))       # washes to cyan and back
        if self.slow_time > 0:
            r, g, b = r * 0.5, g * 0.8, b * 1.2         # blue with cold
        if self.halo.enabled:
            self.halo.scale = 3.3 + 0.5 * sin(self.age * 5)
        if (r, g, b) != self.tint:
            self.tint = (r, g, b)
            self.entity.setColorScale(r, g, b, 1)       # on the node itself, so the limbs follow


class Shot:
    """Something thrown. It is one of `game.projectiles`, so a green one can be parried by the
    katana, which turns it `friendly` and sends it after whoever threw it."""

    def __init__(self, kind, mesh):
        self.kind = kind
        self.entity = Entity(model=mesh, enabled=False)
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
        self.entity.scale = scale
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
        e.rotation_y = degrees(atan2(self.vel.x, self.vel.z))
        if self.friendly or not self.spin:
            e.rotation_x = -degrees(atan2(self.vel.y, sqrt(self.vel.x ** 2 + self.vel.z ** 2)))    # nose first
        else:
            self.tumble += self.spin * dt
            e.rotation_x = self.tumble      # end over end
        return True

    def splat(self, game, point, size=0.11):
        game.particles.burst(point, self.ink, count=22, speed=7, size=size, life=0.7, up=2.5, white=0)
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
