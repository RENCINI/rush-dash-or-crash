"""The health bar, and the heart that lives at its end.

A chunky outlined socket with the heart's seat at its left end. In it, from the back: a white
ghost of health just lost, which bites and then slides away; the rally, the part of a recent hit
that can still be won back by hitting in Overdrive (striped pink, and glowing in the Rush colours
while Overdrive lasts); and the fill, which eases to the player's health in a colour that runs
from mint green down to hot red.

The heart in the seat is the runaway heart (game/heart.py). When it gets out it squeezes out of
its seat, comes to the middle of the screen to have a look round, and dashes off into the arena;
while it is loose the seat stands empty. When it comes back it plays one of two scenes on the
bar: caught, it tips itself up over the bar and pours the health back in; let go, it puts on a
boxing glove and punches some out. The health moves at the moment each glug or punch lands, on
game time.
"""
from math import cos, exp, pi, sin
from random import randint, uniform

from ursina import Entity, Mesh, Vec2, Vec3, camera, color

from data import tuning as T
from fx.popups import world_to_ui
from fx.toon import ball, barrel, build, disc, heart, loft, placed, plate
from ui.font import Label

X, Y = -0.805, -0.448           # the left end of the fill
WIDTH, HEIGHT = 0.3, 0.03
SEAT = (X - 0.038, Y + 0.002)   # where the heart sits
SEAT_SIZE = 0.024               # its scale there; a heart is about 2 units tall
LOW = 30                        # health under this throbs
GHOST_HOLD = 0.25
BOSS_WIDTH = 0.7
POPS = 6
CENTRE = (0.0, 0.06)            # where the heart shows itself off, in the middle of the screen
SOCKET = color.hsv(250, 0.35, 0.22)
HEART_RED = color.hsv(352, 0.82, 0.96)
HEART_PALE = color.hsv(350, 0.35, 1)
LID = color.hsv(352, 0.85, 0.78)
BLUSH = color.hsv(338, 0.5, 1)
GLOVE = color.hsv(5, 0.8, 0.9)
EYE_INK = color.hsv(250, 0.4, 0.12)
RALLY_PINK = color.hsv(345, 0.32, 1)
WHITE = (1, 1, 1)
EYE_Y, EYE_Z = 0.12, -0.3      # the middle of its eye
LID_OPEN, LID_SHUT = 90, -90    # the eyelid's tilt: open it lies back behind the eye, a rim round it


def fill_colour(t, bright=1.0):
    """Mint at full, through yellow and orange, to hot red when nearly empty."""
    hue = 150 * t ** 0.85 if t > 0.25 else 8 + 40 * t
    return color.hsv(hue, 0.78, bright)


def heart_parts(depth, z=0.0):
    """A flat heart as three convex solids, each to be given its colour: the seat's outline."""
    return heart(depth, z)


def heart_body():
    """A chubby heart about 2 tall and 2.1 wide round the origin, as deep as it is round: two
    lobes over a rounded point, each convex, for `build` to outline as one."""
    def ring(y, width):
        return [(width * sin(2 * pi * (i + 0.5) / 12), y, 0.43 * width * cos(2 * pi * (i + 0.5) / 12)) for i in range(12)]

    lobes = [ball(0.6, (side * 0.47, 0.32, 0), (1, 1, 0.72), rings=6, sides=12) for side in (-1, 1)]
    return lobes + [loft([ring(0.3, 1.0), ring(-0.25, 0.66), ring(-0.75, 0.28), [(0.0, -1.05, 0.0)]])]


def heart_meshes():
    """The runaway heart's parts, facing -z (toward a camera looking down +z): its body, its one
    eye, the pupil that looks about, the lid that blinks, a brow for when it is cross and the
    glove it punches with. Shared by the heart in the arena and the one on the bar."""
    body = [*[(part, HEART_RED) for part in heart_body()],
            (ball(0.13, (-0.62, 0.6, -0.33), (1.3, 0.9, 0.5), rings=4, sides=8), HEART_PALE),     # a shine
            *[(ball(0.13, (side * 0.62, -0.14, -0.27), (1.2, 0.7, 0.35), rings=4, sides=8), BLUSH)
              for side in (-1, 1)]]
    eye = [(ball(0.36, (0, EYE_Y, EYE_Z), (1, 1, 0.55), rings=6, sides=12), WHITE)]
    pupil = [(ball(0.15, (0, 0, -0.47), (1, 1, 0.45), rings=4, sides=10), EYE_INK),
             (ball(0.05, (-0.05, 0.05, -0.53), rings=3, sides=6), WHITE)]
    lid = [(ball(0.39, (0, 0, 0), (1, 1, 0.6), rings=6, sides=12, dome=True), LID)]
    brow = [(plate([(-0.48, 0.5), (0.42, 0.62), (0.44, 0.74), (-0.46, 0.66)], 0.08, z=-0.5), EYE_INK)]
    glove = [(ball(0.36, (0, 0, 0), (1, 0.9, 0.95), rings=6, sides=12), GLOVE),
             (ball(0.15, (-0.2, 0.22, -0.16), rings=4, sides=8), GLOVE),                       # the thumb
             (placed(barrel(0.24, -0.14, 0.14, sides=10), (-0.42, -0.05, 0), yaw=90), WHITE)]   # the cuff
    return {name: build(parts, 0.05) for name, parts in
            (('body', body), ('eye', eye), ('pupil', pupil), ('lid', lid), ('brow', brow), ('glove', glove))}


class Heart(Entity):
    """A heart built from `heart_meshes`, with the eye, pupil, lid, brow and glove as parts that
    can be moved and shown one at a time."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        meshes = heart_meshes()
        self.body = Entity(parent=self, model=meshes['body'])
        self.eye = Entity(parent=self, model=meshes['eye'])
        self.pupil = Entity(parent=self, model=meshes['pupil'], position=(0, EYE_Y, 0))
        self.lid = Entity(parent=self, model=meshes['lid'], position=(0, EYE_Y, EYE_Z), rotation_x=LID_OPEN)
        self.brow = Entity(parent=self, model=meshes['brow'], enabled=False)
        self.glove = Entity(parent=self, model=meshes['glove'], position=(1.25, -0.25, -0.1), enabled=False)

    def look(self, x, y):
        """Point the pupil: x and y run from -1 to 1. It rides round the front of the eye."""
        length = max(1.0, (x * x + y * y) ** 0.5)
        x, y = x / length, y / length
        self.pupil.position = (0.17 * x, EYE_Y + 0.17 * y, 0.03 * (x * x + y * y))

    def blink(self, shut):
        """0 is wide open, 1 shut: the lid rolls down over the eye."""
        self.lid.rotation_x = LID_OPEN + (LID_SHUT - LID_OPEN) * shut


class HealthBar(Entity):
    def __init__(self, hud):
        from ui.hud import edge_texture, stripes_texture     # ui.hud imports this module
        super().__init__(parent=hud)
        self.hud = hud
        self.game = hud.game
        self.player = hud.player
        self.clock = 0.0
        self.shown = 1.0            # the fill, as a share of full health, easing to the real one
        self.ghost_at = 1.0         # the white ghost behind it
        self.ghost_hold = 0.0
        self.shown_number = None
        self.bounce = 0.0           # the number jumps when it changes
        self.shake = 0.0
        self.bulge = 0.0            # the bar swells when health comes in
        self.sweep = 1.0            # a green flash runs along the fill after a heal: 0 to 1
        self.beat = 0.0             # time to the next heartbeat while health is low
        self.loose = False          # the heart is out in the arena: its seat is empty
        self.scenes = []            # waiting scenes: ('escape' | 'fill' | 'punch', amount, steps)
        self.scene = None
        self.slosh = 0.0            # the fill's end wobbles like a liquid while health pours in
        self.sparks = hud.sparks

        Entity(parent=self, position=(X - 0.004, Y), model=build(
            [(plate([(-0.004, -HEIGHT / 2 - 0.006), (WIDTH + 0.01, -HEIGHT / 2 - 0.006),
                     (WIDTH + 0.016, HEIGHT / 2 + 0.006), (0.002, HEIGHT / 2 + 0.006)], 0.01, 0.02), SOCKET)], 0.004))
        self.ghost = self.bar(0.015, color.white)
        self.rally_back = self.bar(0.0145, RALLY_PINK)
        self.rally = self.bar(0.014, RALLY_PINK, texture=stripes_texture())
        self.fill = self.bar(0.013, fill_colour(1))
        self.gloss = Entity(parent=self, model='quad', origin=(-0.5, 0), position=(X, Y + HEIGHT * 0.26, 0.012),
                            scale=(WIDTH, HEIGHT * 0.22), color=color.Color(1, 1, 1, 0.35))
        self.edge = Entity(parent=self, model='quad', position=(X, Y, 0.011), scale=(0.006, HEIGHT * 1.15),
                           color=color.white)
        self.flash = Entity(parent=self, model='quad', origin=(-0.5, 0), position=(X, Y, 0.0105),
                            scale=(0.04, HEIGHT), color=color.Color(1, 1, 1, 0))
        self.surface = Entity(parent=self, model=build([(plate(disc(0.5, steps=10), 0.1), (1, 1, 1))], 0.1),
                              position=(X, Y, 0.0108), scale=(0.012, HEIGHT), enabled=False)
        # the empty seat, and the heart that sits in it
        self.hollow = Entity(parent=self, position=(*SEAT, 0.01), scale=SEAT_SIZE, enabled=False,
                             model=build([(part, SOCKET) for part in heart_parts(0.1)], 0.08))
        self.heart = Heart(parent=self, position=(*SEAT, -0.02), scale=SEAT_SIZE)
        self.number = Label(parent=self, text='', origin=(-0.5, 0), position=(X, Y + 0.045, -0.02), scale=1.6)
        Label(parent=self, text='HP', origin=(-0.5, 0), position=(X + 0.075, Y + 0.04, -0.02), scale=0.8,
             color=color.hsv(230, 0.08, 0.78))
        self.pops = [Label(parent=self, text='', origin=(-0.5, 0), scale=1.3, enabled=False) for _ in range(POPS)]
        self.pop_life = [0.0] * POPS
        self.pop_cursor = 0
        self.crack = Entity(parent=self, model=crack_mesh(), scale=(0.05, 0.05), z=-0.026, color=color.white,
                            double_sided=True, enabled=False)
        self.word = Label(parent=self, text='', origin=(0, 0), scale=2.4, enabled=False)
        self.chase = Label(parent=hud, text='', origin=(0, 0), position=(0, 0.33), scale=1.5, letters=True, enabled=False)
        self.vignette = Entity(parent=hud, model='quad', texture=edge_texture(), scale=(1.8, 1), z=0.47,
                               color=color.Color(1, 0, 0.1, 0))

    def bar(self, z, tint, texture=None):
        return Entity(parent=self, model='quad', origin=(-0.5, 0), position=(X, Y, z), scale=(0.001, HEIGHT),
                      color=tint, texture=texture)

    # --- what the game tells it ---

    def healed(self, amount):
        if amount >= 1:
            self.sweep = 0.0
            self.bulge = 1.0
            self.pop(f'+{amount:.0f}', fill_colour(1))
            at = X + WIDTH * self.player.hp / T.PLAYER_HP
            self.sparks.spray((at, Y + HEIGHT / 2, -0.06), 'mint', count=5, speed=0.15, size=0.003, life=0.5, up=0.1)

    def hurt(self, amount):
        self.ghost_hold = GHOST_HOLD
        self.shake = min(1.0, 0.4 + amount / 30)
        if amount >= 1:
            self.pop(f'-{amount:.0f}', color.hsv(0, 0.75, 1))
            for _ in range(min(6, 2 + round(amount / 8))):
                self.shard(X + WIDTH * self.player.hp / T.PLAYER_HP)

    def rallied(self, amount):
        """Health won back by hitting in Overdrive."""
        self.sweep = min(self.sweep, 0.5)
        self.bulge = max(self.bulge, 0.5)
        if amount >= 1:
            self.pop(f'+{amount:.0f}', color.hsv((self.clock * 400) % 360, 0.6, 1))

    def escape(self, where):
        """The heart gets out: it leaves its seat, shows itself in the middle of the screen and
        dashes off toward `where`, the spot in the arena it will run from."""
        self.loose = True
        self.scenes.append(('escape', where, 1))

    def pour(self, amount, glugs):
        """Caught: the heart comes home and pours `amount` back in, in `glugs` goes."""
        self.scenes.append(('fill', amount, glugs))

    def punch(self, amount):
        """Let go: the heart comes home and punches `amount` out."""
        self.scenes.append(('punch', amount, 1))

    def reset(self):
        """A new level or a death: the heart is home and nothing is playing."""
        self.scenes.clear()
        self.end_scene()
        self.loose = False

    @property
    def busy(self):
        return self.scene is not None or bool(self.scenes)

    # --- frame ---

    def tick(self, dt):
        self.clock += dt
        player = self.player
        hp = max(0.0, player.hp) / T.PLAYER_HP
        rally = max(0.0, player.rally) / T.PLAYER_HP
        follow = 1 - exp(-14 * dt)
        self.shown += (hp - self.shown) * follow
        if hp > self.ghost_at:
            self.ghost_at = hp
        self.ghost_hold -= dt
        if self.ghost_hold <= 0:
            self.ghost_at += (self.shown - self.ghost_at) * (1 - exp(-5 * dt))
        shown = self.shown

        self.fill.scale_x = WIDTH * max(shown, 0.001)
        self.gloss.scale_x = WIDTH * max(shown, 0.001) * 0.97
        self.ghost.scale_x = WIDTH * max(self.ghost_at, 0.001)
        self.ghost.color = color.Color(1, 1, 1, 0.9 if self.ghost_hold > 0 else 0.6)
        self.edge.x = X + WIDTH * shown
        low = player.hp < LOW
        throb = abs(sin(self.clock * (6 + 6 * (1 - hp)))) if low else 0.0
        self.fill.color = fill_colour(shown, 0.85 + 0.15 * throb)
        self.edge.color = color.Color(1, 1, 1, 0.5 + 0.5 * abs(sin(self.clock * 9)))
        self.edge.enabled = shown > 0.01

        # the rally sits on top of the fill: it shines while it can be won back, and greys as it drains
        self.rally.enabled = self.rally_back.enabled = rally > 0.002
        if self.rally.enabled:
            self.rally.x = self.rally_back.x = X + WIDTH * shown
            self.rally.scale_x = self.rally_back.scale_x = WIDTH * min(rally, 1 - shown + 0.001)
            if player.rush.overdrive:
                tint = color.hsv((self.clock * 420) % 360, 0.55, 1)
                self.rally.color = color.Color(tint[0], tint[1], tint[2], 0.95)
                self.rally.set_shader_input('texture_offset', Vec2(-self.clock * 3, 0))
                self.rally_back.color = color.Color(tint[0], tint[1], tint[2], 0.55 + 0.25 * abs(sin(self.clock * 10)))
            else:
                fresh = 1.0 if player.rally_hold > 0 else 0.55
                self.rally.color = color.Color(RALLY_PINK[0] * fresh + 0.4 * (1 - fresh), RALLY_PINK[1] * fresh
                                               + 0.4 * (1 - fresh), RALLY_PINK[2] * fresh + 0.45 * (1 - fresh), 0.75)
                self.rally.set_shader_input('texture_offset', Vec2(-self.clock * 0.6, 0))
                self.rally_back.color = color.Color(self.rally.color[0], self.rally.color[1], self.rally.color[2], 0.35 * fresh)
            self.rally.set_shader_input('texture_scale', Vec2(self.rally.scale_x / HEIGHT * 0.5, 1))

        # a green sweep along the fill after a heal
        if self.sweep < 1:
            self.sweep = min(1.0, self.sweep + dt * 2.2)
            self.flash.x = X + WIDTH * shown * self.sweep - 0.02
            self.flash.color = color.Color(0.8, 1, 0.85, 0.8 * (1 - self.sweep))
        else:
            self.flash.color = color.Color(1, 1, 1, 0)

        number = max(0, round(player.hp))
        if number != self.shown_number:
            if self.shown_number is not None:
                self.bounce = 1.0
            self.shown_number = number
            self.number.text = str(number)
        self.bounce = max(0.0, self.bounce - dt * 4)
        self.number.scale = 1.6 * (1 + 0.35 * self.bounce + 0.12 * throb)
        self.number.color = fill_colour(shown) if not low else color.hsv(0, 0.6 + 0.3 * throb, 1)

        self.shake = max(0.0, self.shake - dt * 3)
        self.bulge = max(0.0, self.bulge - dt * 3)
        jitter = 0.012 * self.shake
        self.position = (uniform(-jitter, jitter), uniform(-jitter, jitter))
        tall = HEIGHT * (1 + 0.45 * self.bulge)
        for part in (self.ghost, self.rally_back, self.rally, self.fill, self.flash):
            part.scale_y = tall
        self.edge.scale_y = tall * 1.15

        # low health: the heart and the screen's edge beat together, quicker the lower it gets
        if low and player.hp > 0:
            self.beat -= dt
            if self.beat <= 0:
                self.beat = 0.45 + 0.5 * player.hp / LOW
                self.game.sfx.play('heartbeat', volume=0.5 + 0.4 * (1 - player.hp / LOW))
            pulse = max(0.0, 1 - (0.45 + 0.5 * player.hp / LOW - self.beat) * 4)
            self.vignette.color = color.Color(1, 0, 0.12, 0.12 + 0.28 * pulse)
        else:
            self.beat = 0.0
            pulse = 0.0
            self.vignette.color = color.Color(1, 0, 0.12, 0)

        # the slosh: a bright round end on the fill that bobs and stretches
        self.slosh = max(0.0, self.slosh - dt * 1.5)
        self.surface.enabled = self.slosh > 0 and shown > 0.01
        if self.surface.enabled:
            wobble = sin(self.clock * 26) * self.slosh
            self.surface.x = X + WIDTH * shown + 0.002 * wobble
            self.surface.scale = (0.01 + 0.008 * self.slosh + 0.004 * wobble, tall * (1 + 0.15 * wobble))
            tint = fill_colour(shown, 1.0)
            self.surface.color = color.Color(min(1, tint[0] + 0.25), min(1, tint[1] + 0.25), min(1, tint[2] + 0.25), 1)

        out = self.scene is not None and self.scene['kind'] == 'escape' and self.scene['t'] > 0.35
        self.hollow.enabled = self.loose and (out or not self.busy)
        runner = getattr(self.game, 'heart', None)
        self.chase.enabled = runner is not None and runner.state == 'run' and runner.wait <= 0
        if self.chase.enabled:
            hint = runner.direction_hint()
            left = max(0, int(runner.time_left + 0.999))
            words = f'CATCH THE HEART  {left}'
            self.chase.text = (hint + words) if hint.startswith('<') else (words + hint)
            hurry = runner.time_left < 5
            self.chase.color = color.hsv(345, 0.55 + 0.3 * abs(sin(self.clock * (12 if hurry else 4))), 1)
            # it beats like a heart, lub-dub, quicker as time runs out
            beat = (self.clock * (2.2 if hurry else 1.2)) % 1.0
            lub = max(0.0, 1 - abs(beat - 0.1) * 12) + 0.6 * max(0.0, 1 - abs(beat - 0.3) * 12)
            self.chase.scale = 1.5 * (1 + 0.12 * lub)
            if hurry:
                self.chase.jiggle(self.clock, amount=0.5)
            else:
                self.chase.wave(self.clock, height=0.6, speed=5)
        if self.scene is None and self.scenes:
            self.start_scene(*self.scenes.pop(0))
        if self.scene is not None:
            self.play_scene(dt)
        elif not self.loose:
            self.heart.enabled = True
            self.heart.position = (*SEAT, -0.02)
            self.heart.scale = SEAT_SIZE * (1 + 0.15 * pulse + 0.05 * abs(sin(self.clock * 3)))
            self.heart.rotation_z = 6 * sin(self.clock * 1.7)
            self.heart.look(0.6 * sin(self.clock * 0.7), 0.3 * sin(self.clock * 1.1))
            self.heart.blink(1.0 if self.clock % 3.7 < 0.12 else 0.0)
        else:
            self.heart.enabled = False

        self.move_bits(dt)

    # --- the heart's scenes ---

    def start_scene(self, kind, amount, steps):
        heart = self.heart
        heart.enabled = True
        heart.glove.enabled = heart.brow.enabled = kind == 'punch'
        self.scene = {'kind': kind, 'amount': amount, 'steps': steps, 'given': 0, 't': 0.0, 'from': CENTRE}
        if kind == 'escape':
            heart.position = (*SEAT, -0.02)
            heart.scale = SEAT_SIZE
        else:
            heart.position = (*CENTRE, -0.05)
            heart.scale = 0.0
            self.game.sfx.play('catch' if kind == 'fill' else 'giggle', volume=0.8)

    def end_scene(self):
        heart = self.heart
        heart.glove.enabled = heart.brow.enabled = False
        heart.rotation_z = 0
        heart.blink(0)
        self.scene = None

    def play_scene(self, dt):
        scene = self.scene
        scene['t'] += dt
        if scene['kind'] == 'escape':
            self.play_escape(scene)
        elif scene['kind'] == 'fill':
            self.play_fill(scene)
        else:
            self.play_punch(scene)

    def fly(self, t, start, end, size_from, size_to, spin=0.0):
        """Move the heart along an arc from `start` to `end` as t goes 0 to 1."""
        e = 1 - (1 - min(max(t, 0.0), 1.0)) ** 3
        x = start[0] + (end[0] - start[0]) * e
        y = start[1] + (end[1] - start[1]) * e + 0.08 * sin(pi * e)
        self.heart.position = (x, y, -0.05)
        self.heart.scale = size_from + (size_to - size_from) * e
        self.heart.rotation_z = spin * (1 - e)

    def play_escape(self, scene):
        t = scene['t']
        heart = self.heart
        wake, rise, show = 0.35, 0.45, 0.25
        leave = T.HEART_ESCAPE - wake - rise - show
        big = 0.1
        if t < wake:
            # it wakes with a start and wriggles in its seat
            u = t / wake
            heart.position = (SEAT[0], SEAT[1] + 0.004 * abs(sin(t * 40)), -0.02)
            heart.scale = SEAT_SIZE * (1 + 0.35 * u)
            heart.rotation_z = 18 * sin(t * 45) * u
            heart.blink(0)
            heart.look(0.8, 0.8)
            return
        t -= wake
        if scene['given'] == 0:
            # out it pops
            scene['given'] = 1
            self.sparks.spray((SEAT[0], SEAT[1], -0.06), 'heart', count=18, speed=0.5, size=0.005, life=0.6, up=0.2)
            self.game.sfx.play('giggle')
        if t < rise:
            self.fly(t / rise, SEAT, CENTRE, SEAT_SIZE * 1.35, big, spin=-360)
            heart.look(0.3, -0.2)
            return
        t -= rise
        if t < show:
            # a look round, and a wink
            u = t / show
            heart.position = (CENTRE[0], CENTRE[1] + 0.01 * sin(u * pi), -0.05)
            heart.scale = big * (1 + 0.06 * sin(u * pi * 4))
            heart.rotation_z = 8 * sin(u * pi * 2)
            heart.look(sin(u * pi * 2.5), 0.1)
            heart.blink(1.0 if 0.55 < u < 0.8 else 0.0)
            return
        t -= show
        if scene['given'] == 1:
            scene['given'] = 2
            where = world_to_ui(scene['amount']) if scene['amount'] is not None else None
            edge = camera.aspect_ratio / 2
            if where is None or abs(where[0]) > edge or abs(where[1]) > 0.5:
                side = 1 if where is None or where[0] >= 0 else -1
                where = (side * (edge + 0.1), -0.1)
            scene['to'] = where
        if t < leave:
            # off it dashes, shrinking into the distance, a trail of pink behind it
            u = t / leave
            e = u * u
            to = scene['to']
            heart.position = (CENTRE[0] + (to[0] - CENTRE[0]) * e, CENTRE[1] + (to[1] - CENTRE[1]) * e
                              + 0.05 * sin(pi * u), -0.05)
            heart.scale = big * (1 - 0.92 * e)
            heart.rotation_z = -25 if to[0] > 0 else 25
            heart.look(1 if to[0] > 0 else -1, 0)
            self.sparks.emit((heart.x, heart.y, -0.06), (uniform(-0.05, 0.05), uniform(0.0, 0.1), 0), 'heart',
                             0.004 * (1 - e) + 0.002, 0.4, 0, 4, gravity=0.3, drag=2.0)
            return
        heart.enabled = False
        self.end_scene()

    def play_fill(self, scene):
        t = scene['t']
        heart = self.heart
        arrive, tip, each, done, leave = 0.5, 0.25, 0.38, 0.35, 0.45
        steps = scene['steps']
        size = 0.055
        edge = X + WIDTH * min(1.0, self.player.hp / T.PLAYER_HP)
        over = (edge - 0.012, Y + 0.075)
        if t < arrive:
            self.fly(t / arrive, scene['from'], over, 0.0, size, spin=-540)
            heart.look(0.4, -0.7)
            return
        t -= arrive
        if t < tip:
            # it tips itself up over the bar like a jug
            u = 1 - (1 - t / tip) ** 2
            heart.position = (over[0], over[1], -0.05)
            heart.rotation_z = 140 * u
            heart.look(0.8, -0.8)
            return
        t -= tip
        k = int(t // each)
        tipped = (edge - 0.012, Y + 0.075)
        if k < steps:
            # a glug: it squeezes, a gush of red pours into the bar, and the heart is that much emptier
            u = (t - k * each) / each
            squeeze = sin(pi * min(u / 0.4, 1.0)) if u < 0.4 else 0.0
            empty = 1 - 0.4 * (k + u) / steps
            heart.position = (tipped[0], tipped[1] + 0.006 * squeeze, -0.05)
            heart.scale = (size * empty * (1 - 0.18 * squeeze), size * empty * (1 + 0.12 * squeeze), size * empty)
            heart.rotation_z = 140 + 10 * squeeze
            heart.blink(0.6 * squeeze)
            heart.look(1, -1)
            mouth = (tipped[0] + 0.8 * size * empty, tipped[1] - 0.25 * size * empty)
            if u < 0.55:
                for _ in range(2):
                    self.sparks.emit((mouth[0] + uniform(-0.003, 0.003), mouth[1], -0.06),
                                     (uniform(-0.01, 0.03), uniform(-0.25, -0.15), 0), 'heart', uniform(0.0025, 0.004),
                                     uniform(0.18, 0.24), randint(0, 1), 2, gravity=1.5, drag=0.5)
            if k >= scene['given'] and u >= 0.3:
                scene['given'] = k + 1
                share = scene['amount'] / steps
                self.hud.heal_flash(self.player.heal(share))
                self.slosh = 1.0
                self.game.sfx.play('glug', pitch=1.0 + 0.08 * k)
                at = X + WIDTH * min(1.0, self.player.hp / T.PLAYER_HP)
                self.sparks.spray((at, Y + HEIGHT / 2, -0.06), 'mint', count=6, speed=0.2, size=0.003, life=0.5, up=0.12)
            return
        t -= steps * each
        if t < done:
            # empty: it pops back to its full size, and winks
            u = t / done
            pop = 1 + 0.35 * sin(pi * min(u * 2, 1.0))
            heart.scale = size * (0.6 + 0.4 * min(1.0, u * 3)) * pop
            heart.rotation_z = 140 * (1 - min(1.0, u * 3))
            heart.blink(1.0 if 0.4 < u < 0.7 else 0.0)
            heart.look(0, 0)
            if scene['given'] == steps:
                scene['given'] += 1
                self.sparks.spray((heart.x, heart.y, -0.06), 'heart', count=14, speed=0.35, size=0.004, life=0.6, up=0.1)
                self.sparks.spray((heart.x, heart.y, -0.06), 'mint', count=10, speed=0.3, size=0.003, life=0.6, up=0.1)
            return
        t -= done
        if t < leave:
            self.fly(t / leave, (heart.x, heart.y), SEAT, size, SEAT_SIZE)
            return
        self.loose = False
        self.end_scene()

    def play_punch(self, scene):
        t = scene['t']
        heart = self.heart
        arrive, wind, after, leave = 0.5, 0.45, 0.6, 0.45
        spot = (X + WIDTH * 0.62, Y + 0.06)
        if t < arrive:
            self.fly(t / arrive, scene['from'], spot, 0.0, 0.055, spin=360)
            heart.look(-0.6, -0.6)
            return
        t -= arrive
        if t < wind:
            # the glove drawn back, shaking with the effort
            u = t / wind
            heart.position = (spot[0] + 0.03 * u + uniform(-0.002, 0.002) * u, spot[1] + 0.01 * u, -0.05)
            heart.rotation_z = 25 * u
            heart.glove.position = (1.25 + 0.5 * u, -0.25 + 0.3 * u, -0.1)
            heart.look(-1, -0.8)
            return
        t -= wind
        if scene['given'] == 0:
            scene['given'] = 1
            taken = self.player.knock_hp(scene['amount'])
            at = X + WIDTH * self.player.hp / T.PLAYER_HP
            self.hurt(max(taken, 1))
            self.shake = 1.0
            self.crack.position = (at, Y, -0.026)
            self.crack.rotation_z = uniform(-20, 20)
            self.crack.enabled = True
            self.word.text = 'POW!'
            self.word.position = (at + 0.02, Y + 0.075, -0.03)
            self.word.color = color.hsv(48, 0.9, 1)
            self.word.enabled = True
            self.hud.hurt_flash()
            self.game.sfx.play('whack')
            self.game.juice.shake(0.25)
        if t < after:
            u = t / after
            heart.position = (spot[0] - 0.05 * (1 - u) ** 2, spot[1] - 0.02 * (1 - u), -0.05)
            heart.rotation_z = -20 * (1 - u)
            heart.glove.position = (1.25 - 0.6 * (1 - u) ** 2, -0.25, -0.1)
            heart.look(0.3, 0.6 * sin(t * 30))        # pleased with itself
            self.crack.color = color.Color(1, 1, 1, 1 - u)
            self.word.scale = 2.4 * (1 + 0.5 * (1 - u))
            self.word.color = color.Color(1, 0.85, 0.2, 1 - u * u)
            return
        self.crack.enabled = self.word.enabled = False
        t -= after
        if t < leave:
            self.fly(t / leave, spot, SEAT, 0.055, SEAT_SIZE, spin=-200)
            heart.glove.enabled = False
            return
        self.loose = False
        self.end_scene()

    # --- bits that fly off the bar ---

    def pop(self, text, tint):
        i = self.pop_cursor
        self.pop_cursor = (i + 1) % POPS
        label = self.pops[i]
        label.text = text
        label.color = tint
        label.position = (X + WIDTH * self.shown + 0.01, Y + 0.02, -0.03)
        label.enabled = True
        self.pop_life[i] = 0.8

    def shard(self, x):
        """A pixel chipped off the bar's end."""
        self.sparks.emit((x, Y + uniform(-HEIGHT / 2, HEIGHT / 2), -0.06), (uniform(0.05, 0.35), uniform(0.05, 0.45), 0),
                         'hurt', uniform(0.003, 0.0055), uniform(0.35, 0.6), randint(0, 2), 5, gravity=1.2, drag=0.5)

    def move_bits(self, dt):
        for i, label in enumerate(self.pops):
            if self.pop_life[i] <= 0:
                continue
            self.pop_life[i] -= dt
            label.y += dt * 0.06
            label.color = color.Color(label.color[0], label.color[1], label.color[2], min(1.0, self.pop_life[i] * 2))
            label.enabled = self.pop_life[i] > 0


class BossBar(Entity):
    """The miniboss's health, wide across the top of the screen under its name."""

    def __init__(self, hud):
        super().__init__(parent=hud, y=0.315, enabled=False)
        self.hud = hud
        self.enemy = None
        self.shown = 1.0
        self.ghost_at = 1.0
        self.ghost_hold = 0.0
        self.last = 1.0
        self.shake = 0.0
        self.clock = 0.0
        width, height = BOSS_WIDTH, 0.026
        Entity(parent=self, x=-width / 2 - 0.006, model=build(
            [(plate([(-0.006, -height / 2 - 0.007), (width + 0.012, -height / 2 - 0.007),
                     (width + 0.018, height / 2 + 0.007), (0.0, height / 2 + 0.007)], 0.01, 0.02), SOCKET)], 0.004))
        self.ghost = Entity(parent=self, model='quad', origin=(-0.5, 0), x=-width / 2, z=0.015, scale=(width, height),
                            color=color.white)
        self.fill = Entity(parent=self, model='quad', origin=(-0.5, 0), x=-width / 2, z=0.013, scale=(width, height),
                           color=color.hsv(355, 0.8, 0.95))
        self.gloss = Entity(parent=self, model='quad', origin=(-0.5, 0), position=(-width / 2, height * 0.26, 0.012),
                            scale=(width, height * 0.22), color=color.Color(1, 1, 1, 0.3))
        self.label = Label(parent=self, text='', origin=(0, 0), y=0.04, scale=1.5, color=color.hsv(355, 0.5, 1),
                           letters=True)
        self.appear = 9.0       # seconds since it came up: it slams in and its name drops in letter by letter

    def show(self, enemy):
        self.enemy = enemy
        self.enabled = enemy is not None
        self.shown = self.ghost_at = self.last = 1.0
        self.appear = 0.0
        if enemy is not None:
            self.label.text = enemy.boss.name

    def hide(self):
        self.enemy = None
        self.enabled = False

    def tick(self, dt):
        if self.enemy is None:
            return
        self.clock += dt
        enemy = self.enemy
        left = max(0.0, enemy.hp / enemy.max_hp) if enemy.alive else 0.0
        if left < self.last - 0.001:
            self.ghost_hold = GHOST_HOLD
            self.shake = min(1.0, self.shake + (self.last - left) * 6)
            end = self.getPos(self.hud) + Vec3(-BOSS_WIDTH / 2 + BOSS_WIDTH * left, 0, -0.06)
            self.hud.sparks.spray(end, 'hurt', count=min(6, 1 + int((self.last - left) * 60)), speed=0.25,
                                  size=0.004, life=0.5, up=0.12)
        self.last = left
        self.shown += (left - self.shown) * (1 - exp(-16 * dt))
        self.ghost_hold -= dt
        if self.ghost_hold <= 0:
            self.ghost_at += (self.shown - self.ghost_at) * (1 - exp(-4 * dt))
        self.fill.scale_x = BOSS_WIDTH * max(self.shown, 0.001)
        self.gloss.scale_x = BOSS_WIDTH * max(self.shown, 0.001)
        self.ghost.scale_x = BOSS_WIDTH * max(self.ghost_at, 0.001)
        self.fill.color = color.hsv(355 - 30 * (1 - self.shown), 0.8, 0.85 + 0.15 * abs(sin(self.clock * 3)))
        self.shake = max(0.0, self.shake - dt * 4)
        jitter = 0.008 * self.shake
        self.x, self.y = uniform(-jitter, jitter), 0.315 + uniform(-jitter, jitter)
        self.appear += dt
        self.label.scale = 1.5 * (1 + 0.1 * self.shake)
        if self.appear < 1.2:
            self.label.drop_in(self.appear)
            t = min(self.appear / 0.3, 1.0) - 1
            self.scale = 1 + 2.70158 * t ** 3 + 1.70158 * t ** 2 + (0.6 * (1 - self.appear / 0.3) if self.appear < 0.3 else 0)
        else:
            self.scale = 1


def crack_mesh():
    """A starburst of zig-zag cracks, as thin triangles."""
    vertices = []
    for k in range(6):
        a = 2 * pi * k / 6 + uniform(-0.3, 0.3)
        r0, r1 = 0.0, uniform(0.5, 1.0)
        bend = a + uniform(-0.4, 0.4)
        mid = (cos(a) * r1 * 0.5, sin(a) * r1 * 0.5)
        tip = (cos(bend) * r1, sin(bend) * r1)
        w = 0.06
        vertices += [(cos(a + pi / 2) * w, sin(a + pi / 2) * w, 0), (mid[0], mid[1], 0), (cos(a - pi / 2) * w, sin(a - pi / 2) * w, 0),
                     (mid[0] + cos(a + pi / 2) * w * 0.6, mid[1] + sin(a + pi / 2) * w * 0.6, 0), (tip[0], tip[1], 0),
                     (mid[0] + cos(a - pi / 2) * w * 0.6, mid[1] + sin(a - pi / 2) * w * 0.6, 0)]
    return Mesh(vertices=vertices, mode='triangle', static=True)
