from math import atan2, cos, degrees, pi, radians, sin, sqrt, tan
from random import Random

import numpy as np
from ursina import Entity, Mesh, MeshCollider, Vec3, color, time

from data import tuning as T
from fx.toon import box, build, placed, solid
from game.maps.arena import Arena, Deck, Ramp, ball, drum, polar, wedge

ARENA_RADIUS = 60
WALL_HEIGHT = 14
WALL_SEGMENTS = 48
BALCONY_HEIGHT = 3.5
BALCONY_INNER = 50
BALCONY_HALF_ARC = 28       # each of the four balconies spans this many degrees either side
RAMP_START = 38
RAMP_WIDTH = 7
PILLAR_RADIUS = 44
PILLAR_SIZE = 3
PAD_RADIUS = 53
PAD_LAUNCH_UP = 20
PAD_LAUNCH_INWARD = 8
GATE_RADIUS = 26            # middle of the open loop lane
GATE_HALF_WIDTH = 7
GATE_HEIGHT = 6
HUB_SIZE = 2.5
BAR_LENGTH = 24
BAR_WIDTH = 1.0
BAR_TOP = 0.85
BAR_SPIN = 70               # degrees per second
BAR_KNOCK = 18
BAR_KNOCK_UP = 10
DOORS = 8                   # airlocks in the hull, evenly spaced: the astronauts come in through them
DOOR_FIRST = 37.5           # angle of the first; each sits on a plain stretch of hull, clear of the pads
DOOR_WIDTH, DOOR_HEIGHT = 3.6, 4.2
DOOR_OPEN = 1.4             # seconds a door stays open after someone has come through
ROOF_BASE = WALL_HEIGHT + 0.8   # the roof is a shallow cone from here, at the hull...
ROOF_PEAK = 27                  # ...up to here, over the reactor
ROOF_INNER = 5.0
ROOF_SPOKES = 12
ROOF_PLATE = 0.4                # thickness of the roof plating
SKYLIGHT = (18, 46)             # between these radii the middle of each bay is glass
OUTLINE = 0.08

# ship paint: soft and saturated like the weapons, never glowing
HULL = color.hsv(210, 0.1, 0.9)
HULL_ALT = color.hsv(212, 0.15, 0.8)
PANEL = color.hsv(222, 0.28, 0.44)
DECK = color.hsv(226, 0.26, 0.36)
DECK_ALT = color.hsv(226, 0.24, 0.41)
LANE = color.hsv(214, 0.2, 0.58)
LANE_ALT = color.hsv(214, 0.2, 0.64)
TRIM = color.hsv(42, 0.75, 0.98)        # hazard yellow
DARK = color.hsv(230, 0.3, 0.24)
CREAM = color.hsv(45, 0.18, 0.97)
GLASS = color.hsv(190, 0.45, 1)
PANE = color.hsv(195, 0.5, 1, 0.22)     # skylight glass: the stars show through
SPACE = color.hsv(245, 0.6, 0.22)
CATWALK = color.hsv(18, 0.6, 0.94)
TANK = color.hsv(172, 0.5, 0.84)
PAD = color.hsv(105, 0.6, 0.92)
ARM = color.hsv(355, 0.65, 0.94)
PLANET = color.hsv(205, 0.6, 0.95)
MOON = color.hsv(40, 0.12, 0.9)


def roof_height(radius):
    """Height of the underside of the roof this far from the middle of the deck."""
    outer = ARENA_RADIUS + 0.5
    return ROOF_BASE + (outer - radius) / (outer - ROOF_INNER) * (ROOF_PEAK - ROOF_BASE)


def roof_plate(r0, r1, a0, a1, lift=0.0, thickness=ROOF_PLATE):
    """A slab of the roof between two radii and two angles, lying on its slope."""
    low = [tuple(polar(r, a, roof_height(r) + lift)) for r, a in ((r0, a0), (r1, a0), (r1, a1), (r0, a1))]
    high = [(x, y + thickness, z) for x, y, z in low]
    sides = [(low[i], low[i - 1], high[i - 1], high[i]) for i in range(4)]
    return solid([low, high] + sides)


def roof_collider(segments=WALL_SEGMENTS):
    """The underside of the roof as triangles, each wound both ways so a ray finds it from
    either side."""
    outer = ARENA_RADIUS + 2.5      # past the wall, so there is no gap above it
    vertices = []
    for i in range(segments):
        a0, a1 = i * 360 / segments, (i + 1) * 360 / segments
        a, b = polar(ROOF_INNER, a0, roof_height(ROOF_INNER)), polar(outer, a0, roof_height(outer))
        c, d = polar(outer, a1, roof_height(outer)), polar(ROOF_INNER, a1, roof_height(ROOF_INNER))
        top = Vec3(0, roof_height(ROOF_INNER), 0)       # the flat plate under the hub
        for tri in ((a, b, c), (a, c, d), (top, a, d)):
            vertices += [tuple(p) for p in tri] + [tuple(p) for p in reversed(tri)]
    return Mesh(vertices=vertices, mode='triangle', static=True)


def starfield(count=340, radius=420, seed=7):
    """Diamond stars on a far dome, as one mesh."""
    rng = Random(seed)
    vertices, colours = [], []
    for _ in range(count):
        turn, height = rng.uniform(0, 2 * pi), rng.uniform(0.06, 0.98)
        flat = sqrt(1 - height * height)
        centre = np.array((sin(turn) * flat, height, cos(turn) * flat)) * radius
        side = np.cross(centre, (0, 1, 0))
        side /= np.linalg.norm(side)
        up = np.cross(side, centre)
        up /= np.linalg.norm(up)
        size = rng.uniform(0.5, 2.0)
        glow = rng.uniform(0.55, 1)
        r, g, b = rng.choice(((1, 1, 1), (0.8, 0.9, 1), (1, 0.94, 0.78)))
        left, right, top, bottom = centre - side * size, centre + side * size, centre + up * size, centre - up * size
        for corner in (left, top, right, left, right, bottom):
            vertices.append(tuple(corner))
            colours.append((r * glow, g * glow, b * glow, 1))
    return Mesh(vertices=vertices, colors=colours, mode='triangle', static=True)


class Blender(Arena):
    """Round engine deck of a spaceship: a reactor with a spinning arm in the centre, a wide
    open loop lane with airlock boost gates around it, and gangways, coolant tanks, thruster
    pads and catwalks at the hull, under a plated roof with skylights. Colliders are invisible:
    plain boxes, and one cone for the roof. What is seen is baked from cartoon solids section
    by section."""

    name = 'blender'
    title = 'THE SHIP'
    radius = ARENA_RADIUS
    spawn_position = polar(GATE_RADIUS, 0)
    spawn_yaw = 90

    def __init__(self):
        super().__init__()
        self.pad_lights = []
        self.doors = self.entries       # {'angle', 'spot', 'leaves', 'lamp', 'open', 'hold'}
        self.obstacles.append((0.0, 0.0, HUB_SIZE))
        self.knock_cooldown = 0.0
        for quarter in range(4):
            angle = quarter * 90
            self.decks.append(Deck(angle, BALCONY_HALF_ARC, BALCONY_INNER, ARENA_RADIUS, BALCONY_HEIGHT))
            self.ramps.append(Ramp(angle, RAMP_START, BALCONY_INNER, RAMP_WIDTH, BALCONY_HEIGHT))
            # a sniper stands on a catwalk, either side of its gangway, or on a coolant tank
            self.perches += [polar(ARENA_RADIUS - 4, angle + side * 18, BALCONY_HEIGHT) for side in (-1, 1)]
            self.perches.append(polar(PILLAR_RADIUS, angle + 45, 10))
        self.build_deck_and_hull()
        self.build_roof_and_sky()
        self.build_catwalks()
        self.build_tanks_and_pads()
        self.build_gates()
        self.build_centre()

    def build_deck_and_hull(self):
        size = ARENA_RADIUS * 2 + 6
        self.block(position=(0, -0.5, 0), scale=(size, 1, size))
        step = 360 / WALL_SEGMENTS
        rim = ARENA_RADIUS + 3
        deck = [(drum(8, -1, 0, sides=WALL_SEGMENTS), DECK_ALT)]
        marks = []
        lane_in, lane_out = GATE_RADIUS - GATE_HALF_WIDTH, GATE_RADIUS + GATE_HALF_WIDTH
        for i in range(WALL_SEGMENTS):
            a0, a1 = (i - 0.5) * step, (i + 0.5) * step
            odd = i % 2
            deck += [
                (wedge(8, lane_in, a0, a1, -1, 0), DECK if odd else DECK_ALT),
                (wedge(lane_in, lane_out, a0, a1, -1, 0), LANE if odd else LANE_ALT),
                (wedge(lane_out, RAMP_START, a0, a1, -1, 0), DECK_ALT if odd else DECK),
                (wedge(RAMP_START, rim, a0, a1, -1, 0), DECK if odd else DECK_ALT),
            ]
            if odd:
                # dashed edges of the loop lane
                marks += [(wedge(lane_in - 0.2, lane_in + 0.2, a0, a1, 0, 0.03), TRIM),
                          (wedge(lane_out - 0.2, lane_out + 0.2, a0, a1, 0, 0.03), TRIM)]
            else:
                marks.append((wedge(RAMP_START - 0.15, RAMP_START + 0.15, a0, a1, 0, 0.03), DARK))
        self.piece(deck, outline=0)
        self.piece(marks, outline=0)

        centre_radius = ARENA_RADIUS + 0.5
        width = 2 * (centre_radius + 0.5) * tan(pi / WALL_SEGMENTS) + 0.1
        stars = Random(3)
        hull = []
        for i in range(WALL_SEGMENTS):
            angle = i * step
            # taller than the wall that is seen, to meet the roof
            self.block(position=polar(centre_radius, angle, WALL_HEIGHT / 2 + 1), rotation_y=angle,
                       scale=(width, WALL_HEIGHT + 2, 1))

            def put(shape, colour):
                # panel space: x across, y up, z outward; the wall's inner face is at z = -0.5
                hull.append((placed(shape, polar(centre_radius, angle), yaw=angle), colour))

            put(box((width, WALL_HEIGHT, 1), (0, WALL_HEIGHT / 2, 0)), HULL if i % 2 else HULL_ALT)
            put(box((width, 1.2, 1.3), (0, 0.6, -0.05)), PANEL)                     # skirting
            put(box((width, 1.6, 1.3), (0, WALL_HEIGHT - 2.2, -0.05)), PANEL)
            put(box((width, 0.8, 2.2), (0, WALL_HEIGHT + 0.4, -0.4)), HULL_ALT)     # roof rail
            hull.append((placed(box((0.7, WALL_HEIGHT, 0.5), (0, WALL_HEIGHT / 2, 0)),
                                polar(ARENA_RADIUS, angle + step / 2), yaw=angle + step / 2), PANEL))    # rib
            if i % 3 == 0:
                # a window: there is no hole, the view is painted on
                put(box((5.4, 4.8, 0.3), (0, 7.4, -0.55)), PANEL)
                put(box((4.6, 4.0, 0.3), (0, 7.4, -0.62)), SPACE)
                for _ in range(6):
                    put(box((0.14, 0.14, 0.3), (stars.uniform(-2, 2), 7.4 + stars.uniform(-1.7, 1.7), -0.66)), CREAM)
            elif i % 3 == 1:
                put(box((3.2, 2.2, 0.3), (0, 2.7, -0.5)), PANEL)                     # wall console
                put(box((1.3, 1.0, 0.3), (-0.7, 2.9, -0.56)), GLASS)
                put(box((0.9, 0.3, 0.3), (0.9, 3.2, -0.56)), TRIM)
                put(box((0.9, 0.3, 0.3), (0.9, 2.6, -0.56)), CREAM)
            elif (angle - DOOR_FIRST) % (360 / DOORS) < 0.01:
                self.build_door(angle, put)
            else:
                put(box((width - 1.4, 0.5, 0.3), (0, 5.2, -0.5)), TRIM)             # hazard band
        self.piece(hull)

    def build_door(self, angle, put):
        """An airlock set into one panel of the hull: a frame baked into the wall, and two leaves
        and a lamp that are their own entities, so the door can open."""
        w, h = DOOR_WIDTH, DOOR_HEIGHT
        put(box((w + 1.0, h + 0.7, 0.4), (0, (h + 0.7) / 2, -0.6)), PANEL)          # frame
        put(box((w, h, 0.4), (0, h / 2, -0.64)), DARK)                              # the dark inside
        put(box((w + 1.4, 0.3, 0.5), (0, 0.15, -0.7)), TRIM)                        # sill
        for side in (-1, 1):
            put(box((0.3, h + 0.7, 0.5), (side * (w / 2 + 0.65), (h + 0.7) / 2, -0.62)), TRIM)

        def part(parts, **kwargs):
            return Entity(parent=self, model=build(parts, 0.05), position=polar(ARENA_RADIUS - 0.4, angle),
                          rotation_y=angle, **kwargs)

        leaves = []
        for side in (-1, 1):
            leaves.append(part([
                (box((w / 2, h, 0.2), (side * w / 4, h / 2, 0)), HULL),
                (box((w / 2 - 0.3, 0.5, 0.26), (side * w / 4, h * 0.62, 0)), TRIM),
                (box((w / 2 - 0.3, 0.9, 0.26), (side * w / 4, h * 0.3, 0)), HULL_ALT),
                (box((0.16, h, 0.26), (side * 0.08, h / 2, 0)), DARK),              # where the leaves meet
            ]))
        lamp = part([(box((1.4, 0.3, 0.3), (0, h + 0.95, 0)), color.white)])
        self.doors.append({'angle': angle, 'spot': polar(ARENA_RADIUS - 2.4, angle), 'leaves': leaves, 'lamp': lamp,
                           'open': 0.0, 'hold': 0.0})

    def open_entry(self, door):
        """Someone is coming through: slide it open and hold it a moment."""
        door['hold'] = DOOR_OPEN

    open_door = open_entry

    def build_roof_and_sky(self):
        """Girders over the deck carrying the roof plating, with skylights on to open space.
        Nothing gets through it: the whole underside is one collider."""
        base = ROOF_BASE
        outer, inner = ARENA_RADIUS + 0.5, ROOF_INNER
        run, rise = outer - inner, ROOF_PEAK - base
        slope = degrees(atan2(rise, run))
        length = sqrt(run * run + rise * rise)
        roof = [(drum(6, ROOF_PEAK - 0.6, ROOF_PEAK + 0.6, sides=ROOF_SPOKES), PANEL),
                (drum(3, ROOF_PEAK - 1.2, ROOF_PEAK - 0.6, sides=ROOF_SPOKES), TRIM)]
        for i in range(ROOF_SPOKES):
            angle = i * 360 / ROOF_SPOKES
            roof.append((placed(box((0.9, 0.9, length)), polar((outer + inner) / 2, angle, (base + ROOF_PEAK) / 2),
                                yaw=angle, pitch=slope), HULL_ALT))
        ring = 32
        height = base + (outer - ring) / run * rise
        step = 360 / WALL_SEGMENTS
        for i in range(WALL_SEGMENTS):
            roof.append((wedge(ring - 0.4, ring + 0.4, (i - 0.5) * step, (i + 0.5) * step, height - 0.35, height + 0.35),
                         PANEL))
        self.piece(roof)

        # plating, lying on top of the girders; the two middle slices of each bay are glass
        plates, panes = [], []
        per_bay = WALL_SEGMENTS // ROOF_SPOKES
        for i in range(WALL_SEGMENTS):
            a0, a1 = i * step, (i + 1) * step
            tone = HULL if (i // per_bay) % 2 else HULL_ALT
            glazed = i % per_bay in (per_bay // 2 - 1, per_bay // 2)
            if glazed:
                plates += [(roof_plate(inner, SKYLIGHT[0], a0, a1, 0.45), tone),
                           (roof_plate(SKYLIGHT[1], outer + 1.5, a0, a1, 0.45), tone)]
                panes.append((roof_plate(SKYLIGHT[0], SKYLIGHT[1], a0, a1, 0.5, 0.1), color.white))
                # frame round the glass
                plates += [(roof_plate(r - 0.5, r + 0.5, a0, a1, 0.3, 0.3), PANEL) for r in SKYLIGHT]
            else:
                plates.append((roof_plate(inner, outer + 1.5, a0, a1, 0.45), tone))
        self.piece(plates, outline=0)
        glass = self.piece(panes, outline=0, color=PANE, double_sided=True)
        glass.setTransparency(True)
        ceiling = Entity(parent=self)
        ceiling.collider = MeshCollider(ceiling, mesh=roof_collider())
        Entity(parent=self, model=starfield(), double_sided=True)
        self.piece([(ball(70, (-170, 150, 240)), PLANET), (ball(13, (-40, 215, 200)), MOON)], outline=1.6)

    def build_catwalks(self):
        depth = ARENA_RADIUS - BALCONY_INNER
        mid = BALCONY_INNER + depth / 2
        pieces = 4
        seg_angle = BALCONY_HALF_ARC * 2 / pieces
        width = 2 * ARENA_RADIUS * tan(radians(seg_angle / 2)) + 0.1
        rise = BALCONY_HEIGHT
        run = BALCONY_INNER - RAMP_START
        slope = degrees(atan2(rise, run))
        length = sqrt(rise * rise + run * run)
        thickness = 0.5
        parts = []
        for quarter in range(4):
            base = quarter * 90
            for k in range(pieces):
                angle = base + (k - (pieces - 1) / 2) * seg_angle
                at = polar(mid, angle, BALCONY_HEIGHT - thickness / 2)
                self.block(position=at, rotation_y=angle, scale=(width, thickness, depth))
                parts += [
                    (placed(box((width, thickness, depth)), at, yaw=angle), CATWALK),
                    # the lip along the open edge, a little proud of the deck
                    (placed(box((width, thickness + 0.06, 0.5), (0, 0, 0.25 - depth / 2)), at, yaw=angle), TRIM),
                    (placed(box((width - 0.6, 0.3, 0.6), (0, -thickness / 2 - 0.15, 0)), at, yaw=angle), PANEL),
                ]
            # radial gangway from the floor up to the catwalk edge; the centre is
            # lowered so the top face, not the middle of the slab, meets the edge
            drop = thickness / 2 / cos(radians(slope))
            at = polar(RAMP_START + run / 2, base, rise / 2 - drop)
            self.block(position=at, rotation_y=base, rotation_x=-slope, scale=(RAMP_WIDTH, thickness, length))
            parts.append((placed(box((RAMP_WIDTH, thickness, length)), at, yaw=base, pitch=-slope), HULL))
            for side in (-1, 1):
                parts.append((placed(box((0.5, thickness + 0.06, length), (side * (RAMP_WIDTH / 2 - 0.25), 0, 0)), at,
                                     yaw=base, pitch=-slope), TRIM))
        self.piece(parts)

    def build_tanks_and_pads(self):
        tanks = []
        size = PILLAR_SIZE
        for quarter in range(4):
            angle = 45 + quarter * 90
            at = polar(PILLAR_RADIUS, angle, 5)
            self.block(position=at, rotation_y=angle, scale=(size, 10, size))
            self.obstacles.append((at.x, at.z, size * 0.8))
            foot = polar(PILLAR_RADIUS, angle)
            tanks += [(placed(box((size - 0.4, 10, size - 0.4), (0, 5, 0)), foot, yaw=angle), TANK),
                      (placed(box((size, 0.8, size), (0, 0.4, 0)), foot, yaw=angle), PANEL),
                      (placed(box((size, 0.8, size), (0, 9.6, 0)), foot, yaw=angle), PANEL)]
            tanks += [(placed(box((size - 0.2, 0.5, size - 0.2), (0, y, 0)), foot, yaw=angle), TRIM) for y in (3.2, 6.8)]

            pad = self.block(position=polar(PAD_RADIUS, angle, 0.1), rotation_y=angle, scale=(4, 0.3, 4))
            pad.pad_velocity = polar(-PAD_LAUNCH_INWARD, angle, PAD_LAUNCH_UP)
            self.pads.append(pad)
            # thruster plate; its own entity so it can pulse
            spot = polar(PAD_RADIUS, angle)
            self.pad_lights.append(self.piece([
                (placed(box((4, 0.25, 4), (0, 0.125, 0)), spot, yaw=angle), PAD),
                (drum(1.4, 0.25, 0.3, spot), CREAM),
                (drum(0.8, 0.3, 0.36, spot), PAD),
            ], outline=0.05))
        self.piece(tanks)

    def build_gates(self):
        """Airlock frames across the loop lane. They have no collider; passing through speeds you up."""
        frames = []
        span = GATE_HALF_WIDTH * 2
        for quarter in range(4):
            angle = 45 + quarter * 90
            centre = polar(GATE_RADIUS, angle)
            for side in (-1, 1):
                foot = polar(GATE_RADIUS + side * GATE_HALF_WIDTH, angle)
                frames += [(placed(box((0.9, GATE_HEIGHT, 0.9), (0, GATE_HEIGHT / 2, 0)), foot, yaw=angle), HULL),
                           (placed(box((1.3, 0.6, 1.3), (0, 0.3, 0)), foot, yaw=angle), PANEL),
                           (placed(box((1.1, 0.4, 1.1), (0, GATE_HEIGHT - 1.2, 0)), foot, yaw=angle), TRIM)]
            frames.append((placed(box((0.9, 0.8, span + 1.3), (0, GATE_HEIGHT + 0.2, 0)), centre, yaw=angle), HULL))
            # the lit strips are white so the tint alone gives them their colour
            strips = self.piece([
                (placed(box((1.2, 0.05, span - 1.4), (0, 0.025, 0)), centre, yaw=angle), color.white),
                (placed(box((0.5, 0.2, span - 1.2), (0, GATE_HEIGHT - 0.3, 0)), centre, yaw=angle), color.white),
            ], outline=0)
            self.gates.append((centre, [strips]))
        self.piece(frames)

    def build_centre(self):
        self.block(position=(0, 1, 0), scale=(HUB_SIZE, 2, HUB_SIZE))
        self.piece([
            (box((HUB_SIZE, 2, HUB_SIZE), (0, 1, 0)), PANEL),
            (box((HUB_SIZE + 0.1, 0.3, HUB_SIZE + 0.1), (0, 1.5, 0)), TRIM),
            (drum(0.9, 2, 2.5), GLASS),
            (drum(0.5, 2.5, 3.2), TRIM),
        ])
        # the arm spins, so it is built around its own pivot
        height = BAR_TOP - 0.15
        middle = BAR_TOP / 2 + 0.1
        arm = [(box((BAR_WIDTH, height, BAR_LENGTH), (0, middle, 0)), ARM)]
        for i, z in enumerate((2.5, 5, 7.5, 10)):
            for side in (-1, 1):
                arm.append((box((BAR_WIDTH + 0.06, height + 0.06, 0.7), (0, middle, side * z)), DARK if i % 2 else TRIM))
        self.bar = self.piece(arm, outline=0.05)

    # --- frame ---

    def animate(self, dt):
        self.bar.rotation_y += BAR_SPIN * dt
        now = time.time()
        pulse = color.hsv(0, 0, 0.82 + 0.18 * sin(now * 8))
        for light in self.pad_lights:
            light.color = pulse
        self.light_gates(color.hsv((now * 90) % 360, 0.6, 1))
        for door in self.doors:
            a = radians(door['angle'])
            slide = door['open'] * DOOR_WIDTH * 0.48
            base = polar(ARENA_RADIUS - 0.4, door['angle'])
            for side, leaf in zip((-1, 1), door['leaves']):
                leaf.position = base + Vec3(cos(a), 0, -sin(a)) * (side * slide)
            # red while someone is coming through, a dim green when it is shut
            door['lamp'].color = (color.hsv(0, 0.8, 0.75 + 0.25 * sin(now * 20)) if door['open'] > 0.05
                                  else color.hsv(130, 0.5, 0.6))
        self.knock_cooldown -= dt
        if self.player is not None and self.knock_cooldown <= 0:
            self.check_bar_hit()

    def check_bar_hit(self):
        """The arm has no collider; it throws the player instead of blocking them."""
        p = self.player
        if p.y > BAR_TOP:
            return
        a = radians(self.bar.rotation_y)
        axis = Vec3(sin(a), 0, cos(a))
        side = Vec3(cos(a), 0, -sin(a))
        along = p.x * axis.x + p.z * axis.z
        across = p.x * side.x + p.z * side.z
        if abs(along) > BAR_LENGTH / 2 + T.PLAYER_RADIUS or abs(across) > BAR_WIDTH / 2 + T.PLAYER_RADIUS:
            return
        away = side if across >= 0 else -side
        p.knock(away * BAR_KNOCK + Vec3(0, BAR_KNOCK_UP, 0))
        p.emit('pad')
        self.knock_cooldown = 0.4
