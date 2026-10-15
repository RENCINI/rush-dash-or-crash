from math import cos, sin
from random import Random

from ursina import Entity, Vec3, color, time

from fx.toon import box, build, placed, solid
from game.maps.arena import Arena, ball, drum, polar, wedge

RADIUS = 60
CLIFF = 12                  # height of the rock round the clearing
CANOPY_BASE = 17            # the leaves overhead: a shallow cone from here, at the cliff...
CANOPY_PEAK = 30            # ...up to here over the pond
CANOPY_INNER = 5.0
CANOPY_OPEN = 34            # inside this radius there are no leaves, only sky
PATH = (19, 33)             # the dirt track round the pond
POND = 7.5
IDOL = 2.5
DECKS = (0, 120, 240)       # treehouse decks against the cliff...
DECK_HEIGHT = 4.5
DECK_INNER = 49
DECK_HALF_ARC = 24
RAMP_START = 36             # ...and the log ramps up to them
RAMP_WIDTH = 6
TREES = (36, 108, 180, 252, 324)    # the great trees a sniper climbs
TREE_RADIUS = 44
TRUNK = 2.2
CROWN_HEIGHT = 12.6         # top of a great tree's crown, flat enough to stand on
BOUNCE = (60, 180, 300)     # mushrooms to bounce on, and the vine arches across the path
MUSHROOM_RADIUS = 53
ARCH_RADIUS = 26
DENS = (35, 85, 155, 205, 275, 325, 0, 120, 240)    # holes in the cliff the crocodiles come out of

GRASS = color.hsv(104, 0.52, 0.66)
GRASS_ALT = color.hsv(98, 0.5, 0.72)
MOSS = color.hsv(118, 0.5, 0.52)
DIRT = color.hsv(32, 0.42, 0.66)
DIRT_ALT = color.hsv(30, 0.42, 0.6)
ROCK = color.hsv(28, 0.16, 0.56)
ROCK_ALT = color.hsv(24, 0.2, 0.48)
SHADOW = color.hsv(250, 0.4, 0.14)
BARK = color.hsv(24, 0.5, 0.4)
BARK_ALT = color.hsv(28, 0.45, 0.5)
LEAF = color.hsv(128, 0.6, 0.5)
LEAF_ALT = color.hsv(112, 0.62, 0.62)
LEAF_DARK = color.hsv(140, 0.6, 0.36)
WOOD = color.hsv(32, 0.5, 0.74)
WOOD_ALT = color.hsv(28, 0.5, 0.62)
ROPE = color.hsv(44, 0.4, 0.86)
WATER = color.hsv(192, 0.6, 0.92)
WATER_ALT = color.hsv(198, 0.55, 0.84)
STONE = color.hsv(60, 0.08, 0.66)
CAP = color.hsv(355, 0.7, 0.92)
CREAM = color.hsv(45, 0.18, 0.97)
PETALS = (color.hsv(330, 0.55, 1), color.hsv(50, 0.7, 1), color.hsv(275, 0.45, 1), color.hsv(15, 0.7, 1))
SKY = color.hsv(200, 0.42, 0.97)
SUN = color.hsv(50, 0.35, 1)
CLOUD = color.hsv(200, 0.05, 1)


def canopy_height(radius):
    outer = RADIUS + 0.5
    return CANOPY_BASE + (outer - radius) / (outer - CANOPY_INNER) * (CANOPY_PEAK - CANOPY_BASE)


def canopy_plate(r0, r1, a0, a1, thickness=0.8):
    """A slab of leaves between two radii and two angles, lying on the slope of the canopy."""
    low = [tuple(polar(r, a, canopy_height(r))) for r, a in ((r0, a0), (r1, a0), (r1, a1), (r0, a1))]
    high = [(x, y + thickness, z) for x, y, z in low]
    sides = [(low[i], low[i - 1], high[i - 1], high[i]) for i in range(4)]
    return solid([low, high] + sides)


class Jungle(Arena):
    """A clearing in the jungle, walled in by rock and great trees: a pond with a stone idol in the
    middle, a dirt track round it under three vine arches, treehouse decks against the cliff with
    log ramps up to them, mushrooms to bounce on, and five trees tall enough to snipe from."""

    name = 'jungle'
    title = 'THE JUNGLE'
    radius = RADIUS
    sky = SKY
    spawn_position = polar(ARCH_RADIUS, 0)
    spawn_yaw = 90

    def __init__(self):
        super().__init__()
        self.rng = Random(11)
        self.bushes = []        # one in front of each den: it shakes when something comes out
        self.caps = []
        self.build_floor_and_wall(CLIFF + 6)
        self.build_ceiling(CANOPY_INNER, CANOPY_PEAK, CANOPY_BASE)
        self.build_ground()
        self.build_cliff()
        self.build_canopy_and_sky()
        self.build_decks()
        self.build_trees()
        self.build_mushrooms()
        self.build_arches()
        self.build_idol()
        self.build_plants()

    def build_ground(self):
        step = 360 / self.wall_segments
        rim = RADIUS + 3
        ground, water = [], []
        for i in range(self.wall_segments):
            a0, a1 = (i - 0.5) * step, (i + 0.5) * step
            odd = i % 2
            ground += [
                (wedge(POND, PATH[0], a0, a1, -1, 0), GRASS if odd else GRASS_ALT),
                (wedge(PATH[0], PATH[1], a0, a1, -1, 0), DIRT if odd else DIRT_ALT),
                (wedge(PATH[1], RAMP_START + 6, a0, a1, -1, 0), GRASS_ALT if odd else GRASS),
                (wedge(RAMP_START + 6, rim, a0, a1, -1, 0), MOSS if odd else GRASS),
                (wedge(POND, POND + 0.9, a0, a1, 0, 0.12), STONE if odd else ROCK),      # the pond's kerb
            ]
            water.append((wedge(POND * 0.45, POND, a0, a1, -1, 0.04), WATER if odd else WATER_ALT))
        self.piece(ground, outline=0)
        water.append((drum(POND * 0.45, -1, 0.04, sides=self.wall_segments), WATER_ALT))
        self.piece(water, outline=0)

    def build_cliff(self):
        """Rock all the way round, higher in some places than others, with trees standing on it
        and the dens the crocodiles come out of at its foot."""
        step = 360 / self.wall_segments
        rng = self.rng
        rock, trees = [], []
        for i in range(self.wall_segments):
            a0, a1 = (i - 0.5) * step, (i + 0.5) * step
            top = CLIFF + rng.uniform(-1.5, 3)
            rock += [
                (wedge(RADIUS, RADIUS + 6, a0, a1, 0, top), ROCK if i % 2 else ROCK_ALT),
                (wedge(RADIUS - 0.5, RADIUS + 0.2, a0, a1, 0, rng.uniform(1.5, 4)), ROCK_ALT if i % 2 else ROCK),
                (wedge(RADIUS - 0.2, RADIUS + 6.2, a0, a1, top, top + 0.7), MOSS),      # grass along the top
            ]
            if i % 2 == 0:
                # a tree on the cliff, leaning in a little over the clearing
                foot = polar(RADIUS + 3.5, i * step)
                height = rng.uniform(8, 12)
                trees += [(drum(1.1, top, top + height, foot, sides=6, top=0.7), BARK if i % 4 else BARK_ALT),
                          (ball(rng.uniform(4.5, 6), polar(RADIUS + 1.5, i * step, top + height + 1.5), rings=4,
                                sides=7, squash=0.7), LEAF if i % 4 else LEAF_ALT)]
        for angle in DENS:
            entry = self.add_entry(angle)

            def put(shape, colour, angle=angle):
                # cliff space: x across, y up, z outward; the rock face is at z = 0
                rock.append((placed(shape, polar(RADIUS - 0.4, angle), yaw=angle), colour))

            put(box((4.6, 4.2, 1.0), (0, 2.1, 0)), ROCK_ALT)            # the lintel and jambs
            put(box((3.4, 3.3, 1.2), (0, 1.65, -0.1)), SHADOW)          # the dark inside
            put(box((5.2, 0.7, 1.4), (0, 4.4, -0.1)), ROCK)
            for side in (-1, 1):
                put(box((0.9, 1.2, 1.3), (side * 2.6, 0.6, -0.2)), ROCK)
            bush = Entity(parent=self, position=polar(RADIUS - 2.0, angle), rotation_y=angle,
                          model=build([(ball(1.0, (-2.6, 0.7, 0), rings=3, sides=6, squash=0.8), LEAF),
                                       (ball(0.8, (2.7, 0.55, 0.2), rings=3, sides=6, squash=0.8), LEAF_ALT),
                                       (ball(0.6, (-1.7, 0.4, -0.5), rings=3, sides=6, squash=0.8), LEAF_ALT)], 0.06))
            entry['bush'] = bush
        self.piece(rock)
        self.piece(trees)

    def build_canopy_and_sky(self):
        """Leaves close the clearing in overhead, all but a ragged hole over the middle that the
        sun comes through. The hole is closed too, but by nothing that can be seen."""
        step = 360 / self.wall_segments
        leaves = []
        for i in range(self.wall_segments):
            a0, a1 = i * step, (i + 1) * step
            ragged = CANOPY_OPEN + (0, 5, 2, 8, 3, 6)[i % 6]
            leaves += [(canopy_plate(ragged, 50, a0, a1), LEAF_DARK if i % 2 else LEAF),
                       (canopy_plate(50, RADIUS + 7, a0, a1, 1.2), LEAF if i % 2 else LEAF_DARK)]
        self.piece(leaves, outline=0, double_sided=True)
        sky = [(ball(26, (-120, 230, 160), rings=5, sides=10), SUN)]
        for x, y, z, size in ((90, 150, 200, 22), (-40, 170, -210, 28), (210, 140, -40, 18), (-230, 135, 30, 24)):
            sky += [(ball(size, (x, y, z), rings=4, sides=8, squash=0.45), CLOUD),
                    (ball(size * 0.7, (x + size * 0.9, y - 2, z + 4), rings=4, sides=8, squash=0.45), CLOUD)]
        self.lamp(sky, depth=0.12)

    def build_decks(self):
        parts = []
        for angle in DECKS:
            for at, yaw, width, depth in self.add_deck(angle, DECK_HALF_ARC, DECK_INNER, DECK_HEIGHT):
                planks = 5
                for k in range(planks):
                    z = (k - (planks - 1) / 2) * depth / planks
                    parts.append((placed(box((width, 0.5, depth / planks - 0.12), (0, 0, z)), at, yaw=yaw),
                                  WOOD if k % 2 else WOOD_ALT))
                parts.append((placed(box((width, 0.24, 0.3), (0, 1.1, 0.2 - depth / 2)), at, yaw=yaw), ROPE))     # rail
                for side in (-1, 1):
                    parts.append((placed(box((0.3, 1.4, 0.3), (side * (width / 2 - 0.2), 0.7, 0.2 - depth / 2)), at,
                                         yaw=yaw), BARK))
            # stilts under the open edge, clear of the ramp
            for side in (-1, 1):
                for off in (9, 20):
                    parts.append((drum(0.45, 0, DECK_HEIGHT - 0.5, polar(DECK_INNER + 0.8, angle + side * off), sides=6),
                                  BARK))
            at, pitch, length = self.add_ramp(angle, RAMP_START, DECK_INNER, RAMP_WIDTH, DECK_HEIGHT)
            logs = 9
            for k in range(logs):
                z = (k - (logs - 1) / 2) * length / logs
                parts.append((placed(box((RAMP_WIDTH, 0.5, length / logs - 0.1), (0, 0, z)), at, yaw=angle, pitch=pitch),
                              WOOD_ALT if k % 2 else BARK_ALT))
            for side in (-1, 1):
                parts.append((placed(box((0.4, 0.62, length), (side * (RAMP_WIDTH / 2 - 0.2), 0, 0)), at, yaw=angle,
                                     pitch=pitch), BARK))
                self.perches.append(polar(RADIUS - 4, angle + side * 15, DECK_HEIGHT))
        self.piece(parts, outline=0.06)

    def build_trees(self):
        parts = []
        for i, angle in enumerate(TREES):
            foot = polar(TREE_RADIUS, angle)
            self.block(position=foot + Vec3(0, CROWN_HEIGHT / 2, 0), rotation_y=angle, scale=(TRUNK * 1.7, CROWN_HEIGHT, TRUNK * 1.7))
            self.block(position=foot + Vec3(0, CROWN_HEIGHT - 1.3, 0), rotation_y=angle, scale=(8.5, 2.6, 8.5))
            self.obstacles.append((foot.x, foot.z, TRUNK + 0.4))
            self.perches.append(foot + Vec3(0, CROWN_HEIGHT, 0))
            parts += [(drum(TRUNK + 0.9, 0, 1.6, foot, top=TRUNK), BARK_ALT),                    # roots
                      (drum(TRUNK, 1.6, CROWN_HEIGHT - 2, foot, top=TRUNK * 0.8), BARK),
                      (placed(box((8.6, 2.6, 8.6), (0, CROWN_HEIGHT - 1.3, 0)), foot, yaw=angle), LEAF if i % 2 else LEAF_ALT),
                      (placed(box((10.4, 1.3, 10.4), (0, CROWN_HEIGHT - 2.2, 0)), foot, yaw=angle + 45), LEAF_DARK)]
            # vines hanging from the crown
            for k in range(4):
                a = angle + 45 + k * 90
                parts.append((box((0.16, self.rng.uniform(2.5, 5), 0.16),
                                  tuple(foot + polar(4.4, a, CROWN_HEIGHT - 4.2))), LEAF_ALT if k % 2 else LEAF_DARK))
        self.piece(parts)

    def build_mushrooms(self):
        for angle in BOUNCE:
            self.add_pad(MUSHROOM_RADIUS, angle, up=20, inward=8)
            spot = polar(MUSHROOM_RADIUS, angle)
            spots = [(ball(0.34, tuple(spot + polar(1.2, a, 0.72)), rings=3, sides=6, squash=0.35), CREAM)
                     for a in (10, 130, 250)]
            # the cap is its own entity so it can throb
            self.caps.append(self.piece([(drum(0.8, 0, 0.3, spot, sides=8), CREAM),
                                         (ball(2.3, tuple(spot + Vec3(0, 0.22, 0)), rings=4, sides=10, squash=0.26), CAP),
                                         (ball(0.5, tuple(spot + Vec3(0, 0.74, 0)), rings=3, sides=6, squash=0.3), CREAM),
                                         *spots], outline=0.05))

    def build_arches(self):
        """Arches of vine over the track. They have no collider; passing under speeds you up."""
        frames = []
        half = self.gate_half_width
        for angle in BOUNCE:
            centre = polar(ARCH_RADIUS, angle)
            for side in (-1, 1):
                foot = polar(ARCH_RADIUS + side * half, angle)
                frames += [(drum(0.55, 0, self.gate_height, foot, sides=6, top=0.4), BARK),
                           (ball(0.9, tuple(foot + Vec3(0, 0.4, 0)), rings=3, sides=6, squash=0.7), LEAF)]
            frames += [(placed(box((0.8, 0.7, half * 2 + 1.2), (0, self.gate_height + 0.2, 0)), centre, yaw=angle), BARK_ALT),
                       (placed(box((1.3, 0.5, half * 2 - 1), (0, self.gate_height + 0.75, 0)), centre, yaw=angle), LEAF)]
            # flowers along the arch and petals on the track: white, so the tint gives them their colour
            lit = [(placed(box((1.3, 0.05, half * 2 - 1.6), (0, 0.025, 0)), centre, yaw=angle), color.white)]
            for k in range(-3, 4):
                lit.append((placed(box((0.5, 0.5, 0.5), (0, self.gate_height - 0.35 - 0.5 * (k % 2), k * 1.7)), centre,
                                   yaw=angle), color.white))
            self.gates.append((centre, [self.piece(lit, outline=0)]))
        self.piece(frames)

    def build_idol(self):
        """A stone head in the pond, grown over."""
        self.block(position=(0, 2, 0), scale=(IDOL, 4, IDOL))
        self.obstacles.append((0.0, 0.0, IDOL))
        self.piece([
            (box((IDOL + 0.8, 0.8, IDOL + 0.8), (0, 0.4, 0)), ROCK_ALT),
            (box((IDOL, 3.2, IDOL), (0, 2.4, 0)), STONE),
            (box((IDOL + 0.4, 0.6, IDOL + 0.4), (0, 4.2, 0)), ROCK),
            (box((IDOL + 0.1, 0.5, IDOL + 0.1), (0, 1.6, 0)), MOSS),
            (ball(0.9, (0.5, 4.6, 0.3), rings=3, sides=6, squash=0.6), LEAF),
        ] + [
            # the same face on all four sides
            (placed(shape, yaw=yaw), tint)
            for yaw in (0, 90, 180, 270)
            for shape, tint in ((box((0.5, 0.4, 0.2), (-0.55, 3.1, IDOL / 2)), SHADOW),
                                (box((0.5, 0.4, 0.2), (0.55, 3.1, IDOL / 2)), SHADOW),
                                (box((0.4, 0.9, 0.3), (0, 2.6, IDOL / 2)), ROCK),
                                (box((1.3, 0.3, 0.2), (0, 1.95, IDOL / 2)), SHADOW))
        ])

    def build_plants(self):
        """Ferns, stones and flowers on the grass. Nothing here gets in anyone's way."""
        rng = self.rng
        parts = []
        for _ in range(110):
            r = rng.choice((rng.uniform(POND + 1.5, PATH[0] - 1), rng.uniform(PATH[1] + 1, RADIUS - 2)))
            angle = rng.uniform(0, 360)
            if any(abs((angle - a + 180) % 360 - 180) < 9 for a in DECKS) and r > RAMP_START - 2:
                continue        # not on a ramp
            at = polar(r, angle)
            kind = rng.random()
            if kind < 0.45:     # a fern: three blades
                for k in range(3):
                    parts.append((placed(box((0.14, rng.uniform(0.5, 1.0), 0.5), (0, 0.3, 0.25)), at,
                                         yaw=angle + k * 120 + rng.uniform(-20, 20), pitch=-35),
                                  LEAF_ALT if k % 2 else LEAF))
            elif kind < 0.7:
                parts.append((ball(rng.uniform(0.3, 0.8), tuple(at + Vec3(0, 0.15, 0)), rings=3, sides=6, squash=0.6),
                              ROCK if kind < 0.6 else ROCK_ALT))
            else:
                petal = rng.choice(PETALS)
                parts += [(box((0.07, 0.5, 0.07), tuple(at + Vec3(0, 0.25, 0))), LEAF_DARK),
                          (box((0.26, 0.2, 0.26), tuple(at + Vec3(0, 0.56, 0))), petal)]
        self.piece(parts, outline=0.04)

    def open_entry(self, entry):
        """Something is coming out of this den: the bushes round it shake."""
        entry['hold'] = 0.9

    def animate(self, dt):
        now = time.time()
        self.light_gates(color.hsv((now * 90) % 360, 0.55, 1))
        throb = color.hsv(0, 0, 0.84 + 0.16 * sin(now * 8))
        for cap in self.caps:
            cap.color = throb
        for entry in self.entries:
            shake = entry['open']
            bush = entry['bush']
            if shake > 0.02 or bush.scale_y != 1:
                bush.scale = (1 + 0.12 * shake * sin(now * 40), 1 + 0.2 * shake * abs(cos(now * 33)), 1) if shake > 0.02 else 1
                bush.rotation_z = 6 * shake * sin(now * 47)
