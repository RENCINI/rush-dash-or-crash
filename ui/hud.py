from colorsys import hsv_to_rgb
from math import atan2, cos, degrees, exp, pi, sin
from random import Random, choice, uniform

from PIL import Image, ImageDraw
from ursina import Entity, Mesh, Texture, Vec2, Vec3, camera, clamp, color, time

from data import tuning as T
from data.controls import key_name
from fx.pixels import Pixels
from fx.toon import build, disc, plate
from ui.font import Label
from ui.health import BossBar, HealthBar
from ui.score import ScoreHud

DIM = color.hsv(0, 0, 1, 0.18)
INK = color.Color(0.08, 0.07, 0.15, 1)      # the outline colour the weapons use
GOLD = color.hsv(46, 0.75, 1)
BLAST_TIME = 0.16
BANNER_TIME = 2.4           # a round's name stays up this long
NOTICE_TIME = 3.0
DASH_Y = -0.122             # the dash charges, under the speed bar's multiplier and drive pips
DASH_WIDTH, DASH_HEIGHT, DASH_LEAN, DASH_GAP = 0.04, 0.02, 0.01, 0.064
DASH_READY = color.hsv(190, 0.75, 1)
DASH_FILLING = color.hsv(205, 0.45, 0.6)
HEAL_TIME = 0.5
HEAL = color.hsv(160, 0.45, 1)          # mint: health back is not the parry green
HURT = color.hsv(0, 0.75, 1)
SLOT_GAP = 0.036            # between rows of the weapon list
PARRY = color.hsv(T.GREEN_HUE, 0.7, 1)

BAR_X, BAR_Y = -0.79, -0.235    # bottom centre of the speed bar
BAR_WIDTH, BAR_HEIGHT = 0.058, 0.5
# (share of the bar, hue): cyan at the bottom through green, yellow and orange to pink
BAR_HUES = ((0.0, 190), (0.3, 140), (0.55, 58), (0.78, 22), (1.0, -35))
BOLT_SHAPES = 12
BOLTS = 6
SPARKS = 22
SPARK_TINTS = (color.white, color.hsv(190, 0.4, 1), color.hsv(55, 0.5, 1), color.hsv(310, 0.4, 1))


def help_text():
    """The controls as they are bound right now: three short lines for the foot of the screen."""
    move = ' '.join(key_name(key) for key in (T.KEY_FORWARD, T.KEY_LEFT, T.KEY_BACK, T.KEY_RIGHT))
    slide = ' or '.join(key_name(key) for key in T.KEYS_SLIDE)
    weapons = ' '.join(key_name(key) for key in T.KEYS_WEAPON)
    return (f'{move} move   {key_name(T.KEY_JUMP)} jump / wall-kick   {key_name(T.KEY_DASH)} dash   {slide} slide\n'
            f'{key_name(T.KEY_FIRE)} fire   {key_name(T.KEY_SCOPE)} scope / sticky   {weapons} weapons   '
            f'{key_name(T.KEY_RELOAD)} reload\n'
            f'{key_name(T.KEY_KATANA)} katana: parry anything GREEN   ESC menu')


def tick_model():
    """One stroke of the hit marker: an outlined bar, one unit tall."""
    return build([(plate([(-0.11, -0.5), (0.11, -0.5), (0.11, 0.5), (-0.11, 0.5)], 0.1), (1, 1, 1))], 0.07)


def diamond_model():
    """A drive charge: an outlined diamond, one unit across."""
    return build([(plate([(0, -0.5), (0.5, 0), (0, 0.5), (-0.5, 0)], 0.1), (1, 1, 1))], 0.1)


def arrow_model():
    """A chunky outlined arrowhead pointing along +y, one unit long."""
    return build([(plate([(0, 0.5), (0.45, -0.3), (0.16, -0.18), (0.16, -0.5), (-0.16, -0.5), (-0.16, -0.18),
                          (-0.45, -0.3)][::-1], 0.1), (1, 1, 1))], 0.08)


def rush_colour(t):
    """Cyan at empty, through green and yellow, to magenta at full."""
    return color.hsv((180 - 220 * t) % 360, 0.85, 1)


def player_colour(hue):
    """The colour picked on the menu; white while the weapons keep their own paint."""
    return color.white if hue is None else color.hsv(hue, 0.62, 1)


def streak_mesh(seed, count=34):
    """Thin triangles pointing at the screen centre, clear at the tip and solid at the rim."""
    rng = Random(seed)
    vertices, colours = [], []
    for _ in range(count):
        a = rng.uniform(0, 2 * pi)
        inner, outer = rng.uniform(0.42, 0.7), rng.uniform(0.95, 1.2)
        half = rng.uniform(0.004, 0.012)
        vertices += [(sin(a) * inner, cos(a) * inner, 0),
                     (sin(a - half) * outer, cos(a - half) * outer, 0),
                     (sin(a + half) * outer, cos(a + half) * outer, 0)]
        colours += [(1, 1, 1, 0), (1, 1, 1, 1), (1, 1, 1, 1)]
    return Mesh(vertices=vertices, colors=colours, mode='triangle', static=True)


# --- textures drawn once at start-up ---

def bar_hue(t):
    for (t0, h0), (t1, h1) in zip(BAR_HUES, BAR_HUES[1:]):
        if t <= t1:
            return h0 + (h1 - h0) * (t - t0) / (t1 - t0)
    return BAR_HUES[-1][1]


def tube_texture(hue_at, width=32, height=256):
    """Vertical colour ramp shaded like a glossy tube: bright stripe on the left, dark right edge."""
    image = Image.new('RGBA', (width, height))
    pixels = image.load()
    for y in range(height):
        hue = hue_at(1 - y / (height - 1)) % 360 / 360
        for x in range(width):
            u = x / (width - 1)
            gloss = max(0.0, 1 - abs(u - 0.26) / 0.13) * 0.45
            value = 1.0 if u < 0.72 else 1.0 - (u - 0.72) * 1.1
            r, g, b = hsv_to_rgb(hue, 0.78 * (1 - gloss), value)
            pixels[x, y] = (int(r * 255), int(g * 255), int(b * 255), 255)
    return Texture(image, filtering='bilinear')


def stripes_texture(size=64):
    """Slanted light bands that tile, scrolled up the bar as moving energy."""
    image = Image.new('RGBA', (size, size))
    pixels = image.load()
    for y in range(size):
        for x in range(size):
            wave = max(0.0, sin(2 * pi * (y + x * 0.5) / size)) ** 3
            pixels[x, y] = (255, 255, 255, int(255 * wave))
    return Texture(image, filtering='bilinear')


def edge_texture(size=64):
    """Clear in the middle and solid at the rim: a colour that closes in round the screen."""
    image = Image.new('RGBA', (size, size))
    pixels = image.load()
    half = (size - 1) / 2
    for y in range(size):
        for x in range(size):
            d = max(abs(x - half), abs(y - half)) / half
            pixels[x, y] = (255, 255, 255, int(255 * d ** 2.5))
    return Texture(image, filtering='bilinear')


def glow_texture(size=64):
    image = Image.new('RGBA', (size, size))
    pixels = image.load()
    half = (size - 1) / 2
    for y in range(size):
        for x in range(size):
            d = min(1.0, (((x - half) / half) ** 2 + ((y - half) / half) ** 2) ** 0.5)
            pixels[x, y] = (255, 255, 255, int(255 * (1 - d) ** 2))
    return Texture(image, filtering='bilinear')


def scope_texture(kind='cross', width=1024, height=512):
    """What is seen through a rifle's sight: a dark mask with a window in it and the marks to aim
    by. 'cross' is the plain rifle's round glass and cross lines; 'dragon' a narrower red glass
    ringed with teeth, with a chevron to aim by; 'holo' a wide open frame with a ring and a dot."""
    big = 2     # drawn oversized then shrunk, for smooth edges
    w, h = width * big, height * big
    cx, cy = w // 2, h // 2
    ink = (20, 18, 38, 255)
    if kind == 'holo':
        image = Image.new('RGBA', (w, h), (10, 16, 34, 150))
        draw = ImageDraw.Draw(image)
        rx, ry = int(h * 0.62), int(h * 0.42)
        frame = (cx - rx, cy - ry, cx + rx, cy + ry)
        draw.rounded_rectangle((frame[0] - 30, frame[1] - 30, frame[2] + 30, frame[3] + 30), 110, fill=ink)
        draw.rounded_rectangle((frame[0] - 12, frame[1] - 12, frame[2] + 12, frame[3] + 12), 96, fill=(90, 220, 255, 255))
        draw.rounded_rectangle(frame, 86, fill=(60, 200, 255, 22))
        mark = (255, 70, 60, 235)
        r = int(h * 0.075)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=mark, width=7)
        draw.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=mark)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            draw.line((cx + dx * r, cy + dy * r, cx + dx * (r + 26), cy + dy * (r + 26)), fill=mark, width=7)
        return Texture(image.resize((width, height), Image.LANCZOS), filtering='bilinear')

    dragon = kind == 'dragon'
    rim = (255, 120, 50, 255) if dragon else (120, 205, 150, 255)
    image = Image.new('RGBA', (w, h), (30, 10, 12, 244) if dragon else (16, 13, 32, 238))
    draw = ImageDraw.Draw(image)
    r = int(h * (0.38 if dragon else 0.43))
    draw.ellipse((cx - r - 26, cy - r - 26, cx + r + 26, cy + r + 26), fill=ink)
    draw.ellipse((cx - r - 14, cy - r - 14, cx + r + 14, cy + r + 14), fill=rim)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ink)
    draw.ellipse((cx - r + 10, cy - r + 10, cx + r - 10, cy + r - 10), fill=(255, 90, 30, 16) if dragon else (0, 0, 0, 0))
    line = (20, 18, 38, 215)
    if dragon:
        # teeth all round the glass, and a chevron under a dot in place of cross lines
        for i in range(24):
            a = 2 * pi * i / 24
            tip = (cx + sin(a) * (r - 64), cy + cos(a) * (r - 64))
            base = [(cx + sin(a + d) * (r - 6), cy + cos(a + d) * (r - 6)) for d in (-0.07, 0.07)]
            draw.polygon([tip, *base], fill=ink)
        mark = (255, 70, 30, 240)
        draw.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), fill=mark)
        for i, drop in enumerate((36, 96, 156)):
            half = 44 - i * 10
            draw.line((cx - half, cy + drop + half * 0.6, cx, cy + drop, cx + half, cy + drop + half * 0.6),
                      fill=mark, width=9 - i * 2, joint='curve')
        for side in (-1, 1):
            draw.line((cx + side * 70, cy, cx + side * (r - 80), cy), fill=line, width=6)
        return Texture(image.resize((width, height), Image.LANCZOS), filtering='bilinear')
    gap = int(r * 0.09)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        draw.line((cx + dx * gap, cy + dy * gap, cx + dx * (r - 10), cy + dy * (r - 10)), fill=line, width=5)
        thick = (cx + dx * r * 0.55, cy + dy * r * 0.55, cx + dx * (r - 10), cy + dy * (r - 10))
        draw.line(thick, fill=line, width=16)
    return Texture(image.resize((width, height), Image.LANCZOS), filtering='bilinear')


def ring_texture(size=256):
    big = 2
    s = size * big
    image = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, s - 8, s - 8), outline=(255, 255, 255, 255), width=int(s * 0.07))
    return Texture(image.resize((size, size), Image.LANCZOS), filtering='bilinear')


def bolt_mesh(seed, segments=9, half=0.1):
    """A jagged strip from (0, 0) to (0, 1) with one short fork."""
    rng = Random(seed)
    spine = [(0 if i in (0, segments) else rng.uniform(-0.5, 0.5), i / segments) for i in range(segments + 1)]
    start = rng.randrange(2, segments - 2)
    side = rng.choice((-1, 1))
    fork = [spine[start]] + [(spine[start][0] + side * 0.35 * i + rng.uniform(-0.15, 0.15),
                              spine[start][1] + 0.09 * i) for i in (1, 2)]
    vertices = []
    for path, width in ((spine, half), (fork, half * 0.6)):
        for (x0, y0), (x1, y1) in zip(path, path[1:]):
            vertices += [(x0 - width, y0, 0), (x0 + width, y0, 0), (x1 + width, y1, 0),
                         (x0 - width, y0, 0), (x1 + width, y1, 0), (x1 - width, y1, 0)]
    return Mesh(vertices=vertices, mode='triangle', static=True)


def dash_shape(width, grow=0.0):
    """A dash charge seen from the front: a bar leaning the way the player is going."""
    h = DASH_HEIGHT / 2 + grow
    return [(-grow, -h), (width + grow, -h), (width + DASH_LEAN + grow, h), (DASH_LEAN - grow, h)]


class SpeedBar(Entity):
    """Tall meter at the left edge. It fills with Rush, shows speed and the damage
    multiplier, and throws lightning while Overdrive lasts."""

    def __init__(self, hud):
        super().__init__(parent=hud, position=(BAR_X, BAR_Y))
        self.game = hud.game
        self.player = hud.player
        self.shown = 0.0            # fill, eased toward the Rush meter
        self.needle_at = 0.0
        self.quarter = 0            # highest quarter mark already announced
        self.overdrive = False
        self.punch = 0.0            # 1 at the moment Overdrive starts
        self.speed_punch = 0.0
        self.last_speed = 0.0
        self.shown_speed = -1
        self.shown_multiplier = -1
        self.clock = 0.0
        self.flicker = 0.0
        self.next_zap = 0.0

        w, h = BAR_WIDTH, BAR_HEIGHT
        self.gradient = tube_texture(bar_hue)
        self.rainbow = tube_texture(lambda t: 360 * t)
        self.glow = Entity(parent=self, model='quad', texture=glow_texture(), scale=(w * 6, h * 1.5), y=h / 2,
                           z=0.4)
        Entity(parent=self, model='quad', origin=(0, -0.5), scale=(w + 0.02, h + 0.02), y=-0.01, z=0.3, color=INK)
        Entity(parent=self, model='quad', origin=(0, -0.5), scale=(w, h), z=0.25, color=color.hsv(250, 0.35, 0.24))
        self.fill = Entity(parent=self, model='quad', origin=(0, -0.5), scale=(w, 0.001), z=0.2, texture=self.gradient)
        self.energy = Entity(parent=self, model='quad', origin=(0, -0.5), scale=(w, 0.001), z=0.15,
                             texture=stripes_texture())
        for mark in (0.25, 0.5, 0.75):
            Entity(parent=self, model='quad', scale=(w, 0.004), y=h * mark, z=0.1, color=color.Color(0, 0, 0, 0.45))
        # where Overdrive lets go, and a needle for the speed of this very instant
        Entity(parent=self, model='quad', scale=(0.014, 0.005), position=(w / 2 + 0.019, h * T.OVERDRIVE_EXIT / 100),
               color=color.hsv(0, 0, 1, 0.7))
        self.cap = Entity(parent=self, model='quad', scale=(w + 0.014, 0.008), z=0.05)
        arrow = Mesh(vertices=[(-1, 0.6, 0), (-1, -0.6, 0), (0, 0, 0)], mode='triangle', static=True)
        self.needle = Entity(parent=self, model=arrow, scale=0.017, x=-w / 2 - 0.014, double_sided=True)
        self.flash = Entity(parent=self, model='quad', origin=(0, -0.5), scale=(w, h), z=0.02,
                            color=color.Color(1, 1, 1, 0))

        self.number = Label(parent=self, text='0', origin=(0, 0), position=(0, h + 0.092, -0.1), scale=2.8)
        Label(parent=self, text='SPEED', origin=(0, 0), position=(0, h + 0.03, -0.1), scale=0.7,
             color=color.hsv(230, 0.08, 0.8))
        self.multiplier = Label(parent=self, text='x0.50', origin=(0, 0), position=(0, -0.05, -0.1), scale=1.5)
        # drive charges, earned by parrying
        self.drive_pips = [Entity(parent=self, model=diamond_model(), scale=0.016, z=-0.1,
                                  position=((i - (T.DRIVE_MAX - 1) / 2) * 0.026, -0.088), color=DIM)
                           for i in range(T.DRIVE_MAX)]
        self.shown_drive = 0
        # dash charges: a cartoon socket for each, and a bar in it that fills as the charge comes back
        self.dashes = []
        for i in range(T.DASH_CHARGES):
            x = (i - T.DASH_CHARGES / 2) * DASH_GAP + (DASH_GAP - DASH_WIDTH - DASH_LEAN) / 2
            Entity(parent=self, position=(x, DASH_Y, -0.1),
                   model=build([(plate(dash_shape(DASH_WIDTH, 0.004), 0.012, 0.012), color.hsv(250, 0.35, 0.3))], 0.004))
            fill = Entity(parent=self, position=(x, DASH_Y, -0.13),
                          model=build([(plate(dash_shape(DASH_WIDTH), 0.02), (1, 1, 1))], 0.0025))
            self.dashes.append({'fill': fill, 'ready': True, 'pop': 0.0})

        shapes = [bolt_mesh(seed) for seed in range(BOLT_SHAPES)]
        self.bolt_shapes = shapes
        self.bolts = [Entity(parent=self, model=shapes[i], z=-0.05, double_sided=True, enabled=False)
                      for i in range(BOLTS)]
        self.sparks = [{'entity': Entity(parent=self, model='quad', z=-0.06, enabled=False), 'life': 0.0,
                        'vx': 0.0, 'vy': 0.0} for _ in range(SPARKS)]
        self.spark_cursor = 0

    def tick(self, dt):
        rush = self.player.rush
        speed = self.player.speed
        self.clock += dt
        self.shown += (rush.fraction - self.shown) * (1 - exp(-T.BAR_FOLLOW * dt))
        shown = self.shown
        over = rush.overdrive
        if over != self.overdrive:
            self.overdrive = over
            self.fill.texture = self.rainbow if over else self.gradient
            if over:
                self.punch = 1.0
                for _ in range(SPARKS):
                    self.spark(uniform(0, BAR_HEIGHT), burst=True)
            else:
                for bolt in self.bolts:
                    bolt.enabled = False
        self.punch = max(0.0, self.punch - dt * 2.2)
        cycle = color.hsv((self.clock * 420) % 360, 0.7, 1)
        tint = cycle if over else rush_colour(shown)

        # fill: the texture is cropped, not squashed, so colours stay put as it rises
        height = BAR_HEIGHT * max(shown, 0.001)
        self.fill.scale_y = self.energy.scale_y = height
        if over:
            self.fill.set_shader_input('texture_scale', Vec2(1, shown * 0.7))
            self.fill.set_shader_input('texture_offset', Vec2(0, -self.clock * 1.8))
        else:
            self.fill.set_shader_input('texture_scale', Vec2(1, shown))
            self.fill.set_shader_input('texture_offset', Vec2(0, 0))
        self.energy.set_shader_input('texture_scale', Vec2(1, shown * 5))
        self.energy.set_shader_input('texture_offset', Vec2(0, -self.clock * (0.7 + 2.6 * shown)))
        self.energy.color = color.Color(1, 1, 1, 0.75 if over else 0.2 + 0.3 * shown)
        self.cap.y = height
        self.cap.color = color.white if over else color.Color(1, 1, 1, min(1.0, shown * 8))

        live = clamp((speed - T.RUSH_MIN_SPEED) / (T.RUSH_MAX_SPEED - T.RUSH_MIN_SPEED), 0, 1.05)
        self.needle_at += (live - self.needle_at) * (1 - exp(-25 * dt))
        self.needle.y = BAR_HEIGHT * self.needle_at
        self.needle.color = tint

        # a rising blip each time the fill passes a quarter mark
        quarter = min(int(shown * 4 + 0.001), 3)
        if quarter > self.quarter:
            self.quarter = quarter
            self.game.sfx.play('bar_tick', volume=0.45, pitch=0.85 + 0.2 * quarter)
        elif shown < self.quarter * 0.25 - 0.06:
            self.quarter -= 1

        # the number jumps in size whenever speed is gained quickly
        if dt > 0:
            gain = (speed - self.last_speed) / dt
            if gain > 25:
                self.speed_punch = min(1.0, self.speed_punch + gain * dt * 0.08)
        self.last_speed = speed
        self.speed_punch = max(0.0, self.speed_punch - dt * 3)
        if round(speed) != self.shown_speed:
            self.shown_speed = round(speed)
            self.number.text = str(self.shown_speed)
        beat = 0.12 * abs(sin(self.clock * 14)) if over else 0
        self.number.scale = 2.8 * (1 + 0.4 * self.speed_punch + 0.2 * shown + beat)
        self.number.color = tint
        multiplier = round(rush.damage_multiplier * 100)
        if multiplier != self.shown_multiplier:
            self.shown_multiplier = multiplier
            self.multiplier.text = f'x{multiplier / 100:.2f}'
        self.multiplier.scale = 1.5 * (1 + 0.3 * shown + beat)
        self.multiplier.color = tint
        if self.player.drive != self.shown_drive:
            self.shown_drive = self.player.drive
            for i, pip in enumerate(self.drive_pips):
                pip.color = PARRY if i < self.shown_drive else DIM
        charge = self.player.dash_progress
        for i, dash in enumerate(self.dashes):
            amount = clamp(charge - i, 0, 1)
            ready = amount >= 1
            if ready and not dash['ready']:
                dash['pop'] = 1.0       # it jumps as it comes back
            dash['ready'] = ready
            dash['pop'] = max(0.0, dash['pop'] - dt * 5)
            fill = dash['fill']
            fill.enabled = amount > 0.03
            fill.scale = (max(amount, 0.03) * (1 + 0.25 * dash['pop']), 1 + 0.5 * dash['pop'], 1)
            fill.color = color.white if dash['pop'] > 0.5 else DASH_READY if ready else DASH_FILLING

        pulse = 0.25 * abs(sin(self.clock * 22)) if over else 0
        self.glow.color = color.Color(tint[0], tint[1], tint[2], min(1.0, 0.06 + 0.3 * shown + pulse + self.punch))
        self.glow.scale = (BAR_WIDTH * (6 + 8 * self.punch), BAR_HEIGHT * (1.5 + 0.5 * self.punch))
        self.flash.color = color.Color(1, 1, 1, self.punch ** 2)
        self.scale = 1 + 0.16 * self.punch ** 2
        jitter = (0.003 if over else 0) + 0.008 * self.punch
        self.position = (BAR_X + uniform(-jitter, jitter), BAR_Y + uniform(-jitter, jitter))

        if over:
            self.arc(dt)
        self.move_sparks(dt)

    def arc(self, dt):
        """Lightning that re-rolls its shape a couple of dozen times a second."""
        self.flicker -= dt
        if self.flicker <= 0:
            self.flicker = uniform(0.03, 0.06)
            for i, bolt in enumerate(self.bolts):
                bolt.enabled = uniform(0, 1) < 0.8
                bolt.model = choice(self.bolt_shapes)
                bolt.color = choice(SPARK_TINTS)
                side = choice((-1, 1))
                if i < 2:       # crawling up the tube
                    bolt.rotation_z = uniform(-6, 6)
                    bolt.position = (uniform(-0.4, 0.4) * BAR_WIDTH, uniform(0, BAR_HEIGHT * 0.55), -0.05)
                    bolt.scale = (side * 0.055, uniform(0.18, BAR_HEIGHT * 0.45))
                else:           # leaping off the sides
                    bolt.rotation_z = side * uniform(50, 125)
                    bolt.position = (side * BAR_WIDTH / 2, uniform(0.03, BAR_HEIGHT), -0.05)
                    # rotation_z is clockwise, so a positive angle leans toward the screen's right
                    bolt.scale = (0.05, uniform(0.06, 0.16) if side > 0 else uniform(0.05, 0.1))
            self.spark(BAR_HEIGHT * self.shown)
            self.spark(uniform(0, BAR_HEIGHT))
        self.next_zap -= dt
        if self.next_zap <= 0:
            self.next_zap = uniform(0.12, 0.5)
            self.game.sfx.play('zap', volume=uniform(0.2, 0.4), pitch=uniform(0.75, 1.5))

    def spark(self, y, burst=False):
        item = self.sparks[self.spark_cursor]
        self.spark_cursor = (self.spark_cursor + 1) % SPARKS
        side = choice((-1, 1))
        speed = uniform(0.25, 0.8) if burst else uniform(0.1, 0.35)
        item['vx'], item['vy'] = side * speed, uniform(-0.1, 0.45)
        item['life'] = item['span'] = uniform(0.25, 0.5)
        entity = item['entity']
        entity.position = (side * BAR_WIDTH / 2, y, -0.06)
        entity.color = choice(SPARK_TINTS)
        entity.enabled = True

    def move_sparks(self, dt):
        for item in self.sparks:
            if item['life'] <= 0:
                continue
            item['life'] -= dt
            entity = item['entity']
            if item['life'] <= 0:
                entity.enabled = False
                continue
            item['vy'] -= 1.4 * dt
            entity.x += item['vx'] * dt
            entity.y += item['vy'] * dt
            entity.scale = 0.011 * item['life'] / item['span']


class Hud(Entity):
    def __init__(self, game):
        super().__init__(parent=camera.ui)
        self.game = game
        self.player = game.player
        self.shown_kills = -1
        self.kill_pop = 0.0
        self.puffed = 0             # letters of the banner that have landed so far
        self.shown_weapon = -1
        self.marker_time = 0.0
        self.hurt_time = 0.0
        self.heal_time = 0.0
        self.quick_time = 0.0
        self.ring_tint = GOLD
        self.age = 0.0

        # speed streaks sit behind everything else on the HUD
        self.streaks = [Entity(parent=self, model=streak_mesh(seed), double_sided=True, z=1, enabled=False)
                        for seed in (1, 2)]
        self.streak_timer = 0.0
        # hurt: red closing in round the edge, as health coming back is green (see heal_flash)
        self.hurt = Entity(parent=self, model='quad', texture=edge_texture(), scale=(1.8, 1), color=color.hsv(0, 0.9, 1, 0),
                           z=0.5)
        self.healed = Entity(parent=self, model='quad', texture=edge_texture(), scale=(1.8, 1), z=0.49,
                             color=color.Color(HEAL[0], HEAL[1], HEAL[2], 0))
        self.white = Entity(parent=self, model='quad', scale=(2, 1), color=color.Color(1, 1, 1, 0), z=0.48)
        self.blast_time = 0.0
        self.sights = {'cross': scope_texture()}      # the other kinds are drawn when first looked through
        self.sight = 'cross'
        self.scope = Entity(parent=self, model='quad', texture=self.sights['cross'], z=0.45, enabled=False)
        self.quick_ring = Entity(parent=self, model='quad', texture=ring_texture(), color=GOLD, enabled=False)

        # the crosshair: an outlined dot
        self.dot = Entity(parent=self, model=build([(plate(disc(0.5, steps=10), 0.1), (1, 1, 1))], 0.16),
                          scale=0.008, color=color.white)
        # hit marker: four chunky outlined ticks in an X around the crosshair, which spin on a kill
        self.marker_holder = Entity(parent=self)
        self.marker = [Entity(parent=self.marker_holder, model=tick_model(), scale=0.02, rotation_z=45 + 90 * i,
                              position=(sin(pi / 4 + i * pi / 2) * 0.028, cos(pi / 4 + i * pi / 2) * 0.028),
                              enabled=False) for i in range(4)]
        self.marker_spin = 0.0
        # a sniper's aim: an arrow at the edge of the screen pointing to it
        self.threat_arrow = Entity(parent=self, model=arrow_model(), scale=0.045, enabled=False)

        self.overdrive = Label(parent=self, text='', origin=(0, 0), position=(0, 0.13), scale=2, letters=True)
        self.bar = SpeedBar(self)

        self.sparks = Pixels(ui=True)       # pixels flung about the screen
        self.health = HealthBar(self)
        self.boss_bar = BossBar(self)
        # weapon list: every slot you carry, the one in hand lit up, the katana at the bottom
        names = [(str(i + 1), weapon) for i, weapon in enumerate(game.arsenal.weapons)]
        self.slots = [Label(parent=self, text=f'{key}  {weapon.name}', origin=(0.5, 0), scale=0.95,
                           position=(0.86, -0.43 + (len(names) - i) * SLOT_GAP))
                      for i, (key, weapon) in enumerate(names)]
        self.slot_bar = Entity(parent=self, model='quad', scale=(0.006, 0.03), x=0.872)
        self.blade_slot = Label(parent=self, text=f'{T.KEY_KATANA.upper()}  KATANA', origin=(0.5, 0), scale=0.95,
                               position=(0.86, -0.43))
        self.slot_punch = 0.0
        # what is in the gun and what is carried, and under the crosshair how a reload is going
        self.ammo = Label(parent=self, text='', origin=(0.5, 0), position=(0.86, -0.43 + (len(names) + 2.2) * SLOT_GAP),
                          scale=2.2, letters=True)
        self.shown_ammo = None
        self.ammo_pop = 0.0
        # the reload bar: a dark socket like the dash bars', and a fill from its left end
        self.reload_back = Entity(parent=self, position=(0, -0.1), enabled=False, model=build(
            [(plate([(-0.054, -0.007), (0.054, -0.007), (0.054, 0.007), (-0.054, 0.007)], 0.01), color.hsv(250, 0.35, 0.25))],
            0.003))
        self.reload_fill = Entity(parent=self, position=(-0.05, -0.1, -0.01), scale=(0.1, 1), enabled=False,
                                  model=build([(plate([(0, -0.004), (1, -0.004), (1, 0.004), (0, 0.004)], 0.01), (1, 1, 1))], 0))
        self.reload_text = Label(parent=self, text='', origin=(0, 0), position=(0, -0.125), scale=0.8)
        self.kills = Label(parent=self, text='', origin=(0.5, 0), position=(0.86, 0.322), scale=0.9)
        self.tag = Label(parent=self, text='', origin=(0.5, 0), position=(0.86, 0.396), scale=1)
        self.chips = Label(parent=self, text='', origin=(0.5, 0), position=(0.86, 0.359), scale=1.1, color=GOLD)
        self.shown_chips = -1
        self.chip_pop = 0.0
        # the level: where the player is in it, a banner as each round starts and ends,
        # and a line for news: a key picked up, an ally won or lost
        self.round = Label(parent=self, text='', origin=(0, 0), position=(0, 0.35), scale=1.05)
        self.shown_round = ''
        self.title = Label(parent=self, text='', origin=(0, 0), position=(0, 0.275), scale=3.2, letters=True,
                           enabled=False)
        self.subtitle = Label(parent=self, text='', origin=(0, 0), position=(0, 0.215), scale=1.2, enabled=False)
        self.banner_time = 0.0
        self.note = Label(parent=self, text='', origin=(0, 0), position=(0, -0.2), scale=1.5, color=GOLD, letters=True,
                          enabled=False)
        self.note_time = 0.0
        # a sniper has the player in its sights: which way it is, and how long is left
        self.alarm = Label(parent=self, text='', origin=(0, 0), position=(0, 0.16), scale=1.6, enabled=False, letters=True)
        self.danger = None          # (how red, seconds left, the sniper) of the one closest to firing
        self.danger_time = 0.0
        self.help = Label(parent=self, origin=(0, 0), position=(-0.13, -0.385), scale=0.62, text=help_text(),
                          color=color.hsv(230, 0.08, 0.86))
        # frames a second, for checking the game keeps up: F3 shows it
        self.fps = Label(parent=self, text='', origin=(-0.5, 0), position=(-0.86, 0.475), scale=0.75, enabled=False)
        self.fps_time = 0.0
        self.fps_frames = 0
        self.score = ScoreHud(self)     # the chain badge, the score and the points flying to it

    # --- events ---

    def show_controls(self):
        """Rewrite the help lines after keys were rebound."""
        self.help.text = help_text()

    def set_player(self, name, hue):
        """The name tag and the crosshair dot take the colour picked on the menu."""
        tint = player_colour(hue)
        self.tag.text = name
        self.tag.color = tint
        self.dot.color = tint

    def hit_marker(self, killed, size=None, tint=None):
        self.marker_time = 0.14 if killed else 0.07
        tint = tint or (color.hsv(50, 0.9, 1) if killed else color.white)
        size = size or (1.6 if killed else 1.0)
        self.marker_spin = 1.0 if killed else 0.0
        self.marker_holder.rotation_z = 0
        for i, tick in enumerate(self.marker):
            a = pi / 4 + i * pi / 2
            tick.position = (sin(a) * 0.028 * size, cos(a) * 0.028 * size)
            tick.scale = 0.02 * size
            tick.color = tint
            tick.enabled = True

    def quickscope(self):
        """Gold marker and a ring that bursts outward from the crosshair."""
        self.hit_marker(True, size=2.4, tint=GOLD)
        self.marker_time = 0.3
        self.quick_time = 0.35
        self.ring_tint = GOLD

    def parry(self):
        """The same burst as a quickscope, in parry green."""
        self.hit_marker(True, size=2.2, tint=PARRY)
        self.marker_time = 0.25
        self.quick_time = 0.35
        self.ring_tint = PARRY

    def banner(self, title, subtitle=''):
        """Big words across the top of the screen for a couple of seconds: the letters drop in
        one by one, each with a puff, and burst into pixels when it goes."""
        if self.banner_time > 0:
            self.shatter(self.title, 'white', 3)
        self.title.text, self.subtitle.text = title, subtitle
        self.title.enabled = self.subtitle.enabled = True
        self.title.drop_in(0)
        self.banner_time = BANNER_TIME
        self.puffed = 0

    def notice(self, message):
        """A gold line under the crosshair: a key picked up, an ally won or lost. Its letters
        wobble in with a sparkle."""
        self.note.text = message
        self.note.enabled = True
        self.note.drop_in(0, height=4)
        self.note_time = NOTICE_TIME
        for point in self.note.points()[::3]:
            self.sparks.spray(point, 'gold', count=2, speed=0.12, size=0.003, life=0.5, up=0.08)

    def shatter(self, label, look, count=4, speed=0.35):
        """Burst a label's letters into pixels."""
        size = 0.0011 * label.scale_y
        for point in label.points():
            self.sparks.spray(point, look, count=count, speed=speed, size=size, life=0.7, gravity=0.6)

    def threat(self, sniper, heat, left):
        """A sniper is aiming, `left` seconds from its shot; `heat` is 0 while its laser is blue
        and rises to 1 as it turns red. Called every frame it aims; the nearest to firing is shown."""
        if self.danger is None or self.danger_time <= 0 or left <= self.danger[1]:
            self.danger = (heat, left, sniper)
        self.danger_time = 0.15

    def chip(self):
        self.chip_pop = 1.0

    def refresh_weapons(self):
        """The arsenal changed: a slot may hold a branch with another name and colour."""
        for i, weapon in enumerate(self.game.arsenal.weapons):
            self.slots[i].text = f'{i + 1}  {weapon.name}'
        self.shown_weapon = -1

    def blast(self):
        """White flash across the whole screen, for the Longshot going off: the full-screen effects
        do it if they are on, the HUD if not."""
        if self.game.postfx.active:
            self.game.postfx.pulse('flash', 0.5, BLAST_TIME)
        else:
            self.blast_time = BLAST_TIME

    def hurt_flash(self, amount=0.0):
        self.hurt_time = 0.35
        if amount:
            self.health.hurt(amount)

    def out_of_ammo(self):
        """The trigger was pulled on nothing: the ammunition count jumps."""
        self.ammo_pop = 1.0

    def ammo_gain(self, weapon):
        """A crate was picked up for this weapon."""
        self.notice(f'AMMO FOR THE {weapon.name}')
        self.ammo_pop = 1.0

    def heal_flash(self, amount):
        """Health came back: green closes in round the screen and the health bar jumps."""
        self.heal_time = HEAL_TIME
        self.health.healed(amount)

    # --- frame ---

    def input(self, key):
        if key == 'f3':
            self.fps.enabled = not self.fps.enabled

    def update(self):
        dt = time.dt
        self.age += dt
        if self.fps.enabled:
            self.fps_time += time.dt_unscaled
            self.fps_frames += 1
            if self.fps_time >= 0.25:
                self.fps.text = f'{self.fps_frames / self.fps_time:.0f} FPS'
                self.fps_time = self.fps_frames = 0
        self.update_rush()
        self.bar.tick(dt)
        self.update_streaks(dt)
        self.update_scope(dt)
        self.update_status(dt)
        self.update_level(dt)
        self.update_alarm(dt)
        self.score.tick(dt)

    def update_alarm(self, dt):
        self.danger_time -= dt
        if self.danger_time <= 0 or self.danger is None:
            self.danger = None
            self.alarm.enabled = False
            self.threat_arrow.enabled = False
            return
        heat, left, sniper = self.danger
        self.danger = (heat, left + 1e-3, sniper)      # so the same sniper's next call replaces this one
        # which side of the screen it is on, from where the camera is looking
        to = Vec3(sniper.x - self.player.x, 0, sniper.z - self.player.z)
        forward, right = camera.forward, camera.right
        ahead, across = to.x * forward.x + to.z * forward.z, to.x * right.x + to.z * right.z
        if ahead > 0 and abs(across) < ahead * 0.6:
            words = 'SNIPER'
        elif ahead < 0 and abs(across) < -ahead * 0.6:
            words = 'SNIPER BEHIND'
        else:
            words = '<<  SNIPER' if across < 0 else 'SNIPER  >>'
        if heat > 0:
            words += f'   {max(left, 0):.1f}'
        alarm = self.alarm
        alarm.enabled = True
        alarm.text = words
        alarm.origin = (0, 0)
        blink = 0.6 + 0.4 * abs(sin(self.age * (5 + 14 * heat)))
        alarm.color = color.Color(0.45 + 0.55 * heat, 0.85 - 0.7 * heat, 1 - 0.9 * heat, blink if heat > 0 else 0.7)
        alarm.scale = 1.4 + 0.8 * heat
        if heat > 0.5:
            alarm.jiggle(self.age, amount=0.6 + heat)     # close to the shot: the words shake
        else:
            alarm.settle()
        # an arrow on an oval round the middle of the screen, pointing out toward the sniper
        way = atan2(across, ahead)
        arrow = self.threat_arrow
        arrow.enabled = True
        arrow.position = (sin(way) * 0.62, cos(way) * 0.36, -0.05)
        arrow.rotation_z = degrees(way)
        arrow.color = alarm.color
        arrow.scale = 0.04 + 0.025 * heat * blink

    def update_rush(self):
        rush = self.player.rush
        self.overdrive.text = f'OVERDRIVE  {rush.overdrive_time:.1f}s' if rush.overdrive else ''
        self.overdrive.color = color.hsv((time.time() * 400) % 360, 0.7, 1)
        if rush.overdrive:
            # the word ripples, throwing off pixels in every colour
            self.overdrive.wave(self.age, height=1.5, speed=12)
            if uniform(0, 1) < 0.5:
                points = self.overdrive.points()
                if points:
                    self.sparks.spray(choice(points), 'rush', count=1, speed=0.15, size=0.003, life=0.5, up=0.1,
                                      gravity=-0.2)

    def update_streaks(self, dt):
        """Streaks rush past the edges of the screen, thicker and brighter with speed."""
        speed = self.player.speed
        tint = rush_colour(self.player.rush.fraction)
        amount = clamp((speed - T.SPEED_LINES_START) / (T.SPEED_LINES_FULL - T.SPEED_LINES_START), 0, 1)
        self.streak_timer -= dt
        for i, layer in enumerate(self.streaks):
            layer.enabled = amount > 0.02
            if not layer.enabled:
                continue
            if self.streak_timer <= 0:
                layer.rotation_z = uniform(0, 360)
                layer.scale = uniform(0.95, 1.25) - 0.2 * amount
            base = color.white if i == 0 else tint
            layer.color = color.Color(base[0], base[1], base[2], amount * (0.55 if i == 0 else 0.8))
        if self.streak_timer <= 0:
            self.streak_timer = 0.035

    def update_scope(self, dt):
        arsenal = self.game.arsenal
        amount = arsenal.scope
        self.scope.enabled = amount > 0.01
        kind = getattr(arsenal.weapon, 'reticle', self.sight)
        if self.scope.enabled and kind != self.sight:
            if kind not in self.sights:
                self.sights[kind] = scope_texture(kind)
            self.sight = kind
            self.scope.texture = self.sights[kind]
        if self.scope.enabled:
            # the mask closes in from oversized as the scope comes up
            grow = 1 + 0.9 * (1 - amount) ** 2
            self.scope.scale = (2.2 * grow, 1.1 * grow)
            self.scope.color = color.Color(1, 1, 1, amount)

        # gold ring: steady pulse while a quickscope is on offer, a burst when one lands
        self.quick_time = max(0.0, self.quick_time - dt)
        ready = arsenal.weapon.can_scope and arsenal.quick_ready
        self.quick_ring.enabled = ready or self.quick_time > 0
        if self.quick_time > 0:
            t = 1 - self.quick_time / 0.35
            self.quick_ring.scale = 0.13 + 0.4 * t
            tint = self.ring_tint
            self.quick_ring.color = color.Color(tint[0], tint[1], tint[2], 1 - t)
        elif ready:
            self.quick_ring.scale = 0.13 + 0.012 * sin(self.age * 40)
            self.quick_ring.color = GOLD

    def update_level(self, dt):
        game = self.game
        director = game.director
        line = ''
        if director.state == 'clear' and game.beacon.live:
            line = f'SHOOT THE BEACON FOR A MINIBOSS   {max(0, int(director.timer + 0.999))}'
        elif director.state in ('intro', 'fight', 'clear'):
            line = f'LEVEL {director.level}   ROUND {director.round + 1}/{len(director.rounds)}   {director.left} LEFT'
        if line != self.shown_round:
            self.shown_round = line
            self.round.text = line

        if game.progress.chips != self.shown_chips:
            if game.progress.chips > self.shown_chips >= 0:
                self.sparks.spray(self.chips.getPos(camera.ui) + Vec3(-0.03, 0, 0), 'gold', count=4, speed=0.18,
                                  size=0.0035, life=0.5, up=0.1)
            self.shown_chips = game.progress.chips
            self.chips.text = f'CHIPS {self.shown_chips}'
        if self.chip_pop > 0:
            self.chip_pop = max(0.0, self.chip_pop - dt * 6)
            self.chips.scale = 1.1 + 0.5 * self.chip_pop

        if self.banner_time > 0:
            self.banner_time -= dt
            age = BANNER_TIME - self.banner_time
            self.title.drop_in(age)
            # a puff of pixels under each letter as it lands
            landed = sum(1 for i in range(len(self.title.home)) if age >= i * 0.035 + 0.16)
            for i in range(self.puffed, landed):
                if i < len(self.title.glyphs):
                    at = self.title.glyphs[i].getPos(camera.ui) + Vec3(0, -0.035, 0)
                    self.sparks.spray(at, 'white', count=3, speed=0.12, size=0.003, life=0.35, gravity=0.0)
            self.puffed = landed
            self.subtitle.color = color.Color(1, 1, 1, 0.75 * clamp(age / 0.3, 0, 1))
            if self.banner_time <= 0:
                self.shatter(self.title, 'white')
                self.title.enabled = self.subtitle.enabled = False
        if self.note_time > 0:
            self.note_time -= dt
            age = NOTICE_TIME - self.note_time
            if age < 0.6:
                self.note.drop_in(age, height=4)
            else:
                self.note.wave(age, height=0.5, speed=6)
            self.note.color = color.Color(GOLD[0], GOLD[1], GOLD[2], clamp(self.note_time / 0.5, 0, 1))
            if self.note_time <= 0:
                self.note.enabled = False

    def update_status(self, dt):
        self.marker_time -= dt
        if self.marker_time <= 0 and self.marker[0].enabled:
            for tick in self.marker:
                tick.enabled = False
        if self.marker_spin > 0:
            self.marker_spin = max(0.0, self.marker_spin - dt * 6)
            self.marker_holder.rotation_z += 900 * self.marker_spin * dt       # a kill's X spins as it fades

        self.hurt_time = max(0.0, self.hurt_time - dt)
        self.blast_time = max(0.0, self.blast_time - dt)
        self.white.color = color.Color(1, 1, 1, 0.5 * (self.blast_time / BLAST_TIME) ** 2)
        self.hurt.color = color.hsv(0, 0.9, 1, 0.7 * self.hurt_time / 0.35)
        if self.heal_time > 0:
            self.heal_time = max(0.0, self.heal_time - dt)
            t = self.heal_time / HEAL_TIME
            self.healed.color = color.Color(HEAL[0], HEAL[1], HEAL[2], 0.4 * t)
        self.health.tick(dt)
        self.boss_bar.tick(dt)

        arsenal = self.game.arsenal
        if arsenal.current != self.shown_weapon:
            self.shown_weapon = arsenal.current
            self.slot_punch = 1.0
            for i, slot in enumerate(self.slots):
                slot.color = arsenal.weapons[i].colour if i == arsenal.current else color.hsv(230, 0.1, 0.66)
                slot.scale = 0.95
                slot.style = 'block' if i == arsenal.current else 'flat'      # the one in hand stands out
            for point in self.slots[arsenal.current].points()[-6:]:
                self.sparks.spray(point, 'white', count=1, speed=0.2, size=0.003, life=0.35, gravity=0.0)
            self.slot_bar.color = arsenal.weapon.colour
            self.slot_bar.y = self.slots[arsenal.current].y
        self.slot_punch = max(0.0, self.slot_punch - dt * 5)
        self.slots[arsenal.current].scale = 1.3 + 0.35 * self.slot_punch
        weapon = arsenal.weapon
        loading = arsenal.reloading and bool(weapon.stat('reload'))
        dry = weapon.rounds <= 0 and not arsenal.reloading
        ammo = (weapon.rounds, weapon.reserve, loading, dry)
        if ammo != self.shown_ammo:
            self.shown_ammo = ammo
            self.ammo.text = f'{weapon.rounds}' if weapon.reserve is None else f'{weapon.rounds} / {weapon.reserve}'
            low = weapon.rounds <= max(1, weapon.mag // 4)
            self.ammo.color = HURT if dry else GOLD if low and weapon.mag > 2 else color.white
            self.reload_back.enabled = self.reload_fill.enabled = loading
            self.reload_text.text = ('RELOADING' if loading
                                     else f'NO AMMO   {key_name(T.KEYS_WEAPON[0])}: {arsenal.weapons[0].name}' if dry else '')
        if loading:
            self.reload_fill.scale_x = 0.1 * (1 - clamp(arsenal.cooldown / arsenal.wait, 0, 1))
            self.reload_fill.color = weapon.colour
        self.ammo_pop = max(0.0, self.ammo_pop - dt * 4)
        self.ammo.scale = 2.2 * (1 + 0.35 * self.ammo_pop)
        if dry:
            self.ammo.jiggle(self.age, amount=0.8)       # empty: it shakes
        else:
            self.ammo.settle()

        swinging = self.game.katana.busy
        self.blade_slot.color = color.white if swinging else color.hsv(200, 0.15, 0.72)
        self.blade_slot.scale = 1.2 if swinging else 0.95
        if self.game.kills != self.shown_kills:
            if self.game.kills > self.shown_kills >= 0:
                self.kill_pop = 1.0
                self.sparks.spray(self.kills.getPos(camera.ui) + Vec3(-0.02, 0, 0), 'hurt', count=5, speed=0.2,
                                  size=0.0035, life=0.45, up=0.1)
            self.shown_kills = self.game.kills
            self.kills.text = f'KILLS {self.shown_kills}'
        self.kill_pop = max(0.0, self.kill_pop - dt * 5)
        self.kills.scale = 0.9 * (1 + 0.35 * self.kill_pop)

        if self.help.enabled and self.age > 15:
            self.help.enabled = False
