"""The miniboss beacon. After round 3 of a level it rises out of the floor for a while: shoot it
and the level's miniboss comes out of it, and killing that gives health back, the more the
quicker it dies (see Director). Leave it and it sinks again and the next round comes as usual."""
from math import atan2, degrees, sin
from random import uniform

from ursina import Entity, Vec3, color, raycast, time

from data import tuning as T
from fx.toon import barrel, box, build, disc, plate
from game.maps.arena import glow, polar

STONE = color.hsv(250, 0.25, 0.32)
STONE_LIGHT = color.hsv(250, 0.2, 0.46)
LIGHT = color.hsv(345, 0.6, 1)
HEIGHT = 11.0
WIDE = 1.6                  # how much bigger than its first drawing it is built


class Beacon(Entity):
    def __init__(self, game):
        super().__init__(enabled=False)
        self.game = game
        self.live = False       # it can be shot
        self.rise = 0.0         # 0 under the floor, 1 all the way up
        self.going = 0          # 1 rising, -1 sinking
        self.clock = 0.0
        self.body = Entity(parent=self, scale=WIDE)
        self.base = Entity(parent=self.body, model=build([
            (barrel(1.5, -0.2, 0.25, sides=8), STONE),
            (barrel(1.15, 0.25, 0.7, sides=8, end_radius=0.95), STONE_LIGHT),
            *[(box((0.3, 0.9, 0.3), (1.05 * x, 0.6, 1.05 * z)), STONE) for x, z in ((1, 0), (-1, 0), (0, 1), (0, -1))],
        ], 0.04), rotation_x=-90)
        self.column = Entity(parent=self, model=glow([(barrel(0.85, 0.7, HEIGHT, sides=10, end_radius=0.35), color.white)], 0.2),
                             rotation_x=-90, color=LIGHT)
        self.core = Entity(parent=self, model=glow([(barrel(1.0, -1.0, 1.0, sides=8, end_radius=1.0), color.white)], 0.3),
                           y=HEIGHT * 0.75, scale=(1, 1.4, 1), color=color.white)
        self.ring = Entity(parent=self, model=build([(plate(disc(1.0, steps=24), 0.02), color.white)], 0),
                           rotation_x=90, y=0.06, color=LIGHT)
        self.collider_box = Entity(parent=self, collider='box', scale=(3.4, HEIGHT, 3.4), y=HEIGHT / 2, visible=False)

    def spot(self):
        """Open floor to one side of the player, where they can see it."""
        game = self.game
        player, arena = game.player, game.map
        eye = player.position + Vec3(0, T.EYE_HEIGHT, 0)
        around = degrees(atan2(player.x, player.z)) if player.x ** 2 + player.z ** 2 > 1 else uniform(0, 360)
        fallback = None
        for turn in (60, -60, 90, -90, 40, -40, 120, -120, 180):
            for r in (22, 28, 16):
                at = polar(r, around + turn)
                if (at - Vec3(player.x, 0, player.z)).length() < 10:
                    continue
                if any((at.x - ox) ** 2 + (at.z - oz) ** 2 < (radius + 3) ** 2 for ox, oz, radius in arena.obstacles):
                    continue
                if abs(arena.ground_height(at.x, at.z, 1.0)) > 0.05:
                    continue
                fallback = fallback or at
                to = at + Vec3(0, 3, 0) - eye
                if not raycast(eye, to.normalized(), distance=to.length() - 2, ignore=(player,)).hit:
                    return at
        return fallback or polar(20, around + 90)

    def raise_up(self):
        self.position = self.spot()
        self.enabled = True
        self.live = True
        self.going = 1
        self.rise = 0.0
        self.game.sfx.play('beacon')
        self.game.particles.burst(self.position + Vec3(0, 0.5, 0), LIGHT, count=30, speed=7, life=0.6, up=4)

    def sink(self):
        self.live = False
        self.going = -1

    def clear(self):
        self.live = False
        self.going = 0
        self.enabled = False

    # --- being shot ---

    def struck(self, entity):
        """Something hit `entity`: if that was the beacon, it calls the miniboss."""
        if self.live and entity is self.collider_box:
            self.hit()

    def blasted(self, position, radius):
        if self.live and (Vec3(position[0], 0, position[2]) - Vec3(self.x, 0, self.z)).length() < radius + 1.8 \
                and position[1] < HEIGHT + radius:
            self.hit()

    def hit(self):
        game = self.game
        self.live = False
        self.enabled = False
        centre = self.position + Vec3(0, HEIGHT * 0.5, 0)
        game.pixels.show(centre, 5.0, 'heart', shape=False)
        game.particles.burst(centre, LIGHT, count=60, speed=14, life=0.8, white=0.4)
        game.juice.shake(0.5)
        game.sfx.play('explode', volume=0.6, pitch=0.7)
        game.director.call_boss(Vec3(self.x, 0, self.z))

    # --- frame ---

    def update(self):
        dt = time.dt
        self.clock += dt
        if self.going:
            self.rise = max(0.0, min(1.0, self.rise + self.going * dt / 0.8))
            if self.going < 0 and self.rise <= 0:
                self.enabled = False
                self.going = 0
                return
        up = 1 - (1 - self.rise) ** 3
        self.base.y = -1.2 * (1 - up)
        self.column.scale = (1 + 0.15 * sin(self.clock * 6), up, 1 + 0.15 * sin(self.clock * 6))
        self.core.y = HEIGHT * 0.75 * up + 0.3 * sin(self.clock * 2.5)
        self.core.rotation_y += 90 * dt
        self.core.enabled = up > 0.5
        self.ring.scale = 2.5 + (self.clock * 4) % 5
        pulse = 0.5 + 0.5 * sin(self.clock * 7)
        self.column.color = color.hsv(345, 0.6 - 0.25 * pulse, 1)
        self.ring.color = color.hsv(345, 0.6, 1, 1 - ((self.clock * 4) % 5) / 5)
        if self.live and uniform(0, 1) < 20 * dt:
            self.game.pixels.emit((self.x + uniform(-0.6, 0.6), 0.4, self.z + uniform(-0.6, 0.6)),
                                  (0, uniform(3, 6), 0), 'heart', uniform(0.06, 0.12), uniform(0.6, 1.0), 0, 4, drag=0.5)
