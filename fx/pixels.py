"""Explosions made of pixels: square bits of colour that step from one shade to the next as they
age, never blending, the way an explosion in pixel art does. The rocket launchers, the Impulse's
grenades and the Dragon's bursts each have their own palette. A Tiger's blast also draws a tiger's
head out of them, and a poison rocket's a skull: the pixels fly out of the fire to their places,
hang there a moment and fall apart. The pictures are reliefs, several pixels deep and thickest in
the middle, and they swing round a little while they hang so the depth shows.

Like fx/particles.py, every pixel is one square in a single mesh rewritten each frame from numpy
arrays, turned to face the camera. `Pixels(ui=True)` is the same thing flat on the screen, for
the HUD and the menus."""
from math import cos, pi, radians, sin
from random import choice, randint, uniform

import numpy as np
from panda3d.core import (ColorAttrib, Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat,
                          OmniBoundingVolume, TransparencyAttrib)
from PIL import Image
from ursina import Entity, Texture, camera, time
from ursina.shaders import unlit_shader

POOL = 3000
FLOOR_Y = 0.06
VERTEX = np.dtype([('pos', '<f4', 3), ('col', 'u1', 4)])
CORNERS = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]], dtype=np.float32)
PIXEL = 0.11            # half the width of the smallest pixel, for a blast of PIXEL_RADIUS
PIXEL_RADIUS = 5.5
BOUNCE = np.array((0.7, -0.4, 0.7), np.float32)     # what is left of a pixel's speed when it hits the floor

# each look's colours from the hottest to the coldest: a pixel steps down them as it ages
PALETTES = {
    'rocket': ((1, 1, 1), (1, 0.96, 0.72), (1, 0.88, 0.25), (1, 0.7, 0.12), (1, 0.5, 0.1), (0.95, 0.3, 0.1),
               (0.85, 0.13, 0.12), (0.6, 0.08, 0.2), (0.4, 0.16, 0.34), (0.24, 0.21, 0.3)),
    'tiger': ((1, 0.95, 0.2), (1, 0.8, 0.0), (1, 0.6, 0.0), (1, 0.42, 0.0), (1, 0.2, 0.04), (0.92, 0.04, 0.04),
              (0.64, 0.0, 0.08), (0.36, 0.0, 0.05)),
    'impulse': ((1, 1, 1), (0.86, 0.8, 1), (0.66, 0.5, 1), (0.5, 0.3, 0.95), (0.32, 0.86, 0.8), (0.12, 0.6, 0.62),
                (0.15, 0.2, 0.42), (0.1, 0.1, 0.26)),
    'dragon': ((1, 1, 0.8), (1, 0.86, 0.3), (1, 0.56, 0.05), (0.96, 0.16, 0.1), (0.72, 0.02, 0.16), (0.44, 0.02, 0.2),
               (0.22, 0.05, 0.18)),
    'gold': ((1, 1, 0.85), (1, 0.92, 0.4), (1, 0.78, 0.15), (0.92, 0.56, 0.08), (0.7, 0.36, 0.06), (0.42, 0.2, 0.06)),
    'mint': ((1, 1, 1), (0.8, 1, 0.88), (0.5, 1, 0.7), (0.25, 0.9, 0.55), (0.1, 0.62, 0.45), (0.06, 0.36, 0.32)),
    'hurt': ((1, 1, 1), (1, 0.75, 0.6), (1, 0.4, 0.3), (0.92, 0.12, 0.16), (0.6, 0.05, 0.14), (0.32, 0.03, 0.1)),
    'white': ((1, 1, 1), (0.92, 0.96, 1), (0.74, 0.82, 0.95), (0.52, 0.56, 0.72), (0.32, 0.33, 0.46)),
    'rush': ((1, 0.32, 0.36), (1, 0.62, 0.2), (1, 0.92, 0.22), (0.42, 1, 0.42), (0.3, 0.9, 1), (0.48, 0.5, 1),
             (0.8, 0.4, 1), (1, 0.4, 0.8)),
    'heart': ((1, 0.85, 0.9), (1, 0.55, 0.7), (1, 0.3, 0.5), (0.9, 0.1, 0.3), (0.6, 0.05, 0.2)),
    'frost': ((1, 1, 1), (0.85, 0.97, 1), (0.6, 0.9, 1), (0.36, 0.76, 1), (0.22, 0.54, 0.95), (0.18, 0.34, 0.78),
              (0.16, 0.2, 0.5), (0.12, 0.12, 0.3)),
    'legion': ((1, 0.9, 1), (0.92, 0.6, 1), (0.76, 0.32, 1), (0.58, 0.16, 0.92), (0.42, 0.08, 0.7), (0.3, 0.06, 0.5),
               (0.2, 0.04, 0.32), (0.12, 0.03, 0.2)),
    'poison': ((0.9, 1, 0.78), (0.66, 1, 0.18), (0.28, 0.9, 0.24), (0.08, 0.58, 0.26), (0.68, 0.36, 1),
               (0.5, 0.14, 0.82), (0.3, 0.06, 0.46), (0.17, 0.04, 0.24)),
}
LOOKS = tuple(PALETTES)
STEPS = max(len(p) for p in PALETTES.values())

# the pictures, one character a pixel, each a step of the look's palette; '.' is empty
TIGER = (
    '.55.........55.',
    '.525.......525.',
    '.5225555555225.',
    '..53337373335..',
    '.5337333337335.',
    '533333333333335',
    '533007333700335',
    '573007333700375',
    '533333111333335',
    '.5731166611375.',
    '..53111611135..',
    '...531010135...',
    '....5555555....',
)
SKULL = (
    '...3333333...',
    '..311111113..',
    '.31001111113.',
    '3101111111223',
    '3114441444123',
    '3115451545123',
    '3115551555123',
    '.31111611123.',
    '.31116661123.',
    '..331111133..',
    '...3161613...',
    '...3111113...',
    '....33333....',
)
PICTURES = {'tiger': TIGER, 'poison': SKULL}
PICTURE_WIDTH = 0.65    # of the blast's radius
RELIEF = (2, 4)         # pixels deep at a picture's edge, and in its middle
SUNK = {'tiger': '06', 'poison': '456'}     # marks set one pixel back: eyes and noses
SPIN = 35.0             # degrees a picture swings round while it hangs...
SPIN_RATE = 2.5         # ...this fast
PICTURE_RISE = 0.6      # its middle is this much of the radius above the blast
FORM_TIME = 0.3         # for a pixel to fly to its place in the picture...
HOLD_TIME = 0.6         # ...which then holds this long before it falls apart


def cells(picture):
    """[(column, row, step), ...] of the filled cells, with the middle of the picture at (0, 0)
    and rows counted upward."""
    height, width = len(picture), len(picture[0])
    return [(i - (width - 1) / 2, (height - 1) / 2 - j, int(mark)) for j, row in enumerate(picture)
            for i, mark in enumerate(row) if mark != '.']


def relief(look):
    """[(column, row, layer, step), ...] for the look's picture as a relief: each cell a stack of
    pixels, two palette steps darker for each layer back, deepest in the middle, with the eyes and
    nose set back. Back layers come first, so the front is drawn over them."""
    picture = PICTURES[look]
    height, width = len(picture), len(picture[0])
    steps = len(PALETTES[look])
    out = []
    for column, row, step in cells(picture):
        u, v = column / (width / 2), row / (height / 2)
        depth = RELIEF[0] + round((RELIEF[1] - RELIEF[0]) * max(0.0, 1 - u * u - v * v))
        sunk = 1 if str(step) in SUNK.get(look, '') else 0
        for layer in range(depth):
            out.append((column, row, layer + sunk, min(step + 2 * layer, steps - 1)))
    out.sort(key=lambda c: -c[2])
    return out


def on_sphere():
    a, h = uniform(0, 2 * pi), uniform(-1, 1)
    flat = (1 - h * h) ** 0.5
    return cos(a) * flat, h, sin(a) * flat


class Pixels(Entity):
    def __init__(self, ui=False):
        super().__init__(**({'parent': camera.ui, 'ignore_paused': True} if ui else {}))
        self.ui = ui            # flat on the screen, in UI units, with nothing to bounce off
        n = POOL
        self.pos = np.zeros((n, 3), np.float32)
        self.vel = np.zeros((n, 3), np.float32)
        self.age = np.ones(n, np.float32)
        self.life = np.ones(n, np.float32)      # age >= life means the slot is free
        self.size = np.zeros(n, np.float32)
        self.gravity = np.zeros(n, np.float32)
        self.drag = np.zeros(n, np.float32)
        self.look = np.zeros(n, np.int32)
        self.first = np.zeros(n, np.int32)      # the palette step it starts at...
        self.last = np.zeros(n, np.int32)       # ...and the one it ends at
        # a pixel of a picture flies from `start` to `home` until `form`, stays there until
        # `hold`, and only then moves (and darkens) like any other
        self.start = np.zeros((n, 3), np.float32)
        self.home = np.zeros((n, 3), np.float32)
        self.form = np.zeros(n, np.float32)
        self.hold = np.zeros(n, np.float32)
        # while it hangs, a picture swings about the vertical through its middle: each of its
        # pixels keeps where it sits from that middle, and how far the swing goes
        self.centre = np.zeros((n, 3), np.float32)
        self.local = np.zeros((n, 3), np.float32)
        self.spin = np.zeros(n, np.float32)
        self.cursor = 0
        self.live = False
        self.ramps = np.zeros((len(LOOKS), STEPS, 4), np.float32)
        for k, look in enumerate(LOOKS):
            colours = PALETTES[look]
            for s in range(STEPS):
                self.ramps[k, s] = (*colours[min(s, len(colours) - 1)], 1)
        self.buffer = np.zeros(n * 4, VERTEX)
        self.corners = np.zeros((n, 4, 3), np.float32)
        self.colours = np.zeros((n, 4, 4), np.uint8)
        self.shown = np.zeros(n, bool)       # drawn last frame

        data = GeomVertexData('pixels', GeomVertexFormat.getV3c4(), Geom.UHDynamic)
        data.uncleanSetNumRows(n * 4)
        triangles = GeomTriangles(Geom.UHStatic)
        for i in range(n):
            a = i * 4
            triangles.addVertices(a, a + 1, a + 2)
            triangles.addVertices(a, a + 2, a + 3)
        geom = Geom(data)
        geom.addPrimitive(triangles)
        self.geom_node = GeomNode('pixels')
        self.geom_node.addGeom(geom)
        self.geom_node.setBounds(OmniBoundingVolume())
        self.geom_node.setFinal(True)
        self.texture = Texture(Image.new('RGBA', (2, 2), (255, 255, 255, 255)))
        self.shader = unlit_shader
        path = self.attachNewNode(self.geom_node)
        path.setAttrib(ColorAttrib.makeVertex(), 10)
        path.setTwoSided(True)
        if ui:
            path.setTransparency(TransparencyAttrib.MAlpha)
            path.setDepthWrite(False)
            path.setDepthTest(False)
            path.setBin('fixed', 60)        # over the rest of the HUD, and the menus
        else:
            # pixels are solid, so they hide each other: a relief's front stands before its back
            path.setBin('transparent', 11)
        self.upload()

    # --- emitting ---

    def emit(self, position, velocity, look, size, life, first, last, gravity=0.0, drag=3.0):
        i = self.cursor
        self.cursor = (i + 1) % POOL
        self.pos[i] = position
        self.vel[i] = velocity
        self.look[i] = LOOKS.index(look)
        self.size[i] = size
        self.life[i] = life
        self.age[i] = 0
        self.first[i], self.last[i] = first, max(first, last)
        self.gravity[i] = gravity
        self.drag[i] = drag
        self.form[i] = self.hold[i] = 0
        self.live = True
        return i

    def spray(self, position, look, count=10, speed=0.3, size=0.005, life=0.6, gravity=0.8, drag=2.0, up=0.0,
              first=0, last=None):
        """A little burst of pixels flung every way from `position`, for the HUD and the menus."""
        x, y, z = position[0], position[1], position[2] if len(position) > 2 else 0.0
        last = len(PALETTES[look]) - 1 if last is None else last
        for _ in range(count):
            a = uniform(0, 2 * pi)
            s = speed * uniform(0.4, 1.0)
            self.emit((x, y, z), (cos(a) * s, sin(a) * s + up, 0), look, size * uniform(0.7, 1.3),
                      life * uniform(0.7, 1.2), first, last, gravity=gravity, drag=drag)

    def show(self, position, radius, look, shape=True):
        """An explosion of `radius` in `look` ('rocket', 'tiger' or 'poison'). `shape=False`
        leaves out the picture, for small blasts."""
        x, y, z = position[0], position[1], position[2]
        px = PIXEL * radius / PIXEL_RADIUS
        steps = len(PALETTES[look])
        # a white-hot core, gone almost at once
        for _ in range(14):
            dx, dy, dz = on_sphere()
            s = radius * uniform(0.1, 0.6)
            self.emit((x, y, z), (dx * s, dy * s, dz * s), look, px * 3, uniform(0.15, 0.25), 0, 1, drag=4)
        # the fireball: thrown out fast, held back by the air, rising as it cools
        for _ in range(110):
            dx, dy, dz = on_sphere()
            s = radius * uniform(1.2, 3.0)
            self.emit((x, y, z), (dx * s, dy * s * 0.8, dz * s), look, px * choice((1.5, 2, 2.5, 3)),
                      uniform(0.5, 1.0), randint(0, 2), steps - 3, gravity=-2.0, drag=4.5)
        # a ring racing out flat to the edge of the blast: it stops where the damage does
        drag = 5.0
        for k in range(40):
            a = 2 * pi * k / 40
            s = radius * drag
            self.emit((x, y + 0.3, z), (cos(a) * s, 0, sin(a) * s), look, px * 2, uniform(0.35, 0.45), 1, 5, drag=drag)
        # smoke, cooling from the middle of the palette to its dark end as it drifts up
        for _ in range(20):
            dx, _, dz = on_sphere()
            self.emit((x + dx * radius * 0.2, y, z + dz * radius * 0.2),
                      (dx * radius * 0.4, uniform(1, 3), dz * radius * 0.4), look, px * 3,
                      uniform(1.2, 1.8), steps // 2, steps - 1, gravity=-1.5, drag=1.5)
        # embers flung far, falling and bouncing
        for _ in range(30):
            dx, dy, dz = on_sphere()
            s = radius * uniform(1.5, 3.5)
            self.emit((x, y, z), (dx * s, abs(dy) * s + 3, dz * s), look, px * 1.3, uniform(0.8, 1.4), 0, 4,
                      gravity=18.0, drag=0.8)
        if shape and look in PICTURES:
            self.picture(position, radius, look)

    def picture(self, position, radius, look):
        """The look's picture, drawn by pixels that fly out of the blast to their places in a
        relief facing the camera above it (see `relief`)."""
        picture = PICTURES[look]
        cell = radius * PICTURE_WIDTH / len(picture[0])
        right = np.array(camera.right, np.float32)
        up = np.array(camera.up, np.float32)
        back = np.array(camera.forward, np.float32)
        origin = np.array((position[0], position[1], position[2]), np.float32)
        middle = origin + np.array((0, radius * PICTURE_RISE, 0), np.float32)
        steps = len(PALETTES[look])
        spin = radians(SPIN) * choice((-1, 1))
        for column, row, layer, step in relief(look):
            i = self.emit(origin, (uniform(-1, 1), uniform(-2, 0), uniform(-1, 1)), look, cell * 0.55,
                          FORM_TIME + HOLD_TIME + uniform(0.6, 1.0), step, steps - 1, gravity=9.0, drag=1.0)
            self.start[i] = origin + np.array((uniform(-0.3, 0.3), uniform(-0.3, 0.3), uniform(-0.3, 0.3)), np.float32)
            self.local[i] = right * (column * cell) + up * (row * cell) + back * (layer * cell * 0.9)
            self.centre[i] = middle
            self.spin[i] = spin
            self.home[i] = middle + self.local[i]
            self.form[i] = FORM_TIME * uniform(0.75, 1.25)
            self.hold[i] = FORM_TIME * 1.25 + HOLD_TIME
            self.pos[i] = self.start[i]

    def ring(self, position, radius, look):
        """A slow ring of pixels spreading out to `radius` along the floor, to show how far
        something reaches."""
        x, y, z = position[0], position[1], position[2]
        steps = len(PALETTES[look])
        drag = 3.0
        for k in range(72):
            a = 2 * pi * k / 72
            s = radius * drag * uniform(0.97, 1.03)
            self.emit((x, max(y, 0) + 0.25, z), (cos(a) * s, 0, sin(a) * s), look, PIXEL * choice((1.5, 2)),
                      uniform(0.9, 1.2), randint(1, 2), steps - 2, drag=drag)

    def clear(self):
        self.age[:] = self.life
        self.live = False
        self.upload()

    # --- frame ---

    def update(self):
        if not self.live:
            return
        dt = time.dt
        # only the live pixels are worked on: there are seldom more than a few hundred
        idx = np.flatnonzero(self.age < self.life)
        if not len(idx):
            self.live = False
            self.upload(idx)
            return
        self.age[idx] += dt
        held = self.age[idx] < self.hold[idx]
        free = idx[~held]
        if len(free):
            vel = self.vel[free]
            vel[:, 1] -= self.gravity[free] * dt
            vel *= (1 - np.minimum(self.drag[free] * dt, 1))[:, None]
            pos = self.pos[free] + vel * dt
            if not self.ui:
                low = (pos[:, 1] < FLOOR_Y) & (vel[:, 1] < 0)
                pos[low, 1] = FLOOR_Y
                vel[low] *= BOUNCE
            self.vel[free] = vel
            self.pos[free] = pos
        placed = idx[held]
        if len(placed):
            # flying in, quick at first and slowing into place, the whole picture swinging round
            angle = self.spin[placed] * np.sin(self.age[placed] * SPIN_RATE + 0.5)     # out to one side and back
            c, s = np.cos(angle), np.sin(angle)
            local = self.local[placed]
            turned = np.stack((local[:, 0] * c + local[:, 2] * s, local[:, 1], local[:, 2] * c - local[:, 0] * s), axis=1)
            self.home[placed] = self.centre[placed] + turned
            t = np.clip(self.age[placed] / self.form[placed], 0, 1)
            ease = 1 - (1 - t) ** 3
            self.pos[placed] = self.start[placed] + (self.home[placed] - self.start[placed]) * ease[:, None]
        self.upload(idx)

    def upload(self, idx=None):
        """Write the squares of the pixels in `idx` (the live ones) into the mesh, and blank
        those that have just died."""
        alive = self.age < self.life
        if idx is None:
            idx = np.flatnonzero(alive)
        self.corners[self.shown & ~alive] = 0
        self.shown = alive
        if len(idx):
            age, life, hold = self.age[idx], self.life[idx], self.hold[idx]
            first, last = self.first[idx], self.last[idx]
            # a step down the palette at a time: held pixels keep their colour until they let go
            cooling = np.clip((age - hold) / np.maximum(life - hold, 1e-3), 0, 0.999)
            step = np.minimum(first + np.floor(cooling * (last - first + 1)).astype(np.int32), last)
            colours = (np.clip(self.ramps[self.look[idx], step], 0, 1) * 255).astype(np.uint8)
            half = (self.size[idx] * np.minimum(1, np.clip(1 - age / life, 0, 1) * 4)).astype(np.float32)
            if self.ui:
                right, up = np.array((1, 0, 0), np.float32), np.array((0, 1, 0), np.float32)
            else:
                right, up = np.array(camera.right, np.float32), np.array(camera.up, np.float32)
            offsets = CORNERS[:, 0, None] * right + CORNERS[:, 1, None] * up        # (4, 3)
            self.corners[idx] = self.pos[idx, None, :] + offsets[None, :, :] * half[:, None, None]
            self.colours[idx] = colours[:, None, :]
        self.buffer['pos'] = self.corners.reshape(-1, 3)
        self.buffer['col'] = self.colours.reshape(-1, 4)
        data = self.geom_node.modifyGeom(0).modifyVertexData()
        data.modifyArray(0).modifyHandle().copyDataFrom(self.buffer.tobytes())
