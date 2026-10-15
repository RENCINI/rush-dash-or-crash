from ursina import Entity, color, time

from fx.toon import burst_mesh, ring_mesh

POOL = 6


class Blasts(Entity):
    """Outlined shock rings with a white-hot star at the centre, for explosions and big guns.
    They always face the camera."""

    def __init__(self):
        super().__init__()
        # a mesh belongs to one entity, so each pooled ring and star builds its own
        self.items = [{'ring': Entity(model=ring_mesh(), billboard=True, double_sided=True, enabled=False),
                       'core': Entity(model=burst_mesh(points=9), billboard=True, double_sided=True, enabled=False),
                       'age': 0.0, 'life': 0.0, 'radius': 1.0, 'colour': color.white, 'core_on': True} for _ in range(POOL)]
        self.cursor = 0

    def show(self, position, radius, colour, life=0.35, core=True):
        """`core=False` leaves out the white star, for rings right in front of the camera."""
        item = self.items[self.cursor]
        self.cursor = (self.cursor + 1) % POOL
        item.update(age=0.0, life=life, radius=radius, colour=colour, core_on=core)
        for part in (item['ring'], item['core']):
            part.position = position
            part.enabled = True
        self.draw(item)

    def draw(self, item):
        t = item['age'] / item['life']
        c = item['colour']
        ring, core = item['ring'], item['core']
        ring.scale = item['radius'] * (0.25 + 0.75 * (1 - (1 - t) ** 3))     # shoots out, then eases
        # it darkens in steps as it spreads, and is gone before it could fade
        shade = 1.0 if t < 0.45 else 0.68 if t < 0.72 else 0.42
        ring.color = color.Color(c[0] * shade, c[1] * shade, c[2] * shade, 1)
        ring.enabled = t < 0.9
        flash = max(0.0, 1 - t * 2.5)       # the core is gone well before the ring
        core.enabled = flash > 0 and item['core_on']
        core.scale = max(item['radius'] * 0.7 * (0.4 + 0.6 * flash), 0.001)
        core.rotation_z = item['radius'] * 40 + t * 90

    def update(self):
        dt = time.dt
        for item in self.items:
            if not item['ring'].enabled:
                continue
            item['age'] += dt
            if item['age'] >= item['life']:
                item['ring'].enabled = item['core'].enabled = False
            else:
                self.draw(item)
