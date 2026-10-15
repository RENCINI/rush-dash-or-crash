"""The runaway heart: once a round a one-eyed red heart gets loose in the arena and runs. It is
seen leaving the health bar first, and comes into the arena once it has dashed off the screen.
Touch it inside the time and it goes home to the health bar and pours health back in; let it get
away and it goes home anyway, and punches some out (see ui/health.py for all three).

It is not an enemy: nothing shoots it, nothing counts it. It flees from the player a little faster
than a run, keeps off the walls and out of the pillars, jukes sideways when the player gets close
and bounces off the pads, so a dash, a boost or a pad is how it is caught."""
from math import atan2, degrees, pi, sin, sqrt
from random import choice, uniform

from ursina import Entity, Vec3, camera, color, time

from data import tuning as T
from fx.toon import ball, barrel, build, placed
from ui.font import Label
from ui.health import HEART_RED, WHITE, Heart

SIZE = 0.75                     # a heart is about 2 units tall: this one is one and a half metres
FEET = 1.0                      # its middle is this far above the ground
LEG = color.hsv(350, 0.75, 0.6)
SHOE = color.hsv(350, 0.7, 0.42)
GRAVITY = 30.0
STRIDE = 1.6                    # metres a step


class RunawayHeart(Entity):
    def __init__(self, game):
        super().__init__(enabled=False)
        self.game = game
        self.state = 'home'     # 'run' while it is loose, 'taunt' as it gets away
        self.x = self.z = self.y = 0.0
        self.vx = self.vy = self.vz = 0.0
        self.time_left = 0.0
        self.juke = 0.0
        self.hop = 0.0
        self.taunt = 0.0
        self.trail = 0.0
        self.grounded = True
        self.wait = 0.0         # while the health bar shows it getting out, it is not here yet
        self.stride = 0.0
        self.heart = Heart(parent=self, y=FEET, scale=SIZE)
        # stubby legs with big shoes, swinging from the hip, and little arms in white gloves
        leg = build([(placed(barrel(0.12, 0, 0.5, sides=8), pitch=90), LEG),
                     (ball(0.2, (0, -0.56, -0.08), (1, 0.6, 1.4), rings=4, sides=8), SHOE)], 0.04)
        self.legs = Entity(parent=self, y=FEET - 0.5)
        self.leg = [Entity(parent=self.legs, model=leg, x=side * 0.24, scale=SIZE) for side in (-1, 1)]
        arm = build([(placed(barrel(0.08, 0, 0.42, sides=6), pitch=90), HEART_RED),
                     (ball(0.17, (0, -0.48, 0), rings=4, sides=8), WHITE)], 0.05)
        self.arm = [Entity(parent=self.heart, model=arm, position=(side * 0.98, -0.02, 0), rotation_z=-side * 40)
                    for side in (-1, 1)]
        self.halo = Entity(parent=self, model='quad', texture=game.enemies.halo_texture, billboard=True, y=FEET,
                           scale=3.2, color=color.hsv(345, 0.6, 1, 0.55))
        self.halo.setDepthWrite(False)
        self.halo.setBin('transparent', 5)
        self.clock = Label(parent=self, text='', origin=(0, 0), y=FEET + 1.4, scale=12, billboard=True)

    @property
    def loose(self):
        return self.state in ('run', 'taunt')

    @property
    def centre(self):
        return Vec3(self.x, self.y + FEET, self.z)

    def release(self):
        """Let it out through one of the map's entries."""
        x, z = self.game.enemies.pick_spawn_point()
        self.x, self.z, self.y = x, z, 0.0
        self.vx = self.vy = self.vz = 0.0
        self.time_left = T.HEART_TIME
        self.juke = self.hop = self.trail = 0.0
        self.grounded = True
        self.state = 'run'
        self.wait = T.HEART_ESCAPE
        self.enabled = True
        self.visible = False
        self.heart.glove.enabled = self.heart.brow.enabled = False
        self.game.hud.health.escape(self.centre)
        self.game.hud.notice('THE HEART GOT OUT!   CATCH IT')

    def arrive(self):
        """Off the screen and into the arena."""
        self.visible = True
        self.game.sfx.play('giggle')
        self.game.pixels.show(self.centre, 2.0, 'heart', shape=False)
        self.draw()

    def clear(self):
        """A new level, or a death: it is simply home again."""
        self.state = 'home'
        self.wait = 0.0
        self.enabled = False

    # --- frame ---

    def update(self):
        dt = min(time.dt, T.MAX_DT)
        if dt <= 0 or not self.loose:
            return
        if self.wait > 0:
            self.wait -= dt
            if self.wait <= 0:
                self.arrive()
            return
        if self.state == 'taunt':
            self.taunt -= dt
            self.heart.rotation_y += 900 * dt
            if self.taunt <= 0:
                self.game.pixels.show(self.centre, 1.6, 'heart', shape=False)
                self.game.particles.burst(self.centre, (1, 0.8, 0.85), count=24, speed=6, size=0.08, life=0.5)
                self.enabled = False
                self.state = 'home'
                self.game.hud.health.punch(T.HEART_PUNCH)
            return
        self.time_left -= dt
        if self.time_left <= 0:
            self.state = 'taunt'
            self.taunt = 0.6
            self.heart.blink(1.0)
            self.game.sfx.play('giggle', pitch=1.2)
            self.game.hud.notice('THE HEART GOT AWAY...')
            return
        self.run(dt)
        player = self.game.player
        if (player.centre - self.centre).length() < T.HEART_CATCH:
            self.caught()
            return
        self.draw()

    def run(self, dt):
        game = self.game
        player, arena = game.player, game.map
        dx, dz = self.x - player.x, self.z - player.z
        distance = sqrt(dx * dx + dz * dz) or 0.001
        ax, az = dx / distance, dz / distance
        # off the wall and out of the pillars, and a wander so it is never quite predictable
        r = sqrt(self.x * self.x + self.z * self.z) or 0.001
        edge = arena.radius - 7
        if r > edge:
            push = (r - edge) / 5
            ax -= self.x / r * push * 2
            az -= self.z / r * push * 2
        for ox, oz, radius in arena.obstacles:
            ox, oz = self.x - ox, self.z - oz
            d = sqrt(ox * ox + oz * oz) or 0.001
            if d < radius + 3:
                ax += ox / d * (radius + 3 - d) / 2
                az += oz / d * (radius + 3 - d) / 2
        wander = sin(self.time_left * 1.3) * 0.5
        ax, az = ax + az * wander, az - ax * wander
        length = sqrt(ax * ax + az * az) or 1.0
        speed = T.HEART_SPEED if distance < 28 else T.HEART_SPEED * 0.6      # far off, it dawdles to tease
        self.juke -= dt
        if self.grounded:
            if distance < T.HEART_JUKE_AT and self.juke <= 0:
                # a leap off to one side of the way it was running
                self.juke = T.HEART_JUKE_EVERY
                side = choice((-1, 1))
                self.vx = (ax / length * 0.4 + side * az / length) * T.HEART_JUKE_SPEED
                self.vz = (az / length * 0.4 - side * ax / length) * T.HEART_JUKE_SPEED
                self.vy = 7.0
                self.grounded = False
                game.sfx.play('giggle', volume=0.5, pitch=1.4)
            else:
                turn = min(1.0, 8 * dt)
                self.vx += (ax / length * speed - self.vx) * turn
                self.vz += (az / length * speed - self.vz) * turn
                self.hop -= dt
                if self.hop <= 0:
                    self.hop = 0.32
                    self.vy = 4.5       # it bounds along
                    self.grounded = False
                for pad in arena.pads:
                    half = pad.scale_x / 2
                    if abs(self.x - pad.x) < half and abs(self.z - pad.z) < half:
                        launch = pad.pad_velocity
                        self.vx, self.vy, self.vz = self.vx + launch.x, launch.y, self.vz + launch.z
                        self.grounded = False
        self.x += self.vx * dt
        self.z += self.vz * dt
        self.stride += sqrt(self.vx * self.vx + self.vz * self.vz) * dt
        r = sqrt(self.x * self.x + self.z * self.z)
        if r > arena.radius - 1.5:
            self.x *= (arena.radius - 1.5) / r
            self.z *= (arena.radius - 1.5) / r
        ground = arena.ground_height(self.x, self.z, self.y + 0.5)
        if not self.grounded:
            self.vy -= GRAVITY * dt
            self.y += self.vy * dt
            if self.y <= ground and self.vy <= 0:
                self.y = ground
                self.vy = 0.0
                self.grounded = True
        else:
            self.y = ground
        self.trail -= dt
        if self.trail <= 0:
            self.trail = 0.06
            game.pixels.emit((self.x, self.y + 0.3, self.z), (uniform(-1, 1), uniform(1, 2.5), uniform(-1, 1)),
                             'heart', uniform(0.06, 0.1), uniform(0.4, 0.7), 0, 3, gravity=-1.0, drag=2.0)

    def caught(self):
        game = self.game
        self.state = 'home'
        self.enabled = False
        game.pixels.show(self.centre, 2.5, 'heart', shape=False)
        game.particles.burst(self.centre, (1, 0.4, 0.55), count=40, speed=9, life=0.6, white=0.4)
        game.juice.shake(0.2)
        game.hud.notice('GOT IT!')
        game.hud.health.pour(T.HEART_HEAL, T.HEART_GLUGS)

    def draw(self):
        player = self.game.player
        self.position = (self.x, self.y, self.z)
        to = player.position - self.position
        self.heart.rotation_y = degrees(atan2(to.x, to.z)) + 180    # it keeps an eye on you as it runs
        self.legs.rotation_y = degrees(atan2(self.vx, self.vz)) + 180 if self.vx or self.vz else self.legs.rotation_y
        flight = 0.0 if self.grounded else min(1.0, abs(self.vy) / 8)
        self.heart.scale = (SIZE * (1 - 0.12 * flight), SIZE * (1 + 0.18 * flight), SIZE)
        self.heart.look(0, 0.2)
        # legs stride with the ground covered, arms pump against them; in the air they splay
        swing = sin(self.stride / STRIDE * pi) if self.grounded else 0.0
        for side, leg, arm in zip((-1, 1), self.leg, self.arm):
            leg.rotation_x = 40 * swing * side if self.grounded else -25
            arm.rotation_x = -50 * swing * side
            arm.rotation_z = -side * (40 if self.grounded else 75)
        self.heart.blink(1.0 if self.time_left % 2.3 < 0.1 else 0.0)
        left = max(0, int(self.time_left + 0.999))
        self.clock.text = str(left)
        self.clock.color = color.hsv(120 * min(1.0, self.time_left / T.HEART_TIME), 0.75, 1)
        self.halo.scale = 3.2 + 0.4 * sin(self.time_left * 8)

    def direction_hint(self):
        """'<< ', ' >>' or '' for the HUD: which way to turn to see it."""
        if not self.loose:
            return ''
        forward, right = camera.forward, camera.right
        to = self.centre - camera.world_position
        ahead = to.x * forward.x + to.z * forward.z
        across = to.x * right.x + to.z * right.z
        if ahead > 0 and abs(across) < ahead:
            return ''
        return ' >>' if across > 0 else '<< '
