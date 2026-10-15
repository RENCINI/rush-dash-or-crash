"""What special enemies drop: toon chips, the currency, and from the golden ones tokens, which are
keys to weapon branches, and crates of ammunition. They pop out of the kill, bounce, and fly to the player once close;
at the end of a round whatever is left on the deck flies in by itself."""
from math import cos, pi, sin
from random import choice, uniform

from ursina import Entity, Vec3, color, time

from data import tuning as T
from fx.toon import barrel, box, build

CHIP_POOL = 48
TOKEN_POOL = 6
AMMO_POOL = 8
CRATE = color.hsv(36, 0.5, 0.7)
BRASS = color.hsv(44, 0.6, 0.95)
CHIP_HUES = (185, 325, 52, 275)
GOLD = color.hsv(46, 0.75, 1)
REST = 0.4                  # how high above the deck a drop comes to rest
ARMED = 0.35                # a drop can't be picked up until it has been out this long
GRAVITY = 24.0


def chip_model():
    """A fat poker chip, built pale so the entity's tint is its colour."""
    pale, rim = color.white, color.hsv(0, 0, 0.72)
    return build([
        (barrel(0.24, -0.04, 0.04, sides=12), rim),
        (barrel(0.17, -0.055, 0.055, sides=12), pale),
        (barrel(0.07, -0.065, 0.065, sides=8), rim),
    ], 0.02)


def token_model():
    """A gold diamond with a white heart."""
    return build([
        (barrel(0.36, -0.06, 0.06, sides=4), GOLD),
        (barrel(0.2, -0.09, 0.09, sides=4), color.white),
    ], 0.025)


def crate_model():
    """An ammunition box with a row of rounds standing on its lid."""
    return build([
        (box((0.5, 0.3, 0.34)), CRATE),
        (box((0.54, 0.07, 0.38), (0, 0.07, 0)), color.hsv(30, 0.5, 0.46)),
        *[(barrel(0.04, -0.06, 0.1, x=x, sides=6), BRASS) for x in (-0.15, -0.05, 0.05, 0.15)],
    ], 0.025)


class Pickups(Entity):
    def __init__(self, game):
        super().__init__()
        self.game = game
        # a mesh belongs to one entity, so every pooled drop builds its own
        self.items = ([{'kind': 'chip', 'entity': Entity(model=chip_model(), enabled=False, ignore=True), 'live': False}
                       for _ in range(CHIP_POOL)]
                      + [{'kind': 'token', 'entity': Entity(model=token_model(), enabled=False, ignore=True),
                          'live': False} for _ in range(TOKEN_POOL)]
                      + [{'kind': 'ammo', 'entity': Entity(model=crate_model(), enabled=False, ignore=True),
                          'live': False} for _ in range(AMMO_POOL)])

    @property
    def live(self):
        return [item for item in self.items if item['live']]

    def drop(self, position, chips=0, tokens=0, ammo=0):
        """Scatter drops out of a point. If the pool is used up the rest is handed over at once."""
        for kind, count in (('chip', chips), ('token', tokens), ('ammo', ammo)):
            for _ in range(count):
                item = next((i for i in self.items if i['kind'] == kind and not i['live']), None)
                if item is None:
                    self.collect(kind)
                    continue
                a, speed = uniform(0, 2 * pi), uniform(0.4, 1) * T.CHIP_POP
                item.update(live=True, age=0.0, pull=False, pos=Vec3(*position),
                            vel=Vec3(sin(a) * speed, uniform(5, 9), cos(a) * speed))
                entity = item['entity']
                entity.position = position
                entity.rotation = (uniform(-25, 25), uniform(0, 360), 0)
                if kind == 'chip':
                    entity.color = color.hsv(choice(CHIP_HUES), 0.6, 1)
                entity.enabled = True

    def vacuum(self):
        """Everything still lying about flies to the player."""
        for item in self.live:
            item['pull'] = True

    def clear(self):
        for item in self.live:
            item['live'] = False
            item['entity'].enabled = False

    def collect(self, kind):
        if kind == 'chip':
            self.game.collect_chip()
        elif kind == 'ammo':
            self.game.collect_ammo()
        else:
            self.game.collect_token()

    def update(self):
        dt = min(time.dt, T.MAX_DT)
        if dt <= 0:
            return
        game = self.game
        centre = game.player.centre
        for item in self.items:
            if not item['live']:
                continue
            item['age'] += dt
            pos, vel, entity = item['pos'], item['vel'], item['entity']
            to = centre - pos
            distance = to.length()
            if item['pull'] or (item['age'] > ARMED and distance < T.CHIP_MAGNET):
                # once it has started for the player it does not let go
                item['pull'] = True
                speed = max(vel.length() + T.CHIP_PULL * dt, 12.0)
                if distance < T.CHIP_COLLECT or speed * dt >= distance:
                    item['live'] = False
                    entity.enabled = False
                    self.collect(item['kind'])
                    continue
                vel = to / distance * speed
            else:
                vel.y -= GRAVITY * dt
                floor = game.map.ground_height(pos.x, pos.z, pos.y + 0.5) + REST
                if pos.y + vel.y * dt < floor and vel.y < 0:
                    pos.y = floor
                    vel = Vec3(vel.x * 0.6, -vel.y * 0.4 if vel.y < -3 else 0.0, vel.z * 0.6)
            pos += vel * dt
            item['pos'], item['vel'] = pos, vel
            entity.position = pos
            entity.rotation_y += (300 if item['kind'] == 'chip' else 160) * dt
