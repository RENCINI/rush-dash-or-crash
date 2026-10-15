from math import exp

from data import tuning as T


class Rush:
    """0-100 meter driven by the player's speed. It sets the damage multiplier."""

    def __init__(self):
        self.value = 0.0
        self.overdrive = False
        self.overdrive_time = 0.0

    def update(self, speed, dt):
        span = T.RUSH_MAX_SPEED - T.RUSH_MIN_SPEED
        target = (speed - T.RUSH_MIN_SPEED) / span * 100
        target = max(0.0, min(target, T.RUSH_OVERSHOOT))
        tau = T.RUSH_RISE if target > self.value else T.RUSH_FALL
        self.value += (target - self.value) * (1 - exp(-dt / tau))
        self.value = min(self.value, 100.0)

        if self.value >= 99.9:
            self.overdrive = True
        elif self.value < T.OVERDRIVE_EXIT:
            self.overdrive = False
        self.overdrive_time = self.overdrive_time + dt if self.overdrive else 0.0

    @property
    def fraction(self):
        return self.value / 100

    @property
    def damage_multiplier(self):
        return T.RUSH_DAMAGE_MIN + (T.RUSH_DAMAGE_MAX - T.RUSH_DAMAGE_MIN) * self.fraction
