"""Poison clouds left by the Boomer's poison branch. A cloud hurts nothing itself: it keeps
poisoning the enemies inside it, and game/enemies.py deals the poison's damage."""
from math import cos, pi, sin, sqrt
from random import uniform

from ursina import Entity, Vec3, color, destroy, time

from data import tuning as T
from fx.toon import dashed_ring

GAS = color.hsv(282, 0.6, 0.92)          # purple: green is kept for parrying
PUFFS_PER_SECOND = 5.0      # for each metre of radius
HEIGHT = 3.0


class Clouds(Entity):
    def __init__(self, game):
        super().__init__()
        self.game = game
        self.clouds = []        # {'pos', 'radius', 'per_second', 'time', 'refresh', 'puff'}

    def add(self, position, radius, per_second, seconds, ring=True):
        """`ring=False` leaves out the ring that shows how far it reaches, for one that shows it its own way."""
        # an outlined ring of dashes turns on the floor round its edge, so where it reaches is plain
        edge = Entity(model=dashed_ring(segments=18, fill=0.55), double_sided=True, color=GAS, scale=radius,
                      position=(position[0], max(position[1], 0) + 0.08, position[2]), rotation_x=90, ignore=True)
        self.clouds.append({'pos': Vec3(*position), 'radius': radius, 'per_second': per_second, 'time': seconds,
                            'refresh': 0.0, 'puff': 0.0, 'edge': edge, 'turn': 0.0})
        if ring:
            self.game.pixels.ring(position, radius, 'poison')

    def clear(self):
        for cloud in self.clouds:
            destroy(cloud['edge'])
        self.clouds.clear()

    def update(self):
        dt = min(time.dt, T.MAX_DT)
        game = self.game
        for cloud in list(self.clouds):
            cloud['time'] -= dt
            if cloud['time'] <= 0:
                destroy(cloud['edge'])
                self.clouds.remove(cloud)
                continue
            cloud['turn'] += dt * 25
            cloud['edge'].setHpr(cloud['turn'], -90, 0)
            pos, radius = cloud['pos'], cloud['radius']
            cloud['refresh'] -= dt
            if cloud['refresh'] <= 0:
                cloud['refresh'] = T.CLOUD_REFRESH
                for _, enemy in game.enemies.in_radius(pos, radius):
                    enemy.envenom(cloud['per_second'], T.POISON_LINGER)
            # slow puffs of big poison pixels across the whole cloud, thinning out as it runs down
            cloud['puff'] += PUFFS_PER_SECOND * radius * min(1.0, cloud['time']) * dt
            while cloud['puff'] >= 1:
                cloud['puff'] -= 1
                a, r = uniform(0, 2 * pi), radius * sqrt(uniform(0, 1))
                at = (pos.x + sin(a) * r, max(pos.y, 0.3) + uniform(-0.3, HEIGHT), pos.z + cos(a) * r)
                game.pixels.emit(at, (uniform(-1, 1), uniform(0.2, 1), uniform(-1, 1)), 'poison', uniform(0.15, 0.32),
                                 uniform(0.8, 1.3), 2, 7, gravity=-0.5, drag=1.0)
