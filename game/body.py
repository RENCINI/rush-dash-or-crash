"""The player's own body, as the player sees it: gloved hands and sleeves on whatever is held, and
legs under the camera that run, jump and slide.

There is no torso or head: the camera sits where they would be.
"""
from math import asin, atan2, degrees, sin

import numpy as np
from ursina import Entity, color, destroy, time

from data import tuning as T
from fx.toon import box, build, placed

SUIT = color.hsv(222, 0.3, 0.52)
SUIT_DARK = color.hsv(224, 0.32, 0.4)
GLOVE = color.hsv(230, 0.25, 0.26)
SOLE = color.hsv(40, 0.15, 0.9)
STRIPE_HUE = 190            # cuffs, knees and belt, unless the player has picked a colour
HIP = (0.13, 0.9)           # x and y of the leg pivots
STRIDE = 0.75               # how fast the legs swing for the ground covered
# where each forearm runs to, in the space of a weapon's view: off the bottom of the screen
ELBOW_RIGHT = (0.1, -0.44, -0.5)
ELBOW_LEFT = (-0.4, -0.42, -0.36)


def stripe(hue):
    return color.hsv(STRIPE_HUE if hue is None else hue, 0.6, 0.95)


def arm(at, elbow, cuff):
    """A glove at `at` on a sleeve that runs back to `elbow`, as (shape, colour) pairs."""
    reach = np.array(elbow, float) - np.array(at, float)
    length = float(np.linalg.norm(reach))
    yaw = degrees(atan2(reach[0], reach[2]))
    pitch = degrees(asin(-reach[1] / length))
    return [
        (placed(box((0.066, 0.066, length), (0, 0, length / 2)), at, yaw=yaw, pitch=pitch), SUIT),
        (placed(box((0.076, 0.076, 0.03), (0, 0, 0.07)), at, yaw=yaw, pitch=pitch), cuff),
        (box((0.07, 0.076, 0.09), at), GLOVE),
        (box((0.074, 0.02, 0.07), (at[0], at[1] + 0.03, at[2] + 0.005)), SUIT_DARK),       # knuckle guard
    ]


def hands(hold, fore, cuff):
    """Both arms on a weapon: the right hand on its grip at `hold`, the left at `fore` if it has
    somewhere to go."""
    parts = arm(hold, ELBOW_RIGHT, cuff)
    if fore is not None:
        parts += arm(fore, ELBOW_LEFT, cuff)
    return parts


class Legs(Entity):
    """Hips, legs and boots, turning with the player and seen by looking down."""

    def __init__(self, player):
        super().__init__(parent=player)
        self.player = player
        self.stride = 0.0
        self.hue = None
        self.hips = None
        self.build()

    def build(self):
        if self.hips is not None:
            destroy(self.hips)      # and the legs that hang from them
        trim = stripe(self.hue)
        self.hips = Entity(parent=self, y=HIP[1], model=build([
            # kept small and set back: the camera is right above, and a full waist would hide the legs
            (box((0.28, 0.1, 0.1), (0, -0.04, -0.2)), SUIT),
            (box((0.3, 0.04, 0.12), (0, -0.01, -0.2)), trim),               # belt
        ]))
        self.legs = []
        for side in (-1, 1):
            leg = Entity(parent=self.hips, x=side * HIP[0], z=0.1, model=build([
                (box((0.13, 0.5, 0.15), (0, -0.25, 0)), SUIT),              # thigh
                (box((0.15, 0.12, 0.18), (0, -0.46, 0.02)), trim),          # knee pad
                (box((0.12, 0.36, 0.14), (0, -0.66, 0)), SUIT_DARK),        # shin
                (box((0.15, 0.13, 0.34), (0, -0.83, 0.08)), GLOVE),         # boot
                (box((0.16, 0.035, 0.36), (0, -0.885, 0.08)), SOLE),
            ]))
            self.legs.append(leg)

    def repaint(self, hue):
        if hue != self.hue:
            self.hue = hue
            self.build()

    def update(self):
        dt = min(time.dt, T.MAX_DT)
        player = self.player
        speed = player.flat_speed
        follow = min(1.0, 14 * dt)
        if player.sliding:
            # sat back with both feet out in front
            swing = (-78, -62)
            hip = 0.34
        elif not player.grounded:
            swing = (-32, 16)       # one knee up
            hip = HIP[1]
        else:
            self.stride += speed * dt * STRIDE
            reach = min(speed / T.RUN_SPEED, 1.2) * 34
            # standing still, the feet are a little forward of the hips, where they can be seen
            swing = (sin(self.stride) * reach - 9, -sin(self.stride) * reach - 9)
            hip = HIP[1]
        self.hips.y += (hip - self.hips.y) * follow
        for leg, angle in zip(self.legs, swing):
            leg.rotation_x += (angle - leg.rotation_x) * follow
