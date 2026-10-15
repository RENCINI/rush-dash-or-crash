from math import sin, tau
from random import Random

from ursina import Entity, Vec3, color, time

from fx.toon import box, build, placed, solid
from game.maps.arena import Arena, Vine, ball, drum, glow, polar, wedge

RADIUS = 60
WALL = 13                   # the rock is this high where the dome springs from it
DOME_BASE = 13
DOME_PEAK = 24              # a low roof: there is less sky to jump into than on the ship
DOME_INNER = 5.0
TRACK = (19, 33)
HEART = 3.4                 # the great crystal in the middle
LEDGES = (90, 270)          # shelves of rock against the wall...
LEDGE_HEIGHT = 3.0
LEDGE_INNER = 49
LEDGE_HALF_ARC = 26
RAMP_START = 39             # ...and the slopes up to them
RAMP_WIDTH = 6
SPIRES = 8                  # crystal pillars, evenly spaced from this angle
SPIRE_FIRST = 22.5
SPIRE_RADIUS = 44
SPIRE_HEIGHT = 9.0
GEYSERS = ((53, 0), (53, 180), (36, 135), (36, 315))    # (radius, angle) of each
ARCHES = (45, 135, 225, 315)
ARCH_RADIUS = 26
TUNNELS = (20, 65, 115, 160, 200, 245, 295, 340)
HANGING = [(22, a) for a in range(0, 360, 60)] + [(40, 22.5 + a) for a in range(0, 360, 45)]
HANG_LOW = 7.5              # the tip of a hanging vine: what a monkey holds on to

ROCK = color.hsv(258, 0.28, 0.3)
ROCK_ALT = color.hsv(262, 0.3, 0.36)
ROCK_PALE = color.hsv(250, 0.2, 0.46)
ROCK_DARK = color.hsv(262, 0.35, 0.2)
VINE = color.hsv(168, 0.55, 0.5)
LEAF = color.hsv(150, 0.6, 0.68)
LEAF_DARK = color.hsv(158, 0.6, 0.5)
TRACK_A = color.hsv(240, 0.2, 0.44)
TRACK_B = color.hsv(244, 0.2, 0.5)
VOID = color.hsv(265, 0.5, 0.06)
HUES = (185, 300, 55, 130, 20, 265, 340, 210, 95)      # crystals come in all of these


def crystal_colour(hue, value=1.0):
    return color.hsv(hue, 0.55, value)


def dome_height(radius):
    outer = RADIUS + 0.5
    return DOME_BASE + (outer - radius) / (outer - DOME_INNER) * (DOME_PEAK - DOME_BASE)


def dome_plate(r0, r1, a0, a1, thickness=1.0):
    low = [tuple(polar(r, a, dome_height(r))) for r, a in ((r0, a0), (r1, a0), (r1, a1), (r0, a1))]
    high = [(x, y + thickness, z) for x, y, z in low]
    sides = [(low[i], low[i - 1], high[i - 1], high[i]) for i in range(4)]
    return solid([low, high] + sides)


def crystal(at, radius, height, lean=0.0, yaw=0.0, sides=6, tip=0.25):
    """A six-sided crystal standing at `at`: a shaft that comes to a blunt point."""
    shaft = height * (1 - tip)
    shape = drum(radius, 0, shaft, sides=sides, top=radius * 0.85) + drum(radius * 0.85, shaft, height, sides=sides,
                                                                         top=radius * 0.15)
    return placed(shape, at, yaw=yaw, pitch=lean)


def vine_models(length, hue, rng):
    """A vine hanging from its root at the origin down to `length` below, wandering a little
    from side to side, with leaves along it, glowing buds and a knot of crystal at the end to
    hold on to. Returns the stem and leaves, and what glows."""
    stem, lit = [], []
    links = max(3, round(length / 0.9))
    step = length / links
    sway = [(rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1)) for _ in range(links + 1)]
    sway[0] = sway[-1] = (0.0, 0.0)         # straight out of the rock, and straight into the knot
    for i in range(links):
        y0, y1 = -i * step, -(i + 1) * step
        x, z = (sway[i][0] + sway[i + 1][0]) / 2, (sway[i][1] + sway[i + 1][1]) / 2
        stem.append((drum(0.11, y1 - 0.06, y0 + 0.06, (x, 0, z), sides=5, top=0.12), VINE))
        if 0 < i:
            # a pair of leaves at every joint but the first, turned a different way each time
            turn = i * 137.0
            for side in (0, 180):
                leaf = placed(box((0.42, 0.03, 0.2), (0.27, 0, 0)), (x, y0, z), yaw=turn + side, pitch=-25)
                stem.append((leaf, LEAF if side else LEAF_DARK))
        if i % 2 == 1:
            lit.append((ball(0.09, (x + 0.1, y0 - step / 2, z), rings=3, sides=6), crystal_colour(hue)))
    lit += [(ball(0.24, (0, -length, 0), rings=4, sides=7, squash=1.2), crystal_colour(hue)),
            (drum(0.07, -length - 0.55, -length - 0.1, sides=6, top=0.01), crystal_colour(hue, 0.85))]
    return stem, lit


class Cave(Arena):
    """A cave full of crystals of every colour: a great one in the middle that changes hue, a
    ring of pillars, more hanging from the roof, and arches of them over a stone track. Shelves of
    rock against the wall have slopes up to them, and geysers throw whoever steps on one."""

    name = 'cave'
    title = 'THE CRYSTAL CAVE'
    radius = RADIUS
    sky = VOID
    spawn_position = polar(ARCH_RADIUS, 0)
    spawn_yaw = 90

    def __init__(self):
        super().__init__()
        self.rng = Random(23)
        self.pools = []
        self.build_floor_and_wall(WALL + 6)
        self.build_ceiling(DOME_INNER, DOME_PEAK, DOME_BASE)
        self.build_ground()
        self.build_wall()
        self.build_dome()
        self.build_ledges()
        self.build_spires()
        self.build_geysers()
        self.build_arches()
        self.build_heart()
        self.build_scatter()

    def build_ground(self):
        step = 360 / self.wall_segments
        rim = RADIUS + 3
        ground, veins = [(drum(HEART + 2, -1, 0, sides=self.wall_segments), ROCK_DARK)], []
        for i in range(self.wall_segments):
            a0, a1 = (i - 0.5) * step, (i + 0.5) * step
            odd = i % 2
            ground += [
                (wedge(HEART + 2, TRACK[0], a0, a1, -1, 0), ROCK if odd else ROCK_ALT),
                (wedge(TRACK[0], TRACK[1], a0, a1, -1, 0), TRACK_A if odd else TRACK_B),
                (wedge(TRACK[1], RAMP_START + 4, a0, a1, -1, 0), ROCK_ALT if odd else ROCK),
                (wedge(RAMP_START + 4, rim, a0, a1, -1, 0), ROCK if odd else ROCK_DARK),
            ]
            if odd:
                # veins of crystal along both edges of the track, a different colour every few yards
                hue = HUES[(i // 2) % len(HUES)]
                veins += [(wedge(r - 0.18, r + 0.18, a0, a1, 0, 0.04), crystal_colour(hue)) for r in TRACK]
        self.piece(ground, outline=0)
        self.lamp(veins, depth=0.0)

    def build_wall(self):
        step = 360 / self.wall_segments
        rng = self.rng
        rock, gems = [], []
        for i in range(self.wall_segments):
            a0, a1 = (i - 0.5) * step, (i + 0.5) * step
            rock += [
                (wedge(RADIUS, RADIUS + 6, a0, a1, 0, WALL + 5), ROCK_ALT if i % 2 else ROCK),
                (wedge(RADIUS - rng.uniform(0.3, 1.2), RADIUS + 0.2, a0, a1, 0, rng.uniform(1.5, 5)),
                 ROCK_PALE if i % 2 else ROCK_ALT),
                (wedge(RADIUS - rng.uniform(0.2, 0.9), RADIUS + 0.2, a0, a1, rng.uniform(7, 9), WALL + 1), ROCK_DARK),
            ]
            if i % 3 == 0:
                # a cluster growing out of the wall
                hue = rng.choice(HUES)
                foot = polar(RADIUS - 0.3, i * step, rng.uniform(4.5, 7.5))
                for k in range(3):
                    gems.append((crystal(foot, rng.uniform(0.3, 0.6), rng.uniform(1.4, 2.8), lean=rng.uniform(55, 100),
                                         yaw=i * step + 180 + rng.uniform(-35, 35)), crystal_colour(hue, 1 - 0.12 * k)))
        for angle in TUNNELS:
            self.add_entry(angle)

            def put(shape, colour, angle=angle):
                # wall space: x across, y up, z outward; the rock face is at z = 0
                rock.append((placed(shape, polar(RADIUS - 0.4, angle), yaw=angle), colour))

            put(box((4.8, 4.4, 1.0), (0, 2.2, 0)), ROCK_PALE)           # shored up with pale stone
            put(box((3.4, 3.4, 1.2), (0, 1.7, -0.1)), VOID)             # the dark inside
            put(box((5.4, 0.6, 1.4), (0, 4.6, -0.1)), ROCK_ALT)
            hue = HUES[int(angle) % len(HUES)]
            for side in (-1, 1):
                gems.append((crystal(polar(RADIUS - 1.0, angle + side * 2.6), 0.35, 1.7, lean=side * 12, yaw=angle),
                             crystal_colour(hue)))
        self.piece(rock)
        self.lamp(gems)

    def build_dome(self):
        """The roof: rock all the way over, hung with stalactites and with the vines that
        something can swing from."""
        step = 360 / self.wall_segments
        rng = self.rng
        rock = [(drum(DOME_INNER + 0.5, DOME_PEAK - 0.2, DOME_PEAK + 1, sides=12), ROCK_DARK)]
        for i in range(self.wall_segments):
            a0, a1 = i * step, (i + 1) * step
            rock += [(dome_plate(DOME_INNER, 30, a0, a1), ROCK_DARK if i % 2 else ROCK),
                     (dome_plate(30, RADIUS + 7, a0, a1), ROCK if i % 2 else ROCK_ALT)]
        for _ in range(46):
            r, angle = rng.uniform(8, RADIUS - 3), rng.uniform(0, 360)
            top = dome_height(r) + 0.3
            rock.append((drum(0.08, top - rng.uniform(1.5, 4.5), top, polar(r, angle), sides=5, top=rng.uniform(0.5, 1.0)),
                         ROCK_PALE if rng.random() < 0.4 else ROCK_ALT))
        for i, (r, angle) in enumerate(HANGING):
            top = dome_height(r) + 0.3
            at = polar(r, angle)
            hue = HUES[i % len(HUES)]
            rock.append((drum(0.7, top - 1.2, top, at, sides=6, top=1.2), ROCK_ALT))      # the knob it grows out of
            # a vine down from the roof, which swings: its tip is the handhold
            length = top - 1.0 - HANG_LOW
            pivot = Entity(parent=self, position=at + Vec3(0, top - 1.0, 0))
            stem, lit = vine_models(length, hue, rng)
            Entity(parent=pivot, model=build(stem, 0.03))
            Entity(parent=pivot, model=glow(lit))
            self.vines.append(Vine(pivot, length, phase=rng.uniform(0, tau)))
            self.anchors.append(at + Vec3(0, HANG_LOW, 0))
        self.piece(rock, outline=0)

    def build_ledges(self):
        parts, gems = [], []
        for angle in LEDGES:
            for at, yaw, width, depth in self.add_deck(angle, LEDGE_HALF_ARC, LEDGE_INNER, LEDGE_HEIGHT, thickness=1.0):
                parts += [(placed(box((width, 1.0, depth)), at, yaw=yaw), ROCK_PALE),
                          (placed(box((width, 1.1, 0.7), (0, 0, 0.35 - depth / 2)), at, yaw=yaw), ROCK_ALT),
                          (placed(box((width - 0.4, LEDGE_HEIGHT - 1, depth - 1.5), (0, -LEDGE_HEIGHT / 2, 0.7)), at, yaw=yaw),
                           ROCK)]
            at, pitch, length = self.add_ramp(angle, RAMP_START, LEDGE_INNER, RAMP_WIDTH, LEDGE_HEIGHT)
            parts.append((placed(box((RAMP_WIDTH, 0.5, length)), at, yaw=angle, pitch=pitch), ROCK_PALE))
            for side in (-1, 1):
                parts.append((placed(box((0.6, 0.62, length), (side * (RAMP_WIDTH / 2 - 0.3), 0, 0)), at, yaw=angle,
                                     pitch=pitch), ROCK_ALT))
                self.perches.append(polar(RADIUS - 4, angle + side * 16, LEDGE_HEIGHT))
                gems.append((crystal(polar(LEDGE_INNER + 0.8, angle + side * 24, LEDGE_HEIGHT), 0.4, 2.0, lean=side * 10,
                                     yaw=angle), crystal_colour(HUES[(angle // 90 + side) % len(HUES)])))
        self.piece(parts)
        self.lamp(gems)

    def build_spires(self):
        """Pillars of crystal, flat on top: each a different colour, each a place to snipe from."""
        gems, rock = [], []
        for i in range(SPIRES):
            angle = SPIRE_FIRST + i * 360 / SPIRES
            foot = polar(SPIRE_RADIUS, angle)
            self.block(position=foot + Vec3(0, SPIRE_HEIGHT / 2, 0), rotation_y=angle, scale=(2.6, SPIRE_HEIGHT, 2.6))
            self.obstacles.append((foot.x, foot.z, 1.9))
            self.perches.append(foot + Vec3(0, SPIRE_HEIGHT, 0))
            hue = HUES[i % len(HUES)]
            gems += [(drum(1.6, 0, SPIRE_HEIGHT, foot, sides=6, top=1.3), crystal_colour(hue)),
                     (crystal(foot + polar(1.5, angle + 70), 0.5, 3.4, lean=16, yaw=angle + 70), crystal_colour(hue, 0.85)),
                     (crystal(foot + polar(1.4, angle - 110), 0.4, 2.3, lean=20, yaw=angle - 110), crystal_colour(hue, 0.9))]
            rock.append((drum(2.4, 0, 0.5, foot, sides=7, top=2.0), ROCK_PALE))
        self.lamp(gems)
        self.piece(rock)

    def build_geysers(self):
        rock, water = [], []
        for radius, angle in GEYSERS:
            self.add_pad(radius, angle, up=20, inward=8)
            spot = polar(radius, angle)
            rock.append((drum(2.7, 0, 0.3, spot, sides=10, top=2.3), ROCK_PALE))
            water += [(drum(1.9, 0.3, 0.36, spot, sides=10), color.hsv(190, 0.5, 1)),
                      (drum(0.8, 0.36, 0.6, spot, sides=8, top=0.3), color.white)]
        self.piece(rock)
        self.pools.append(self.lamp(water, depth=0.0))

    def build_arches(self):
        """Two crystals leaning together over the track. They have no collider; passing under
        speeds you up."""
        rock = []
        half = self.gate_half_width
        for angle in ARCHES:
            centre = polar(ARCH_RADIUS, angle)
            lit = [(placed(box((1.2, 0.05, half * 2 - 1.6), (0, 0.025, 0)), centre, yaw=angle), color.white)]
            for side in (-1, 1):
                foot = polar(ARCH_RADIUS + side * half, angle)
                rock.append((drum(1.3, 0, 0.5, foot, sides=6, top=1.0), ROCK_PALE))
                # leaning in over the track; the far one leans the other way
                lit.append((crystal(foot, 0.7, 10.0, lean=-side * 42, yaw=angle), color.white))
                lit.append((crystal(foot, 0.4, 3.0, lean=side * 20, yaw=angle + 60), color.hsv(0, 0, 0.85)))
            self.gates.append((centre, [self.lamp(lit)]))
        self.piece(rock)

    def build_heart(self):
        """The great crystal: a cluster taller than the pillars, slowly changing colour."""
        self.block(position=(0, 5, 0), scale=(HEART * 1.4, 10, HEART * 1.4))
        self.obstacles.append((0.0, 0.0, HEART))
        self.piece([(drum(HEART + 1.2, 0, 0.7, sides=9, top=HEART + 0.3), ROCK_PALE)])
        gems = [(crystal((0, 0, 0), 1.9, 12.5), color.white)]
        for k in range(7):
            a = k * 360 / 7
            gems.append((crystal(tuple(polar(1.7, a)), 0.8 + 0.25 * (k % 3), 4.5 + 1.6 * (k % 4), lean=22 + 5 * (k % 2), yaw=a),
                         color.hsv(0, 0, 0.92 - 0.06 * (k % 3))))
        self.heart = self.lamp(gems)

    def build_scatter(self):
        """Small crystals, stones and glowing mushrooms on the floor. Nothing here gets in anyone's way."""
        rng = self.rng
        gems, rock = [], []
        for _ in range(120):
            r = rng.choice((rng.uniform(HEART + 3, TRACK[0] - 1), rng.uniform(TRACK[1] + 1, RADIUS - 2)))
            angle = rng.uniform(0, 360)
            if any(abs((angle - a + 180) % 360 - 180) < 9 for a in LEDGES) and r > RAMP_START - 2:
                continue        # not on a slope
            if any(abs(r - pr) < 4 and abs((angle - pa + 180) % 360 - 180) < 8 for pr, pa in GEYSERS):
                continue
            at = polar(r, angle)
            kind = rng.random()
            if kind < 0.5:
                hue = rng.choice(HUES)
                for k in range(rng.choice((2, 3))):
                    gems.append((crystal(at, rng.uniform(0.12, 0.26), rng.uniform(0.5, 1.5), lean=rng.uniform(0, 35),
                                         yaw=rng.uniform(0, 360)), crystal_colour(hue, 1 - 0.1 * k)))
            elif kind < 0.8:
                rock.append((ball(rng.uniform(0.3, 0.9), tuple(at + Vec3(0, 0.12, 0)), rings=3, sides=6, squash=0.6),
                             ROCK_PALE if kind < 0.65 else ROCK_ALT))
            else:
                hue = rng.choice((185, 300, 130))
                rock.append((box((0.1, 0.4, 0.1), tuple(at + Vec3(0, 0.2, 0))), ROCK_PALE))
                gems.append((ball(0.28, tuple(at + Vec3(0, 0.45, 0)), rings=3, sides=6, squash=0.5), crystal_colour(hue)))
        self.lamp(gems)
        self.piece(rock, outline=0.04)

    def animate(self, dt):
        now = time.time()
        self.light_gates(color.hsv((now * 90) % 360, 0.5, 1))
        self.heart.color = color.hsv((now * 24) % 360, 0.5, 1)
        throb = color.hsv(0, 0, 0.8 + 0.2 * sin(now * 8))
        for pool in self.pools:
            pool.color = throb
