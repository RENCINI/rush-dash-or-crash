from math import cos, pi, sin
from random import uniform

import numpy as np
from panda3d.core import (ColorAttrib, Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat,
                          OmniBoundingVolume, TransparencyAttrib)
from PIL import Image
from ursina import Entity, Texture, camera, time
from ursina.shaders import unlit_shader

MAX_PARTICLES = 1500
FLOOR_Y = 0.06
VERTEX = np.dtype([('pos', '<f4', 3), ('col', 'u1', 4)])
CORNERS = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]], dtype=np.float32)


class Particles(Entity):
    """Every particle in the game is one square in a single mesh that is rewritten each
    frame from numpy arrays, so a burst of confetti costs no extra scene objects."""

    def __init__(self):
        super().__init__()
        n = MAX_PARTICLES
        self.pos = np.zeros((n, 3), np.float32)
        self.vel = np.zeros((n, 3), np.float32)
        self.col = np.zeros((n, 4), np.float32)
        self.age = np.ones(n, np.float32)
        self.life = np.ones(n, np.float32)      # age >= life means the slot is free
        self.size = np.zeros(n, np.float32)
        self.gravity = np.zeros(n, np.float32)
        self.cursor = 0
        self.live = False
        self.buffer = np.zeros(n * 4, VERTEX)

        data = GeomVertexData('particles', GeomVertexFormat.getV3c4(), Geom.UHDynamic)
        data.uncleanSetNumRows(n * 4)
        triangles = GeomTriangles(Geom.UHStatic)
        for i in range(n):
            a = i * 4
            triangles.addVertices(a, a + 1, a + 2)
            triangles.addVertices(a, a + 2, a + 3)
        geom = Geom(data)
        geom.addPrimitive(triangles)
        self.geom_node = GeomNode('particles')
        self.geom_node.addGeom(geom)
        self.geom_node.setBounds(OmniBoundingVolume())
        self.geom_node.setFinal(True)
        # drawn with the same shader as everything else, which multiplies a texture by
        # the vertex colour, so the mesh gets a plain white texture
        self.texture = Texture(Image.new('RGBA', (2, 2), (255, 255, 255, 255)))
        self.shader = unlit_shader
        path = self.attachNewNode(self.geom_node)
        path.setAttrib(ColorAttrib.makeVertex(), 10)
        path.setTransparency(TransparencyAttrib.MAlpha)
        path.setTwoSided(True)
        path.setDepthWrite(False)
        path.setBin('transparent', 10)
        self.upload()

    # --- emitting ---

    def emit(self, position, velocity, colour, size, life, gravity=24.0):
        i = self.cursor
        self.cursor = (i + 1) % MAX_PARTICLES
        self.pos[i] = position
        self.vel[i] = velocity
        self.col[i] = colour
        self.size[i] = size
        self.life[i] = life
        self.age[i] = 0
        self.gravity[i] = gravity
        self.live = True

    def burst(self, position, colour, count=40, speed=12.0, size=0.09, life=0.9, up=4.0, white=0.25):
        """Confetti flying out in every direction. `colour` is anything indexable as r, g, b."""
        x, y, z = position[0], position[1], position[2]
        r, g, b = colour[0], colour[1], colour[2]
        for _ in range(count):
            a, h = uniform(0, 2 * pi), uniform(-1, 1)
            flat = (1 - h * h) ** 0.5
            s = speed * uniform(0.25, 1)
            shade = uniform(0.75, 1.15)
            tint = (1, 1, 1, 1) if uniform(0, 1) < white else (r * shade, g * shade, b * shade, 1)
            self.emit((x, y, z), (cos(a) * flat * s, h * s + up, sin(a) * flat * s), tint,
                      size * uniform(0.6, 1.4), life * uniform(0.6, 1.2))

    def sparks(self, position, normal, colour, count=8, speed=9.0):
        """A small spray away from a surface, for bullet impacts."""
        x, y, z = position[0], position[1], position[2]
        for _ in range(count):
            v = (normal[0] * speed * 0.6 + uniform(-1, 1) * speed * 0.5,
                 normal[1] * speed * 0.6 + uniform(-1, 1) * speed * 0.5,
                 normal[2] * speed * 0.6 + uniform(-1, 1) * speed * 0.5)
            self.emit((x, y, z), v, (colour[0], colour[1], colour[2], 1), uniform(0.03, 0.06), uniform(0.15, 0.35))

    # --- frame ---

    def update(self):
        if not self.live:
            return
        dt = time.dt
        alive = self.age < self.life
        if not alive.any():
            self.live = False
            self.upload()
            return
        self.age[alive] += dt
        self.vel[alive, 1] -= self.gravity[alive] * dt
        self.vel[alive] *= 1 - min(1.2 * dt, 1)
        self.pos[alive] += self.vel[alive] * dt
        # bounce off the arena floor
        low = alive & (self.pos[:, 1] < FLOOR_Y) & (self.vel[:, 1] < 0)
        self.pos[low, 1] = FLOOR_Y
        self.vel[low, 1] *= -0.45
        self.vel[low, 0] *= 0.7
        self.vel[low, 2] *= 0.7
        self.upload()

    def upload(self):
        alive = self.age < self.life
        remaining = np.clip(1 - self.age / self.life, 0, 1)
        half = np.where(alive, self.size * np.minimum(1, remaining * 3), 0).astype(np.float32)
        right = np.array(camera.right, np.float32)
        up = np.array(camera.up, np.float32)
        offsets = CORNERS[:, 0, None] * right + CORNERS[:, 1, None] * up        # (4, 3)
        corners = self.pos[:, None, :] + offsets[None, :, :] * half[:, None, None]
        self.buffer['pos'] = corners.reshape(-1, 3)
        colours = (np.clip(self.col, 0, 1) * 255).astype(np.uint8)
        self.buffer['col'] = np.repeat(colours, 4, axis=0)
        data = self.geom_node.modifyGeom(0).modifyVertexData()
        data.modifyArray(0).modifyHandle().copyDataFrom(self.buffer.tobytes())
