from random import uniform
from time import perf_counter

from ursina import Entity, Vec3, application, camera


class Juice(Entity):
    """Screen shake and hitstop. Both run on real time so a freeze can end itself."""

    def __init__(self):
        super().__init__()
        self.trauma = 0.0
        self.hitstop_enabled = True
        self.hitstop_until = 0.0
        self.last = perf_counter()

    def shake(self, amount):
        self.trauma = min(1.0, max(self.trauma, amount))

    def hitstop(self, seconds):
        if not self.hitstop_enabled or seconds <= 0:
            return
        self.hitstop_until = max(self.hitstop_until, perf_counter() + seconds)
        application.time_scale = 0.02

    def update(self):
        now = perf_counter()
        real_dt = min(now - self.last, 0.1)
        self.last = now
        if application.time_scale < 1 and now >= self.hitstop_until:
            application.time_scale = 1

        self.trauma = max(0.0, self.trauma - real_dt * 2.2)
        power = self.trauma * self.trauma
        camera.position = Vec3(uniform(-1, 1), uniform(-1, 1), 0) * (0.12 * power)
        camera.rotation_x = uniform(-1, 1) * 1.6 * power
        camera.rotation_y = uniform(-1, 1) * 1.6 * power
