"""Poison clouds left by the Boomer's poison branch. A cloud hurts nothing itself: it keeps
poisoning the enemies inside it, and game/enemies.py deals the poison's damage."""
from math import cos, pi, sin, sqrt
from random import uniform

from ursina import Entity, Vec3, color, time

from data import tuning as T

GAS = color.hsv(105, 0.75, 0.95)
PUFFS_PER_SECOND = 5.0      # for each metre of radius
HEIGHT = 3.0


class Clouds(Entity):
    def __init__(self, game):
        super().__init__()
        self.game = game
        self.clouds = []        # {'pos', 'radius', 'per_second', 'time', 'refresh', 'puff'}

    def add(self, position, radius, per_second, seconds, ring=True):
        """`ring=False` leaves out the ring that shows how far it reaches, for one that shows it its own way."""
        self.clouds.append({'pos': Vec3(*position), 'radius': radius, 'per_second': per_second, 'time': seconds,
                            'refresh': 0.0, 'puff': 0.0})
        if ring:
            self.game.blasts.show(position, radius, GAS, life=0.6, core=False)

    def clear(self):
        self.clouds.clear()

    def update(self):
        dt = min(time.dt, T.MAX_DT)
        game = self.game
        for cloud in list(self.clouds):
            cloud['time'] -= dt
            if cloud['time'] <= 0:
                self.clouds.remove(cloud)
                continue
            pos, radius = cloud['pos'], cloud['radius']
            cloud['refresh'] -= dt
            if cloud['refresh'] <= 0:
                cloud['refresh'] = T.CLOUD_REFRESH
                for _, enemy in game.enemies.in_radius(pos, radius):
                    enemy.envenom(cloud['per_second'], T.POISON_LINGER)
            # slow green puffs across the whole cloud, thinning out as it runs down
            cloud['puff'] += PUFFS_PER_SECOND * radius * min(1.0, cloud['time']) * dt
            while cloud['puff'] >= 1:
                cloud['puff'] -= 1
                a, r = uniform(0, 2 * pi), radius * sqrt(uniform(0, 1))
                at = (pos.x + sin(a) * r, max(pos.y, 0.3) + uniform(-0.3, HEIGHT), pos.z + cos(a) * r)
                shade = uniform(0.6, 1)
                game.particles.emit(at, (uniform(-1, 1), uniform(0.2, 1), uniform(-1, 1)),
                                    (GAS[0] * shade, GAS[1] * shade, GAS[2] * shade, 1), uniform(0.2, 0.45),
                                    uniform(0.7, 1.2), gravity=-0.5)
