"""The katana: one key, one slash. It cuts whatever is in front of you and parries anything green.

How other code makes its attacks parryable:

- An enemy needs `green` (True for the parryable ones), `centre` and `stagger(seconds)`, and must
  pass `source=self, green=self.green` to `player.take_damage`.
- Projectiles are read from `game.projectiles`, any iterable of objects with `pos`, `vel`,
  `green` and `owner`. A parried one is handed back to whoever fired it: the katana sets
  `target = owner` and `friendly = True`, then calls `reflect(speed, damage)` if the projectile
  has one, or turns its velocity round itself. A tracking projectile must follow `target`, so
  after a parry it hunts its sender instead of the player.
"""
from math import cos, pi, radians, sin

from ursina import Entity, Mesh, Vec3, camera, color, destroy, time

from data import tuning as T
from data.controls import pressed
from fx.toon import barrel, box, build, slab
from game.body import arm, stripe
from game.weapons import hit_pitch

STEEL = color.hsv(205, 0.1, 0.93)
EDGE = color.hsv(190, 0.08, 1)
BRASS = color.hsv(44, 0.6, 0.93)
WRAP = color.hsv(230, 0.25, 0.3)
CREAM = color.hsv(45, 0.18, 0.97)
PARRY_GREEN = color.hsv(T.GREEN_HUE, 0.7, 1)
HILT = Vec3(0.12, -0.3, 0.42)       # where the hand holds it, in camera space
SWING = 68                          # degrees to each side of straight ahead
STOW_TIME = 0.16                    # the gun takes this long to come back up


def blade_model():
    return build([
        (slab([(0.1, -0.024), (0.1, 0.022), (0.72, 0.034), (0.72, -0.012)], 0.012), STEEL),
        (slab([(0.72, -0.012), (0.72, 0.034), (0.93, 0.062)], 0.012), STEEL),                # tip
        (slab([(0.1, -0.025), (0.1, -0.01), (0.72, 0.002), (0.72, -0.013)], 0.015), EDGE),   # cutting edge
        (box((0.022, 0.056, 0.035), (0, 0, 0.105)), BRASS),                                  # collar
        (barrel(0.055, 0.068, 0.088, sides=8), BRASS),                                       # guard
        (box((0.03, 0.042, 0.26), (0, 0, -0.062)), WRAP),                                    # handle
        *[(box((0.035, 0.018, 0.022), (0, 0, z)), CREAM) for z in (-0.15, -0.09, -0.03, 0.03)],
        (box((0.036, 0.048, 0.022), (0, 0, -0.2)), BRASS),                                   # pommel
    ])


def trail_mesh(steps=14):
    """Flat crescent swept by the blade: solid at the leading end, clear at the tail."""
    vertices, colours = [], []
    for i in range(steps):
        a0, a1 = (radians(-SWING + 2 * SWING * j / steps) for j in (i, i + 1))
        f0, f1 = i / steps, (i + 1) / steps
        inner = [(sin(a) * 0.45, 0, cos(a) * 0.45) for a in (a0, a1)]
        outer = [(sin(a) * 0.95, 0, cos(a) * 0.95) for a in (a0, a1)]
        vertices += [inner[0], outer[0], outer[1], inner[0], outer[1], inner[1]]
        colours += [(1, 1, 1, f0 * 0.3), (1, 1, 1, f0), (1, 1, 1, f1),
                    (1, 1, 1, f0 * 0.3), (1, 1, 1, f1), (1, 1, 1, f1 * 0.3)]
    return Mesh(vertices=vertices, colors=colours, mode='triangle', static=True)


class Katana(Entity):
    def __init__(self, game):
        super().__init__()
        self.game = game
        self.hand = Entity(parent=camera, position=HILT, rotation_z=-18, enabled=False)
        self.blade = Entity(parent=self.hand, model=blade_model(), rotation_z=90)   # held flat
        self.grip = None
        self.repaint(None)
        self.trail = Entity(parent=self.hand, model=trail_mesh(), double_sided=True)
        self.age = 99.0         # seconds since the slash began
        self.cooldown = 0.0
        self.side = 1           # slashes alternate: 1 sweeps right to left
        self.struck = set()     # what this slash has already cut or parried

    def repaint(self, hue):
        """The glove and sleeve on the handle, with the cuff in the player's colour."""
        if self.grip is not None:
            destroy(self.grip)
        self.grip = Entity(parent=self.hand, model=build(arm((0, 0, -0.06), (0.1, -0.34, -0.5), stripe(hue))))

    @property
    def busy(self):
        return self.age < T.KATANA_SLASH_TIME

    @property
    def parrying(self):
        return self.age < T.KATANA_PARRY_WINDOW

    @property
    def stow(self):
        """0-1: how far the gun should be lowered out of the way."""
        return max(0.0, min(1.0, 1 - (self.age - T.KATANA_SLASH_TIME) / STOW_TIME))

    def input(self, key):
        if pressed(key, T.KEY_KATANA) and self.cooldown <= 0:
            self.slash()

    def slash(self):
        self.age = 0.0
        self.cooldown = T.KATANA_COOLDOWN
        self.side = -self.side
        self.struck.clear()
        self.trail.scale_x = self.side
        self.trail.color = color.white
        self.hand.enabled = True
        self.game.sfx.play('slash')
        self.game.juice.shake(T.SHAKE_SLASH)
        self.cut()

    # --- frame ---

    def update(self):
        dt = min(time.dt, T.MAX_DT)
        self.cooldown -= dt
        self.age += dt
        if not self.hand.enabled:
            return
        if self.parrying:
            self.cut()      # things that walk or fly into the blade while it is still moving
        t = self.age / T.KATANA_SLASH_TIME
        if t >= 1:
            self.hand.enabled = False
            return
        swept = 1 - (1 - t) ** 3
        self.blade.rotation_y = self.side * SWING * (1 - 2 * swept)
        self.blade.z = 0.1 * sin(pi * t)
        tint = self.trail.color
        self.trail.color = color.Color(tint[0], tint[1], tint[2], (1 - t) ** 1.5)

    # --- hitting ---

    def in_cone(self, point, reach):
        to = point - camera.world_position
        distance = to.length()
        if distance > reach:
            return False
        return distance < 0.01 or to.dot(camera.forward) / distance >= cos(radians(T.KATANA_CONE / 2))

    def cut(self):
        game = self.game
        for enemy in list(game.enemies.alive):
            if enemy not in self.struck and not enemy.hidden and self.in_cone(enemy.centre, T.KATANA_REACH + enemy.radius):
                self.strike(enemy)
        for shot in list(getattr(game, 'projectiles', ())):
            if (shot not in self.struck and getattr(shot, 'green', False) and not getattr(shot, 'friendly', False)
                    and self.in_cone(Vec3(*shot.pos), T.KATANA_PROJECTILE_REACH)):
                self.send_back(shot)

    def strike(self, enemy):
        """Melee damage for anything; a green enemy is parried on top of it."""
        game = self.game
        self.struck.add(enemy)
        green = getattr(enemy, 'green', False)
        point = Vec3(*enemy.centre)
        away = point - camera.world_position
        away = Vec3(away.x, 0, away.z)
        away = away.normalized() if away.length() > 0.01 else Vec3(*camera.forward)
        amount = T.KATANA_DAMAGE * game.player.rush.damage_multiplier
        if green:
            amount *= T.KATANA_PARRY_DAMAGE
            enemy.stagger(T.KATANA_STUN)
        knock = T.KATANA_KNOCK * (1.6 if green else 1)
        killed = game.enemies.damage(enemy, amount, (away.x * knock, 4, away.z * knock))
        game.on_hit(enemy, amount, point, killed)
        game.hud.hit_marker(killed)
        game.sfx.play('hit', volume=0.8, pitch=hit_pitch(amount) * 0.85)
        if green:
            self.parried(point)

    def send_back(self, shot):
        """Return a projectile to its sender, even one that was tracking the player."""
        self.struck.add(shot)
        owner = getattr(shot, 'owner', None)
        if owner is not None and not getattr(owner, 'alive', True):
            owner = None
        shot.target = owner
        shot.friendly = True
        velocity = Vec3(*shot.vel)
        speed = velocity.length() * T.KATANA_REFLECT_SPEED
        if hasattr(shot, 'reflect'):
            shot.reflect(speed, T.KATANA_REFLECT_DAMAGE)
        else:
            back = Vec3(*owner.centre) - Vec3(*shot.pos) if owner is not None else -velocity
            shot.vel = back.normalized() * speed
            shot.damage = T.KATANA_REFLECT_DAMAGE
        self.parried(Vec3(*shot.pos), projectile=True)

    def parried(self, point, projectile=False):
        self.trail.color = PARRY_GREEN
        self.game.on_parry(point, projectile)

    def try_parry(self, source):
        """Called when a green hit is about to land on the player. True cancels the hit."""
        if not self.parrying:
            return False
        if source is None:
            return True
        if source in self.struck:
            return True
        ahead = Vec3(*getattr(source, 'centre', getattr(source, 'pos', camera.world_position))) - camera.world_position
        ahead.y = 0
        forward = Vec3(camera.forward.x, 0, camera.forward.z)
        if ahead.length() > 0.3 and ahead.normalized().dot(forward.normalized()) < 0:
            return False    # it came from behind
        if hasattr(source, 'stagger'):
            self.strike(source)
        else:
            self.send_back(source)
        return True
