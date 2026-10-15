"""Lightning: a jagged ribbon from one point to another, a white core inside a band of colour
inside a dark rim, turned to face the camera. Each one lasts a moment and takes a new shape every
frame of it, so it crackles. Pooled: a few entities, their meshes rewritten in place."""
from random import uniform

from ursina import Entity, Mesh, Vec3, camera, color, time

from fx.toon import OUTLINE

POOL = 8
SEGMENT = 0.7           # metres between the kinks


class Arcs(Entity):
    def __init__(self):
        super().__init__()
        self.items = []
        for _ in range(POOL):
            mesh = Mesh(vertices=[(0, 0, 0)] * 3, colors=[(1, 1, 1, 1)] * 3, mode='triangle', static=False)
            entity = Entity(model=mesh, double_sided=True, enabled=False, ignore=True)
            self.items.append({'entity': entity, 'mesh': mesh, 'age': 0.0, 'life': 0.0, 'start': Vec3(0, 0, 0),
                               'end': Vec3(0, 0, 0), 'colour': color.white, 'width': 0.1})
        self.cursor = 0

    def show(self, start, end, colour, width=0.1, life=0.16):
        item = self.items[self.cursor]
        self.cursor = (self.cursor + 1) % POOL
        item.update(age=0.0, life=life, start=Vec3(*start), end=Vec3(*end), colour=colour, width=width)
        item['entity'].enabled = True
        self.shape(item)

    def shape(self, item):
        start, end = item['start'], item['end']
        along = end - start
        length = along.length()
        if length < 0.05:
            item['entity'].enabled = False
            return
        way = along / length
        side = way.cross(camera.forward)
        if side.length() < 1e-3:
            side = way.cross(Vec3(0, 1, 0))
        side = side.normalized()
        lift = way.cross(side).normalized()
        steps = max(3, int(length / SEGMENT))
        jag = min(0.5, length * 0.07)
        points = [start + along * (i / steps)
                  + (side * uniform(-jag, jag) + lift * uniform(-jag, jag) if 0 < i < steps else Vec3(0, 0, 0))
                  for i in range(steps + 1)]
        c = item['colour']
        bands = ((1.0, (*OUTLINE, 1)), (0.62, (c[0], c[1], c[2], 1)), (0.26, (1, 1, 1, 1)))
        toward = -camera.forward
        vertices, colours = [], []
        for k, (share, tint) in enumerate(bands):
            half = item['width'] * share / 2
            nudge = toward * (0.01 * k)         # each band a hair nearer the eye than the one under it
            for a, b in zip(points, points[1:]):
                a0, a1 = a - side * half + nudge, a + side * half + nudge
                b0, b1 = b - side * half + nudge, b + side * half + nudge
                vertices += [a0, a1, b1, a0, b1, b0]
                colours += [tint] * 6
        mesh = item['mesh']
        mesh.vertices = [tuple(v) for v in vertices]
        mesh.colors = colours
        mesh.generate()

    def update(self):
        dt = time.dt
        for item in self.items:
            if not item['entity'].enabled:
                continue
            item['age'] += dt
            if item['age'] >= item['life']:
                item['entity'].enabled = False
            else:
                self.shape(item)
