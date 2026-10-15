from math import sin

from ursina import Entity, Vec3, Vec4, camera, color, scene, time

from ui.font import Label

POOL = 16
LIFE = 0.7
RISE = 1.8


def world_to_ui(point):
    """Where a world position appears in camera.ui coordinates, or None if it is behind the camera."""
    local = camera.getRelativePoint(scene, Vec3(*point))
    full = camera.lens.getProjectionMat().xform(Vec4(local[0], local[1], local[2], 1))
    if full[3] <= 0.01:
        return None
    return full[0] / full[3] * camera.aspect_ratio / 2, full[1] / full[3] / 2


class Popups(Entity):
    """Numbers that pop out of the world: damage, kills. They live on the UI layer so
    they stay the same size on screen however far away the hit was."""

    def __init__(self):
        super().__init__(parent=camera.ui)
        self.items = []
        for _ in range(POOL):
            text = Label(parent=self, text='', origin=(0, 0), style='block', enabled=False)
            self.items.append({'text': text, 'age': LIFE, 'at': Vec3(0, 0, 0), 'size': 1.0, 'colour': color.white})
        self.cursor = 0

    def show(self, position, message, colour=color.white, size=1.0):
        item = self.items[self.cursor]
        self.cursor = (self.cursor + 1) % POOL
        item['text'].text = message
        item['age'] = 0.0
        item['at'] = Vec3(*position)
        item['size'] = size
        item['colour'] = colour
        item['text'].enabled = True

    def update(self):
        dt = time.dt
        for item in self.items:
            if item['age'] >= LIFE:
                continue
            item['age'] += dt
            text = item['text']
            if item['age'] >= LIFE:
                text.enabled = False
                continue
            item['at'].y += RISE * dt
            at = world_to_ui(item['at'])
            if at is None:
                text.visible = False
                continue
            text.visible = True
            text.position = at
            t = item['age'] / LIFE
            pop = 1 + 0.8 * max(0.0, 1 - item['age'] / 0.1)
            # it goes in two steps, smaller each time, and wobbles as it comes in: never a fade
            fall = 1.0 if t < 0.75 else 0.7 if t < 0.88 else 0.4
            text.scale = item['size'] * pop * fall
            text.rotation_z = sin(item['age'] * 45) * 10 * max(0.0, 1 - item['age'] / 0.25)
            text.color = item['colour']
