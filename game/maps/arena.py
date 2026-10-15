"""What every map is: a round arena the rest of the game can ask things of.

A map is a subclass that builds its scenery and tells the arena what it built: where the raised
decks and the ramps up to them are, what ground enemies must run round, where enemies come in,
where a sniper can stand and what there is to hang from. Colliders are invisible boxes; what is
seen is baked from cartoon solids. Add a map by subclassing `Arena` and naming it in
game/maps/__init__.py.
"""
from collections import namedtuple
from math import atan2, cos, degrees, pi, radians, sin, sqrt, tan

from ursina import Entity, Mesh, MeshCollider, Vec3, color, time

from data import tuning as T
from fx.toon import barrel, build, fan, placed, shade, solid

OUTLINE = 0.08

# a raised floor: the part of a ring between two radii, `half_arc` degrees either side of `angle`
Deck = namedtuple('Deck', 'angle half_arc inner outer height')
# a slope running outward along `angle`, from the ground at `start` up to `height` at `end`
Ramp = namedtuple('Ramp', 'angle start end width height')


class Vine:
    """Something that hangs from a point overhead and swings: a pendulum whose tip is a handhold.
    `ax` and `az` are how far it leans (radians) with its tip toward +x and +z, and `vx` and `vz`
    how fast that is changing. While something holds it (`holder`), that moves it, not the map."""

    def __init__(self, entity, length, phase=0.0):
        self.entity = entity        # its pivot is the root; the vine hangs down its -y
        self.length = length
        self.phase = phase
        self.tip = Entity(parent=entity, y=-length)
        self.ax = self.az = self.vx = self.vz = 0.0
        self.holder = None

    def swing(self, dt, stiffness, damping, push=(0.0, 0.0)):
        """A step of a damped spring back to hanging straight down."""
        self.vx += (push[0] - stiffness * self.ax - damping * self.vx) * dt
        self.vz += (push[1] - stiffness * self.az - damping * self.vz) * dt
        self.ax = max(-T.VINE_MAX_LEAN, min(T.VINE_MAX_LEAN, self.ax + self.vx * dt))
        self.az = max(-T.VINE_MAX_LEAN, min(T.VINE_MAX_LEAN, self.az + self.vz * dt))
        # in Ursina's frame a pitch swings the tip toward +z and a roll toward -x
        self.entity.setHpr(0, degrees(self.az), -degrees(self.ax))

    def kick(self, vx, vz):
        """Set it swinging: `vx` and `vz` are how fast its tip is pushed, in m/s."""
        self.vx += vx / self.length
        self.vz += vz / self.length

    @property
    def root(self):
        return self.entity.world_position

    @property
    def end(self):
        return self.tip.world_position

    def below(self, distance):
        """The point `distance` on past the tip, along the line of the vine."""
        root, end = self.root, self.end
        return end + (end - root).normalized() * distance


def polar(radius, angle, y=0):
    """Angle in degrees, matching rotation_y: 0 is +z, 90 is +x."""
    a = radians(angle)
    return Vec3(radius * sin(a), y, radius * cos(a))


def wedge(r0, r1, a0, a1, y0, y1):
    """A slice of a ring between two radii and two angles, from y0 up to y1."""
    low = [tuple(polar(r, a, y0)) for r, a in ((r0, a0), (r1, a0), (r1, a1), (r0, a1))]
    high = [(x, y1, z) for x, _, z in low]
    sides = [(low[i], low[i - 1], high[i - 1], high[i]) for i in range(4)]
    return solid([low, high] + sides)


def drum(radius, y0, y1, at=(0, 0, 0), sides=8, top=None):
    """An upright tube standing at `at`, optionally tapering to `top` at its upper end."""
    return placed(barrel(radius, y0, y1, sides=sides, end_radius=top), at, pitch=-90)


def ball(radius, at, rings=6, sides=12, squash=1.0):
    """A faceted sphere, flattened by `squash`."""
    def point(i, j):
        tilt, turn = pi * i / rings, 2 * pi * j / sides
        return (at[0] + radius * sin(tilt) * sin(turn), at[1] + radius * cos(tilt) * squash,
                at[2] + radius * sin(tilt) * cos(turn))

    faces = []
    for i in range(rings):
        for j in range(sides):
            corners = [point(i, j), point(i, j + 1), point(i + 1, j + 1), point(i + 1, j)]
            if i == 0:
                corners = corners[1:]       # the two top corners are the same pole
            elif i == rings - 1:
                corners = corners[:3]
            faces.append(corners)
    return solid(faces)


def glow(parts, depth=0.3):
    """One mesh of (shape, colour) pairs that seems lit from inside: no outline, and faces turned
    from the light lose only `depth` of their colour. For the sun, for crystals, for anything
    that shines."""
    vertices, colours = [], []
    for faces, colour in parts:
        for corners, normal in faces:
            s = 1 - depth * (1 - shade(normal)) / 0.45
            triangles = fan(corners)
            vertices += triangles
            colours += [(colour[0] * s, colour[1] * s, colour[2] * s, 1)] * len(triangles)
    return Mesh(vertices=vertices, colors=colours, mode='triangle', static=True)


def cone_collider(inner, outer, peak, base, segments=48):
    """A shallow cone seen from below, from `peak` at radius `inner` down to `base` at `outer`, as
    triangles each wound both ways so a ray finds it from either side."""
    vertices = []
    top = Vec3(0, peak, 0)      # the flat plate in the middle
    for i in range(segments):
        a0, a1 = i * 360 / segments, (i + 1) * 360 / segments
        a, b = polar(inner, a0, peak), polar(outer, a0, base)
        c, d = polar(outer, a1, base), polar(inner, a1, peak)
        for tri in ((a, b, c), (a, c, d), (top, a, d)):
            vertices += [tuple(p) for p in tri] + [tuple(p) for p in reversed(tri)]
    return Mesh(vertices=vertices, mode='triangle', static=True)


def gate_hue(now):
    """The hue a boost gate is lit, `now` seconds in: round the colour wheel, skipping the greens
    that mean "parry this"."""
    hue = (now * 75) % 280
    return hue + 80 if hue >= 80 else hue


class Arena(Entity):
    name = ''
    title = ''                  # shown under the level's number
    radius = 60                 # of the floor, out to the wall
    wall_segments = 48
    sky = color.hsv(250, 0.6, 0.07)     # what is seen where nothing is drawn
    DUST = 'steam'              # the pixel look of the puff an enemy comes in with (fx/pixels.py)
    spawn_position = Vec3(0, 0, 26)
    spawn_yaw = 90
    gate_half_width = 7
    gate_height = 6

    def __init__(self):
        super().__init__()
        self.player = None
        self.pads = []
        self.gates = []         # (centre, [the parts that light up])
        self.entries = []       # where enemies come in: {'angle', 'spot', 'hold', ...}
        self.obstacles = []     # circles (x, z, radius) that ground enemies steer out of
        self.perches = []       # high spots a sniper can stand on
        self.anchors = []       # points overhead that something can hang from
        self.vines = []         # the Vine each of them is the tip of, where they swing
        self.decks = []
        self.ramps = []

    def block(self, **kwargs):
        """An invisible box that only collides."""
        return Entity(parent=self, collider='box', **kwargs)

    def piece(self, parts, outline=OUTLINE, **kwargs):
        """One baked mesh of (shape, colour) pairs, in world coordinates."""
        return Entity(parent=self, model=build(parts, outline), **kwargs)

    def lamp(self, parts, depth=0.3, **kwargs):
        """One baked mesh that shines: see `glow`."""
        return Entity(parent=self, model=glow(parts, depth), **kwargs)

    # --- building blocks every map uses ---

    def build_floor_and_wall(self, height):
        """The colliders of the floor and of the wall round it."""
        size = self.radius * 2 + 6
        self.block(position=(0, -0.5, 0), scale=(size, 1, size))
        centre = self.radius + 0.5
        width = 2 * (centre + 0.5) * tan(pi / self.wall_segments) + 0.1
        for i in range(self.wall_segments):
            angle = i * 360 / self.wall_segments
            self.block(position=polar(centre, angle, height / 2), rotation_y=angle, scale=(width, height, 1))

    def build_ceiling(self, inner, peak, base):
        """Nothing gets out of the top: one cone-shaped collider over the whole arena."""
        ceiling = Entity(parent=self)
        ceiling.collider = MeshCollider(ceiling, mesh=cone_collider(inner, self.radius + 2.5, peak, base,
                                                                     self.wall_segments))

    def add_deck(self, angle, half_arc, inner, height, thickness=0.5, pieces=4):
        """A raised floor against the wall. Returns where its slabs are, as (centre, yaw, width, depth)."""
        self.decks.append(Deck(angle, half_arc, inner, self.radius, height))
        depth = self.radius - inner
        step = half_arc * 2 / pieces
        width = 2 * self.radius * tan(radians(step / 2)) + 0.1
        slabs = []
        for k in range(pieces):
            a = angle + (k - (pieces - 1) / 2) * step
            at = polar(inner + depth / 2, a, height - thickness / 2)
            self.block(position=at, rotation_y=a, scale=(width, thickness, depth))
            slabs.append((at, a, width, depth))
        return slabs

    def add_ramp(self, angle, start, end, width, height, thickness=0.5):
        """A slope from the ground up to a deck. Returns (centre, pitch, length) of its slab; the
        centre is lowered so the top face, not the middle of the slab, meets the deck's edge."""
        self.ramps.append(Ramp(angle, start, end, width, height))
        run = end - start
        slope = degrees(atan2(height, run))
        length = sqrt(height * height + run * run)
        drop = thickness / 2 / cos(radians(slope))
        at = polar(start + run / 2, angle, height / 2 - drop)
        self.block(position=at, rotation_y=angle, rotation_x=-slope, scale=(width, thickness, length))
        return at, -slope, length

    def add_pad(self, radius, angle, up, inward, size=4):
        """A square that throws whoever steps on it up and back toward the middle."""
        pad = self.block(position=polar(radius, angle, 0.1), rotation_y=angle, scale=(size, 0.3, size))
        pad.pad_velocity = polar(-inward, angle, up)
        self.pads.append(pad)
        return pad

    def add_entry(self, angle, inset=2.4, **more):
        entry = {'angle': angle, 'spot': polar(self.radius - inset, angle), 'open': 0.0, 'hold': 0.0, **more}
        self.entries.append(entry)
        return entry

    def open_entry(self, entry):
        """Someone is coming through."""
        entry['hold'] = 1.4

    # --- queries for things that don't use colliders ---

    def ground_height(self, x, z, y):
        """Height of the walkable surface under a point that is currently at height y."""
        if not self.decks and not self.ramps:
            return 0.0
        r = sqrt(x * x + z * z)
        angle = degrees(atan2(x, z))
        for deck in self.decks:
            if deck.inner <= r <= deck.outer + 1 and y >= deck.height - 1:
                if abs((angle - deck.angle + 180) % 360 - 180) <= deck.half_arc:
                    return deck.height
        for ramp in self.ramps:
            if not ramp.start <= r < ramp.end:
                continue
            offset = radians((angle - ramp.angle + 180) % 360 - 180)
            across, along = r * sin(offset), r * cos(offset)
            if abs(across) <= ramp.width / 2 and along >= ramp.start:
                height = (along - ramp.start) / (ramp.end - ramp.start) * ramp.height
                if y >= height - 1:
                    return min(height, ramp.height)
        return 0.0

    def way_up(self, enemy, player):
        """The direction to run for a player standing on a deck overhead: to the foot of the
        nearest ramp, then up it. None if there is nothing to climb."""
        if not self.ramps:
            return None
        angle = degrees(atan2(player.x, player.z))
        ramp = min(self.ramps, key=lambda ramp: abs((angle - ramp.angle + 180) % 360 - 180))
        climb = player.y - enemy.y
        on_ramp = 0.3 < enemy.y < ramp.height - 0.1
        if not getattr(player, 'grounded', True) or climb < (0.3 if on_ramp else 1.5):
            return None
        a = radians(ramp.angle)
        ax, az = sin(a), cos(a)                             # the ramp runs outward along this
        along = enemy.x * ax + enemy.z * az
        across = enemy.x * az - enemy.z * ax
        if abs(across) < ramp.width / 2 - 1 and along > ramp.start - 3:
            goal = ramp.end + 3                             # on it: straight up, steering for its middle
            tx, tz = ax * goal - enemy.x, az * goal - enemy.z
        else:
            tx, tz = ax * (ramp.start - 2) - enemy.x, az * (ramp.start - 2) - enemy.z
        length = sqrt(tx * tx + tz * tz)
        return (tx / length, tz / length) if length > 0.5 else (ax, az)

    # --- frame ---

    def update(self):
        dt = time.dt
        for entry in self.entries:
            entry['hold'] -= dt
            wide = 1.0 if entry['hold'] > 0 else 0.0
            entry['open'] += (wide - entry['open']) * min(1.0, 9 * dt)
        if dt > 0:
            now = time.time()
            for vine in self.vines:
                if vine.holder is None:
                    # stirred a little by the air, and swinging on after whatever let go of it
                    stir = (T.VINE_STIR * sin(now * 0.9 + vine.phase), T.VINE_STIR * cos(now * 0.7 + vine.phase * 1.7))
                    vine.swing(min(dt, T.MAX_DT), T.VINE_STIFFNESS, T.VINE_DAMPING, stir)
        self.animate(dt)
        if self.player is not None:
            self.check_gates()

    def animate(self, dt):
        """Whatever moves in this map."""

    def light_gates(self, tint):
        for _, parts in self.gates:
            for part in parts:
                part.color = tint

    def check_gates(self):
        p = self.player
        if p.boost_cooldown > 0 or p.y > self.gate_height:
            return
        for centre, _ in self.gates:
            dx, dz = p.x - centre.x, p.z - centre.z
            if dx * dx + dz * dz < self.gate_half_width * self.gate_half_width:
                if p.boost(T.GATE_BOOST, T.GATE_MAX_SPEED):
                    p.boost_cooldown = T.GATE_COOLDOWN
                return
