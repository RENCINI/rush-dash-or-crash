from math import exp, sin
from time import perf_counter

from ursina import Entity, Vec3, application, camera


class Juice(Entity):
    """Screen shake and hitstop. Both run on real time so a freeze can end itself."""

    def __init__(self):
        super().__init__()
        self.trauma = 0.0
        self.hitstop_enabled = True
        self.hitstop_until = 0.0
        self.push = 0.0         # the view knocked back by a shot, settling forward again
        self.last = perf_counter()

    def shake(self, amount):
        self.trauma = min(1.0, max(self.trauma, amount))

    def recoil(self, amount):
        """A shot knocks the view straight back, a little."""
        self.push = max(self.push, amount)

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
        self.push *= exp(-16 * real_dt)
        power = self.trauma * self.trauma
        # smooth noise, not a new random spot every frame: it rattles without blurring
        t = now * 1.0
        x = sin(t * 47.1) * 0.6 + sin(t * 89.3 + 1.7) * 0.4
        y = sin(t * 53.7 + 0.4) * 0.6 + sin(t * 97.1 + 2.9) * 0.4
        turn = sin(t * 41.3 + 0.9) * 0.6 + sin(t * 77.9 + 4.1) * 0.4
        camera.position = Vec3(x * 0.12 * power, y * 0.12 * power, -self.push)
        camera.rotation_x = y * 1.6 * power
        camera.rotation_y = turn * 1.6 * power
