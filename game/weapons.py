from math import cos, exp, pi, sin
from random import choice, uniform

from ursina import Entity, Vec3, camera, clamp, color, destroy, held_keys, mouse, raycast, time

from data import tuning as T
from data.controls import key_name, pressed
from fx.toon import barrel, box, build, burst_mesh, slab, slug_mesh, star, streak_mesh
from game import mods
from game.body import hands, stripe

VIEW_POSITION = Vec3(0.34, -0.3, 0.75)
SCOPE_POSITION = Vec3(0, -0.2, 0.6)
TRACER_TIME = 0.06
TRACER_WIDTH = 0.035
STREAK = 45.0           # a bullet's streak is this many times as long as it is wide
SLUG_START = 1.2        # a drawn bullet first shows this far out of the muzzle, clear of the gun
TRACER_POOL = 28
IMPACT_POOL = 14
IMPACT_TIME = 0.11
SLUG_SPEED = 200.0      # how fast the drawn bullet crosses the gap; the hit itself is instant
ROCKET_POOL = 8          # a sticky grenade waiting to be set off keeps its slot
BOOMER_SIZE = 1.2       # the launcher and the rifle are big guns
LONGSHOT_SIZE = 1.2
FIRE_BUFFER = 0.12      # a click this early still fires a single-shot weapon

# paint shared by every weapon: soft and saturated, never glowing
DARK = color.hsv(230, 0.25, 0.3)
METAL = color.hsv(215, 0.14, 0.7)
CREAM = color.hsv(45, 0.18, 0.97)
WOOD = color.hsv(28, 0.5, 0.78)
GLASS = color.hsv(195, 0.45, 1)


def spread(direction, degrees_off):
    """Tilt a direction by up to `degrees_off` at random."""
    amount = degrees_off / 57.3
    right, up = camera.right, camera.up
    return (direction + right * uniform(-amount, amount) + up * uniform(-amount, amount)).normalized()


def both(make):
    """Details for the two sides of a gun: `make(side)` gives one side's, with side -1 or 1."""
    return [part for side in (-1, 1) for part in make(side)]


def bolts(x, spots, tint=None, size=0.012):
    """Bolt heads standing proud of a side at `x`; spots are (y, z)."""
    return both(lambda side: [(box((0.006, size, size), (side * x, y, z)), tint or METAL) for y, z in spots])


def groove(x, y, z0, z1, tint=None):
    """A seam along a side at `x`."""
    return both(lambda side: [(box((0.004, 0.005, z1 - z0), (side * x, y, (z0 + z1) / 2)), tint or DARK)])


def cuts(x, y0, y1, spots, tint=None):
    """Upright cuts in a side at `x`, one at each z in `spots`."""
    return both(lambda side: [(box((0.004, y1 - y0, 0.006), (side * x, (y0 + y1) / 2, z)), tint or DARK) for z in spots])


def marks(x, shapes, tint):
    """Flat shapes painted on both sides at `x`: each is a list of (z, y) corners."""
    return both(lambda side: [(slab(shape, 0.004, x=side * x), tint) for shape in shapes])


def grip(z, y, width=0.05, length=0.085, drop=0.16, rake=0.035):
    """A handle hanging from (z, y), raked backwards."""
    return slab([(z - length, y), (z, y), (z - rake, y - drop), (z - length - rake, y - drop)], width)


class Weapon:
    """A weapon's numbers come from game/mods.py, which adds the player's upgrades to them, so
    they are read with `self.stat(...)` and not from the tuning file."""
    name = ''
    slot = ''               # whose numbers and tree it uses: a branch keeps its base weapon's slot
    hue = 0
    accent_hue = 0
    kick = 1.0
    shake = 0.1
    sound = ''
    muzzle = (0.03, 0.4)    # height and forward reach of the barrel tip
    flash = 1.0             # muzzle flash size and how long it lingers
    slug = (0.16, 0.6)      # width and length of the bullet drawn for each shot: cartoon-sized
    automatic = True        # False: one shot per click
    can_scope = False
    alt = False             # True: the scope key fires something else (see alt_now and alt_fire)
    hold = (0, -0.13, -0.08)    # where the right hand grips it, in the space of its view
    fore = None                 # where the left hand steadies it, if it does

    def __init__(self, arsenal):
        self.arsenal = arsenal
        self.game = arsenal.game
        self.colour = color.hsv(self.hue, 0.7, 1)           # tracers, flash and HUD
        self.paint_hue = self.hue
        self.paint = color.hsv(self.hue, 0.58, 0.9)
        self.accent = color.hsv(self.accent_hue, 0.55, 0.92)
        self.view = Entity(parent=arsenal.view, enabled=False)
        self.cycled = True      # the pump or bolt has been worked since the last shot
        self.build_view()
        self.build_hands()
        self.restock()

    def repaint(self, hue=None):
        """Rebuild the view model with its body in `hue`, or in the weapon's own colour."""
        self.paint_hue = self.hue if hue is None else hue
        self.paint = color.hsv(self.paint_hue, 0.58, 0.9)
        for piece in self.view.children:
            destroy(piece)
        self.build_view()
        self.build_hands()

    def build_hands(self):
        """The player's gloves and sleeves, holding it. The cuffs are the colour the player picked."""
        cuff = stripe(None if self.paint_hue == self.hue else self.paint_hue)
        self.solid(*hands(self.hold, self.fore, cuff))

    def trim(self, *parts):
        """Small flat details: bolts, seams, markings. They have no outline of their own, which
        at this size would swallow them."""
        return Entity(parent=self.view, model=build(parts, 0))

    def solid(self, *parts, **kwargs):
        """One outlined piece of the gun made of (shape, colour) pairs."""
        return Entity(parent=self.view, model=build(parts), **kwargs)

    def stat(self, key):
        return mods.stat(self.slot, key)

    def perk(self, name):
        return mods.perk(self.slot, name)

    @property
    def mag(self):
        """Rounds the gun holds."""
        return round(self.stat('mag'))

    @property
    def reload_time(self):
        return self.stat('reload') or self.interval

    @property
    def can_reload(self):
        return self.rounds < self.mag and (self.reserve is None or self.reserve > 0)

    def restock(self):
        """A full gun and everything it can carry: `reserve` is None for a weapon that never runs out."""
        self.rounds = self.mag
        self.reserve = self.stat('reserve')

    def load(self):
        """The reload is done: fill the gun from what is carried."""
        taken = self.mag - self.rounds
        if self.reserve is not None:
            taken = min(taken, self.reserve)
            self.reserve -= taken
        self.rounds += taken

    def spend(self):
        """A shot is about to leave: returns how long until the next may."""
        self.rounds -= 1
        return self.interval

    def reloading(self):
        """A reload has begun."""

    @property
    def interval(self):
        return mods.stat(self.slot, 'interval')

    def build_view(self):
        pass

    def fire(self, origin, direction, muzzle):
        pass

    def alt_now(self):
        """The scope key was pressed, for a weapon with `alt`: True if that did all it does at
        once, False if it means a shot, which waits for the gun to be ready."""
        return False

    def alt_fire(self, origin, direction, muzzle):
        """The shot the scope key fires, for a weapon with `alt`."""

    def animate(self, recoil, ready, dt):
        """recoil is 1 at the shot and fades to 0; ready runs 0 to 1 across the cooldown."""

    def cycle(self, ready, start, end, sound):
        """0-1-0 stroke of a pump or bolt between two points of the cooldown."""
        if not self.cycled and ready >= start:
            self.cycled = True
            self.game.sfx.play(sound, volume=0.7)
        return sin(pi * clamp((ready - start) / (end - start), 0, 1))


class Popper(Weapon):
    name = slot = 'POPPER'
    hue = 178
    accent_hue = 42
    kick = 0.7
    shake = T.SHAKE_SHOT
    sound = 'shot_popper'
    muzzle = (0.03, 0.27)
    hold = (0, -0.115, -0.085)
    fore = (-0.05, -0.14, -0.065)   # cupped under the other hand

    def build_view(self):
        self.solid(
            (box((0.054, 0.036, 0.3), (0, -0.014, 0.05)), CREAM),               # frame
            (grip(-0.035, -0.03, width=0.052, drop=0.17), DARK),
            (box((0.02, 0.012, 0.085), (0, -0.082, 0.02)), self.accent),         # trigger guard
            (box((0.02, 0.05, 0.012), (0, -0.057, 0.063)), self.accent),
            (box((0.012, 0.03, 0.012), (0, -0.05, 0.012)), DARK),                # trigger
            (barrel(0.016, 0.2, 0.255, y=0.03, sides=8), METAL),
        )
        self.slide = self.solid(
            (box((0.064, 0.06, 0.34), (0, 0.032, 0.045)), self.paint),
            (box((0.07, 0.016, 0.1), (0, 0.03, -0.055)), self.accent),          # grip band
            (box((0.012, 0.016, 0.022), (0, 0.07, 0.19)), CREAM),                # front sight
            (box((0.036, 0.016, 0.02), (0, 0.07, -0.105)), DARK),                # rear sight
        )

        # cocking cuts and a seam on the slide, which move with it; pins in the frame
        self.slide_trim = self.trim(
            *cuts(0.034, 0.012, 0.056, (-0.105, -0.09, -0.075, -0.06, -0.045)),
            *groove(0.034, 0.02, -0.02, 0.2),
            *bolts(0.034, [(0.045, 0.19)]),
            (box((0.03, 0.004, 0.06), (0.008, 0.063, 0.06)), DARK),             # ejection port
        )
        self.trim(*bolts(0.029, [(-0.02, 0.0), (-0.02, 0.13), (-0.005, -0.06)], DARK))

    def animate(self, recoil, ready, dt):
        self.slide.z = self.slide_trim.z = -0.075 * recoil

    def fire(self, origin, direction, muzzle):
        self.arsenal.hitscan(origin, direction, muzzle, self.stat('damage'), self.stat('range'), self.colour,
                             slug=self.slug)
        self.arsenal.apply_hits()


class Scatter(Weapon):
    name = slot = 'SCATTER'
    hue = 8
    accent_hue = 48
    kick = 1.8
    shake = T.SHAKE_SCATTER
    sound = 'shot_scatter'
    muzzle = (0.0, 0.47)
    slug = (0.12, 0.28)     # stubby pellets
    barrels = 0.034         # each one's distance from the middle of the gun
    hold = (0, -0.14, -0.185)
    fore = (0, -0.11, 0.17)         # on the pump

    def reloading(self):
        self.cycled = False     # the pump is worked during the reload

    def build_view(self):
        self.solid(
            (barrel(0.033, -0.05, 0.45, x=-0.034), METAL),
            (barrel(0.033, -0.05, 0.45, x=0.034), METAL),
            (box((0.15, 0.03, 0.034), (0, 0, 0.39)), self.paint),                # barrel band
            (box((0.15, 0.105, 0.2), (0, -0.012, -0.1)), self.paint),            # receiver
            (slab([(-0.2, 0.035), (-0.2, -0.06), (-0.42, -0.13), (-0.42, -0.02)], 0.07), WOOD),
            (grip(-0.12, -0.06, width=0.055, length=0.07, drop=0.13), DARK),
            (box((0.02, 0.012, 0.07), (0, -0.075, -0.07)), DARK),                # trigger guard
            *[(box((0.02, 0.05, 0.026), (-0.078, -0.01, z)), self.accent) for z in (-0.15, -0.11, -0.07)],
        )
        self.pump = self.solid(
            (box((0.125, 0.058, 0.17), (0, -0.058, 0.17)), WOOD),
            *[(box((0.132, 0.03, 0.012), (0, -0.058, z)), DARK) for z in (0.125, 0.17, 0.215)],
        )
        self.trim(
            *bolts(0.077, [(0.022, -0.03), (0.022, -0.17), (-0.045, -0.1)]),
            *groove(0.077, -0.012, -0.19, -0.01),
            (box((0.014, 0.008, 0.42), (0, 0.037, 0.2)), DARK),                 # the rib between the barrels
            (box((0.012, 0.014, 0.012), (0, 0.047, 0.42)), CREAM),              # bead
            *[(box((0.146, 0.004, 0.012), (0, 0.034, z)), DARK) for z in (0.05, 0.2)],      # barrel straps
            *bolts(0.037, [(-0.03, -0.3), (-0.07, -0.38)], CREAM),              # screws in the stock
        )

    def animate(self, recoil, ready, dt):
        # two barrels, the second almost at once; the pump is only worked when both are reloaded
        self.pump.z = -0.1 * self.cycle(ready, 0.25, 0.7, 'pump') if self.arsenal.reloading else 0.0

    def fire(self, origin, direction, muzzle):
        side = self.barrels if self.rounds % 2 else -self.barrels      # the barrels take turns
        muzzle = muzzle + camera.right * side
        self.arsenal.muzzle_flash.x = side
        for _ in range(round(self.stat('pellets'))):
            self.arsenal.hitscan(origin, spread(direction, self.stat('spread')), muzzle, self.stat('damage'),
                                 self.stat('range'), self.colour, slug=self.slug)
        self.landed(self.arsenal.pending)
        self.arsenal.apply_hits()
        self.game.player.add_impulse(-direction * self.stat('recoil'), cap=T.SCATTER_MAX_SPEED)

    def landed(self, pending):
        """For the branches: the pellets' hits, before their damage is dealt."""


def rocket_model(hue=282, fat=1.0):
    """The rocket in flight, nose along z. Big enough to follow with the eye. `fat` thickens its body."""
    body, fin = color.hsv(hue, 0.5, 0.92), color.hsv(45, 0.6, 0.95)
    r = 0.11 * fat
    return build([
        (barrel(r, -0.35, 0.25), body),
        (barrel(r, 0.25, 0.55, end_radius=0.02 * fat), CREAM),               # nose
        (barrel(r + 0.008, 0.08, 0.15), DARK),                               # bands
        (barrel(r + 0.008, -0.2, -0.13), DARK),
        (barrel(0.075 * fat, -0.45, -0.35, end_radius=0.095 * fat), DARK),   # nozzle
        (slab([(-0.38, 0.09), (-0.12, 0.09), (-0.3, 0.27), (-0.42, 0.27)], 0.028), fin),
        (slab([(-0.38, -0.09), (-0.12, -0.09), (-0.3, -0.27), (-0.42, -0.27)], 0.028), fin),
        (box((0.18, 0.028, 0.2), (0.18, 0, -0.3)), fin),
        (box((0.18, 0.028, 0.2), (-0.18, 0, -0.3)), fin),
    ], outline=0.022)


class Boomer(Weapon):
    """Rocket launcher. The rocket flies dead straight; the launch throws you backwards."""
    name = slot = 'BOOMER'
    hue = 282
    accent_hue = 45
    kick = 2.8
    shake = T.SHAKE_ROCKET
    sound = 'shot_rocket'
    muzzle = (0.0, 0.56 * BOOMER_SIZE)
    flash = 2.4
    hold = (0, -0.14, -0.025)
    fore = (0, -0.165, 0.24)
    trail = True            # what it fires leaves flame and smoke behind it
    drop = 0.0              # how fast what it fires falls: a rocket flies straight
    throw = T.ROCKET_PLAYER_KNOCK       # how hard its blast throws you
    look = 'rocket'                     # its explosion: see fx/pixels.py

    def shell_model(self):
        """What it fires, as it is seen in flight."""
        return rocket_model(self.hue)

    def build_view(self):
        self.solid(
            (barrel(0.06, -0.3, 0.42), self.paint),                              # tube
            (barrel(0.06, 0.42, 0.5, end_radius=0.086), CREAM),                  # muzzle flare
            (barrel(0.068, 0.495, 0.506), DARK),                                 # bore
            (barrel(0.088, -0.42, -0.3, end_radius=0.06), DARK),                 # exhaust bell
            (barrel(0.067, 0.12, 0.16), DARK),                                   # bands
            (barrel(0.067, -0.06, -0.02), DARK),
            (barrel(0.07, -0.26, -0.12), WOOD),                                  # heat shield
            (grip(0.02, -0.055, width=0.05), DARK),
            (box((0.044, 0.1, 0.045), (0, -0.105, 0.24)), DARK),                 # front grip
            (box((0.012, 0.03, 0.012), (0, -0.07, 0.035)), CREAM),               # trigger
            (box((0.012, 0.075, 0.012), (0, 0.095, 0.26)), CREAM),               # front sight
            (box((0.04, 0.05, 0.016), (0, 0.085, -0.02)), DARK),                 # rear sight
            (box((0.05, 0.09, 0.03), (0, -0.095, -0.24)), DARK),                 # shoulder rest
        )
        # the loaded rocket pokes out of the muzzle until it is fired
        self.warhead = self.solid(
            (barrel(0.05, 0.46, 0.52), self.accent),
            (barrel(0.05, 0.52, 0.66, end_radius=0.01), CREAM),
        )
        self.view.scale = BOOMER_SIZE
        self.build_trim()

    def build_trim(self):
        """Rivets down the tube, an arrow to say which end is which, and stripes on the heat shield."""
        self.trim(
            *[(box((0.012, 0.006, 0.012), (0, 0.061, z)), METAL) for z in (-0.09, 0.03, 0.2, 0.3, 0.38)],
            *bolts(0.061, [(0, z) for z in (-0.09, 0.03, 0.2, 0.3, 0.38)]),
            (slab([(0.33, 0.062), (0.39, 0.062), (0.39, 0.066), (0.33, 0.066)], 0.012), CREAM),     # arrow shaft
            (box((0.04, 0.004, 0.012), (0, 0.064, 0.385)), CREAM),
            *[(box((0.05, 0.004, 0.014), (0, 0.072, z)), CREAM) for z in (-0.24, -0.2, -0.16)],
            *bolts(0.027, [(-0.12, 0.24), (-0.1, 0.0)], CREAM),
        )

    def animate(self, recoil, ready, dt):
        # empty tube after the shot; a fresh rocket slides in for the last part of the cooldown
        loaded = clamp((ready - 0.55) / 0.35, 0, 1) if self.rounds or self.arsenal.reloading else 0
        self.warhead.enabled = loaded > 0
        self.warhead.z = -0.2 * (1 - loaded)

    def fire(self, origin, direction, muzzle):
        game, arsenal = self.game, self.arsenal
        arsenal.launch_rocket(muzzle, direction, self)
        game.player.add_impulse(-direction * self.stat('recoil'), cap=T.ROCKET_MAX_SPEED)
        arsenal.climb += T.ROCKET_CLIMB
        game.player.fov_kick = 11
        game.blasts.show(muzzle + direction * 0.5, 0.42, self.colour, life=0.2, core=False)
        # back-blast out of the exhaust bell
        behind = muzzle - direction * 1.4 * BOOMER_SIZE
        game.particles.burst(behind, (1, 1, 1), count=18, speed=6, size=0.035, life=0.6, up=1, white=1)
        for _ in range(12):
            game.particles.emit(behind, spread(-direction, 14) * uniform(8, 22), (1, 0.75, 0.25, 1),
                                uniform(0.03, 0.05), uniform(0.12, 0.28), gravity=2)

    def burst(self, position):
        """The rocket this weapon fired has just gone off here."""
        self.game.explode(position, self.stat('radius'), self.stat('damage'), self.colour,
                          player_knock=self.throw, self_damage=self.stat('self_damage'), look=self.look)


class Buzzer(Weapon):
    name = slot = 'BUZZER'
    hue = 38
    accent_hue = 225
    kick = 0.45
    shake = T.SHAKE_BUZZER
    sound = 'shot_buzzer'
    muzzle = (0.0, 0.44)
    slug = (0.12, 0.45)
    hold = (0, -0.13, -0.08)
    fore = (0, -0.075, 0.27)

    def build_view(self):
        self.solid(
            (box((0.075, 0.095, 0.36), (0, 0, 0.04)), self.paint),               # receiver
            (barrel(0.03, 0.22, 0.37), METAL),                                   # shroud
            (barrel(0.02, 0.37, 0.43, sides=8), DARK),
            (slab([(0.03, -0.045), (0.1, -0.045), (0.125, -0.28), (0.055, -0.28)], 0.046), self.accent),
            (box((0.052, 0.02, 0.08), (0, -0.285, 0.09)), DARK),                 # magazine base
            (grip(-0.035, -0.045), DARK),
            (box((0.03, 0.03, 0.15), (0, 0.02, -0.21)), METAL),                  # stock
            (box((0.05, 0.11, 0.026), (0, 0, -0.29)), DARK),
            (box((0.032, 0.016, 0.28), (0, 0.055, 0.04)), DARK),                 # top rail
            (box((0.012, 0.02, 0.016), (0, 0.072, 0.17)), CREAM),
            *[(box((0.082, 0.014, 0.026), (0, 0.012, z)), DARK) for z in (0.11, 0.15, 0.19)],    # vents
        )
        self.bolt = self.solid((box((0.03, 0.022, 0.04), (-0.048, 0.02, 0.02)), CREAM))
        self.trim(
            *bolts(0.0395, [(0.03, -0.1), (0.03, 0.19), (-0.03, -0.03), (-0.03, 0.12)]),
            *groove(0.0395, -0.005, -0.12, 0.2),
            (box((0.006, 0.02, 0.012), (-0.0395, -0.03, -0.09)), self.accent),      # selector
            *[(box((0.034, 0.004, 0.008), (0, 0.064, z)), METAL) for z in (-0.08, -0.05, -0.02, 0.01, 0.07, 0.1, 0.13)],
            *cuts(0.027, -0.03, 0.03, (-0.27, -0.3)),                           # stock plate
        )

    def animate(self, recoil, ready, dt):
        self.bolt.z = -0.06 * recoil

    def fire(self, origin, direction, muzzle):
        self.arsenal.hitscan(origin, spread(direction, self.stat('spread')), muzzle, self.stat('damage'),
                             self.stat('range'), self.colour, slug=self.slug)
        self.landed(self.arsenal.pending)
        self.hits = self.arsenal.apply_hits()

    def landed(self, pending):
        """For the branches: the bullet's hits, before their damage is dealt."""


class Longshot(Weapon):
    name = slot = 'LONGSHOT'
    heft = 1.0              # how hard a shot throws the view about; the branches differ
    hue = 140
    accent_hue = 25
    kick = 2.4
    shake = T.SHAKE_LONGSHOT
    sound = 'shot_longshot'
    muzzle = (0.0, 0.78 * LONGSHOT_SIZE)
    flash = 2.2
    slug = (0.3, 1.9)       # a spike, not a bullet
    automatic = False
    can_scope = True
    hold = (0, -0.13, -0.1)
    fore = (0, -0.08, 0.32)
    reticle = 'cross'       # which sight picture the HUD draws: see scope_texture in ui/hud.py
    scope_fov = T.LONGSHOT_SCOPE_FOV

    def build_scope(self):
        """The sight on top of the rifle. Each branch has its own."""
        self.solid(
            (box((0.026, 0.04, 0.03), (0, 0.06, 0.0)), self.accent),             # scope mounts
            (box((0.026, 0.04, 0.03), (0, 0.06, 0.14)), self.accent),
            (barrel(0.032, -0.08, 0.2, y=0.108), DARK),                          # scope tube
            (barrel(0.046, 0.2, 0.28, y=0.108), DARK),
            (barrel(0.04, -0.14, -0.08, y=0.108), DARK),
            (barrel(0.031, -0.147, -0.14, y=0.108), GLASS),
            (box((0.03, 0.03, 0.03), (0, 0.15, 0.06)), self.accent),             # turret
        )

    def build_view(self):
        deep = color.hsv(self.paint_hue, 0.5, 0.62)
        self.solid(
            (barrel(0.02, 0.2, 0.7, sides=8), METAL),
            (box((0.06, 0.046, 0.075), (0, 0, 0.73)), DARK),                     # muzzle brake
            (box((0.07, 0.088, 0.36), (0, 0, 0.04)), self.paint),                # receiver
            (slab([(0.2, -0.046), (0.2, 0.02), (0.44, 0.008), (0.44, -0.032)], 0.06), deep),
            (slab([(-0.14, 0.04), (-0.14, -0.046), (-0.42, -0.125), (-0.42, 0.02)], 0.06), self.paint),
            (box((0.066, 0.022, 0.14), (0, 0.04, -0.27)), self.accent),          # cheek pad
            (box((0.066, 0.15, 0.022), (0, -0.05, -0.425)), DARK),               # butt pad
            (grip(-0.05, -0.044, drop=0.15), DARK),
            (box((0.05, 0.075, 0.08), (0, -0.08, 0.08)), DARK),                  # magazine
        )
        self.build_scope()
        self.bolt = self.solid(
            (box((0.07, 0.018, 0.018), (-0.06, 0.02, -0.03)), CREAM),
            (box((0.03, 0.03, 0.03), (-0.1, 0.02, -0.03)), CREAM),
        )
        self.view.scale = LONGSHOT_SIZE
        self.build_trim()

    def build_trim(self):
        """Bolts and a seam on the receiver, rings on the barrel, chequering on the stock."""
        self.trim(
            *bolts(0.037, [(0.026, -0.1), (0.026, 0.18), (-0.026, 0.0), (-0.026, 0.14)]),
            *groove(0.037, 0.0, -0.12, 0.2),
            *[(barrel(0.024, z, z + 0.012, sides=8), DARK) for z in (0.5, 0.56, 0.62)],
            *cuts(0.032, -0.08, 0.0, (-0.3, -0.33, -0.36)),
            *bolts(0.032, [(-0.04, -0.22)], CREAM),
        )

    def animate(self, recoil, ready, dt):
        stroke = self.cycle(ready, 0.18, 0.7, 'bolt')
        self.bolt.z = -0.09 * stroke
        self.bolt.y = 0.03 * min(1.0, stroke * 3)

    def fire(self, origin, direction, muzzle):
        arsenal = self.arsenal
        self.cycled = False
        quick = self.quick = arsenal.quick_ready
        damage = self.shot_damage() * (self.stat('quick_bonus') if quick else 1)
        direction = spread(direction, T.LONGSHOT_HIP_SPREAD * (1 - arsenal.scope))
        game = self.game
        heft = self.heft
        end = arsenal.hitscan(origin, direction, muzzle, damage, self.stat('range'), self.colour, pierce=True,
                              width=0.1, slug=self.slug)
        game.blasts.show(muzzle + direction * 0.4, 0.3, self.colour, life=0.16, core=False)    # ring off the muzzle
        self.struck = list(arsenal.pending)
        hits = arsenal.apply_hits(push=T.LONGSHOT_PUSH)

        # the gun bucks: view jumps, the player is shoved, smoke and sparks leave the barrel
        arsenal.climb += T.LONGSHOT_CLIMB * heft
        game.player.fov_kick = T.LONGSHOT_FOV_KICK * heft
        game.player.add_impulse(-direction * T.LONGSHOT_RECOIL * heft)
        if heft >= 1:
            game.hud.blast()
        game.particles.burst(muzzle + direction * 0.3, (1, 1, 1), count=12, speed=5, size=0.035, life=0.5, up=1.5,
                             white=1)
        for _ in range(14):
            game.particles.emit(muzzle, spread(direction, 9) * uniform(18, 46), (self.colour[0], self.colour[1], self.colour[2], 1),
                                uniform(0.04, 0.08), uniform(0.12, 0.3), gravity=4)
        # where it lands: a crater's worth of debris on a wall, a white burst through a body
        game.particles.burst(end, self.colour, count=34, speed=15, size=0.08, life=0.6, white=0.5)
        for point, _ in hits:
            game.particles.burst(point, (1, 1, 1), count=22, speed=17, size=0.09, life=0.45, white=1)
        if hits:
            game.sfx.play('longshot_hit', pitch=uniform(0.92, 1.05))
            game.juice.hitstop(T.LONGSHOT_HITSTOP * heft)
        arsenal.scope_lock = self.stat('rechamber')     # the shot throws you out of the scope
        fast = self.stat('quick_interval')
        if quick and fast is not None:
            # a quickscope that is ready again at once: no time to work the bolt
            arsenal.cooldown = fast
            arsenal.scope_lock = fast / 2
            self.cycled = True
        if quick and hits:
            killed = any(kill for _, kill in hits)
            if killed:
                arsenal.cooldown *= self.stat('quick_refund')
                arsenal.scope_lock *= self.stat('quick_refund')
            self.game.on_quickscope(hits[0][0], killed)
        self.landed(hits)

    def shot_damage(self):
        return self.stat('damage')

    def landed(self, hits):
        """For the branches: the shot is over, and these are its [(hit point, killed), ...]."""


SLOTS = (Popper, Scatter, Boomer, Buzzer, Longshot)


class Arsenal(Entity):
    """Holds the weapons, fires them, and owns the bullets and rockets in the air."""

    def __init__(self, game):
        super().__init__()
        self.game = game
        self.view = Entity(parent=camera, position=VIEW_POSITION)
        self.weapons = [weapon(self) for weapon in SLOTS]
        self.current = 0
        self.cooldown = 0.0
        self.wait = 1.0         # how long the cooldown was when it began, for the weapon's animation
        self.reloading = False  # the cooldown now running is a reload
        self.endless = False    # ammunition is never short: for the tests
        self.click = 0.0        # until an empty gun may click again
        self.later = []         # [seconds, call]: things a shot has set going
        self.kick = 0.0
        self.draw = 0.0         # 1 just after a switch: the weapon swings up into view
        self.sway = Vec3(0, 0, 0)
        self.stride = 0.0
        self.fire_buffer = 0.0
        self.alt_buffer = 0.0   # the scope key, for a weapon whose alt is a shot
        self.told_sticky = False
        self.stow = 0.0
        self.climb = 0.0        # recoil that lifts the aim and settles back
        self.climb_applied = 0.0
        self.scope = 0.0        # 0 at the hip, 1 fully scoped
        self.scope_age = 0.0    # how long the scope key has been held
        self.scope_lock = 0.0
        self.pending = {}       # enemy -> [damage, direction, hit point], merged per shot
        self.paint_hue = None   # the player's colour; None leaves each weapon its own
        # a mesh belongs to one entity, so everything pooled below builds its own
        self.muzzle_flash = Entity(parent=self.view, model=star(), enabled=False, double_sided=True)
        Entity(parent=self.muzzle_flash, model=star(), scale=0.5, z=-0.002, color=color.white, double_sided=True)
        self.flash_time = 0.0
        # every shot is drawn as an outlined trail with an outlined bullet at its head
        self.tracers = [{'trail': Entity(model=streak_mesh(), enabled=False),
                         'slug': Entity(model=slug_mesh(), enabled=False), 'live': False}
                        for _ in range(TRACER_POOL)]
        self.tracer_cursor = 0
        self.impacts = [{'star': Entity(model=burst_mesh(), billboard=True, double_sided=True, enabled=False),
                         'age': 0.0, 'size': 1.0} for _ in range(IMPACT_POOL)]
        self.impact_cursor = 0
        self.rockets = []
        for _ in range(ROCKET_POOL):
            body = Entity(enabled=False)
            # one model for each kind of weapon that has fired this slot, built the first time
            self.rockets.append({'entity': body, 'spin': None, 'looks': {}, 'live': False, 'stuck': False,
                                 'remote': False})
        self.select(0, quiet=True)

    @property
    def weapon(self):
        return self.weapons[self.current]

    @property
    def quick_ready(self):
        """True during the short window just after the scope comes up."""
        opens = T.LONGSHOT_SCOPE_TIME * T.LONGSHOT_QUICK_START
        return opens <= self.scope_age <= T.LONGSHOT_SCOPE_TIME + mods.stat('LONGSHOT', 'quick_window')

    def equip(self):
        """Put the branch bought for each slot in the player's hands, or its plain weapon if
        none was. Returns True if anything changed."""
        from game.variants import VARIANTS      # the branches are built on the classes above
        held = mods.progress.branches if mods.progress is not None else {}
        changed = False
        for i, base in enumerate(SLOTS):
            wanted = VARIANTS.get((base.slot, held.get(base.slot)), base)
            if type(self.weapons[i]) is wanted:
                continue
            destroy(self.weapons[i].view)
            self.weapons[i] = wanted(self)
            if self.paint_hue is not None:
                self.weapons[i].repaint(self.paint_hue)
            changed = True
        if changed:
            # a rocket in the air asks its weapon for numbers when it bursts, and a swapped-out
            # branch's numbers are gone: it goes quietly
            for rocket in self.rockets:
                if rocket['live'] and rocket.get('weapon') not in self.weapons:
                    rocket['live'] = rocket['stuck'] = False
                    rocket['entity'].enabled = False
            self.weapon.view.enabled = True
            height, reach = self.weapon.muzzle
            self.muzzle_flash.position = (0, height, reach + 0.03)
            self.reloading = False
        return changed

    # --- ammunition ---

    def restock(self):
        """Fill every weapon up: a level is starting. Whatever is still in the air goes."""
        for weapon in self.weapons:
            weapon.restock()
        self.reloading = False
        for rocket in self.rockets:
            rocket['live'] = False
            rocket['entity'].enabled = False

    def give_ammo(self):
        """A crate was picked up: it tops up one weapon that is short, picked at random. Returns
        the weapon, or None if nothing needed any."""
        short = [w for w in self.weapons if w.reserve is not None and w.reserve < w.stat('reserve')]
        if not short:
            return None
        weapon = choice(short)
        most = weapon.stat('reserve')
        weapon.reserve = min(most, weapon.reserve + max(1, round(most * T.AMMO_CRATE_SHARE)))
        if weapon is self.weapon and weapon.rounds <= 0 and not self.reloading:
            self.reload()
        return weapon

    def reload(self):
        """Start filling the gun in hand. Returns False if there is nothing to do it with."""
        weapon = self.weapon
        if self.reloading or not weapon.can_reload:
            return False
        self.reloading = True
        self.cooldown = self.wait = max(self.cooldown, weapon.reload_time)
        self.scope_lock = max(self.scope_lock, self.cooldown if weapon.stat('reload') else 0.0)
        weapon.reloading()
        if weapon.stat('reload'):
            self.game.sfx.play('reload')
        return True

    def select(self, index, quiet=False):
        index %= len(self.weapons)
        if index == self.current and self.weapon.view.enabled:
            return
        self.weapon.view.enabled = False
        self.current = index
        self.weapon.view.enabled = True
        self.draw = 1.0
        self.kick = 0.0
        self.fire_buffer = 0.0
        self.scope_age = 0.0
        self.reloading = False      # a reload that was under way is lost
        self.cooldown = self.wait = max(self.cooldown, 0.12)
        if self.weapon.rounds <= 0:
            self.reload()
        height, reach = self.weapon.muzzle
        self.muzzle_flash.position = (0, height, reach + 0.03)
        if not quiet:
            self.game.sfx.play('switch')

    def repaint(self, hue):
        if hue == self.paint_hue:
            return
        self.paint_hue = hue
        for weapon in self.weapons:
            weapon.repaint(hue)

    def input(self, key):
        slot = next((i for i, bound in enumerate(T.KEYS_WEAPON) if pressed(key, bound)), None)
        if slot is not None:
            self.select(slot)
        elif pressed(key, T.KEY_PREVIOUS_WEAPON):
            self.select(self.current - 1)
        elif pressed(key, T.KEY_NEXT_WEAPON):
            self.select(self.current + 1)
        elif pressed(key, T.KEY_FIRE) and mouse.locked:
            self.fire_buffer = FIRE_BUFFER
        elif pressed(key, T.KEY_SCOPE) and mouse.locked and self.weapon.alt and not self.weapon.alt_now():
            self.alt_buffer = FIRE_BUFFER
        elif pressed(key, T.KEY_RELOAD) and mouse.locked:
            self.reload()

    # --- frame ---

    def update(self):
        dt = min(time.dt, T.MAX_DT)
        weapon = self.weapon
        self.cooldown -= dt
        self.fire_buffer -= dt
        self.alt_buffer -= dt
        self.click -= dt
        if self.reloading and self.cooldown <= 0:
            self.reloading = False
            weapon.load()
        for entry in list(self.later):
            entry[0] -= dt
            if entry[0] <= 0:
                self.later.remove(entry)
                entry[1]()
        self.update_scope(dt)
        wants = held_keys[T.KEY_FIRE] and mouse.locked if weapon.automatic else self.fire_buffer > 0
        alt = weapon.alt and self.alt_buffer > 0
        katana = getattr(self.game, 'katana', None)
        self.stow = katana.stow if katana is not None else 0.0      # the gun drops while the katana is out
        if (wants or alt) and self.cooldown <= 0 and self.stow < 1:
            if weapon.rounds > 0 or self.endless:
                self.fire(alt=alt and not wants)
            elif not self.reload() and self.click <= 0:
                # nothing in the gun and nothing to put in it
                self.click = 0.35
                self.fire_buffer = self.alt_buffer = 0.0
                self.game.sfx.play('empty')
                self.game.hud.out_of_ammo()
        self.update_view(dt)

        self.flash_time -= dt
        if self.flash_time <= 0:
            self.muzzle_flash.enabled = False
        for tracer in self.tracers:
            if tracer['live']:
                self.update_tracer(tracer, dt)
        for impact in self.impacts:
            if impact['star'].enabled:
                impact['age'] += dt
                t = impact['age'] / IMPACT_TIME
                impact['star'].enabled = t < 1
                impact['star'].scale = impact['size'] * (0.5 + 0.5 * min(1.0, t * 3)) * (1 - 0.5 * max(0.0, t - 0.5))
        for rocket in self.rockets:
            if rocket['live']:
                self.update_rocket(rocket, dt)

    def update_scope(self, dt):
        self.scope_lock -= dt
        if self.weapon.can_scope and held_keys[T.KEY_SCOPE] and self.scope_lock <= 0:
            if self.scope_age == 0:
                self.game.sfx.play('scope_in', volume=0.6)
            self.scope_age += dt
            self.scope = min(1.0, self.scope + dt / T.LONGSHOT_SCOPE_TIME)
        else:
            self.scope_age = 0.0
            self.scope = max(0.0, self.scope - dt / T.LONGSHOT_UNSCOPE_TIME)
        self.game.player.zoom = self.scope
        if self.weapon.can_scope:
            self.game.player.zoom_fov = self.weapon.scope_fov

    def update_view(self, dt):
        """Recoil, the draw swing, sway against the mouse and a bob while running."""
        weapon = self.weapon
        player = self.game.player
        self.kick *= exp(-14 * dt)
        self.climb *= exp(-9 * dt)
        player.pivot.rotation_x = clamp(player.pivot.rotation_x - (self.climb - self.climb_applied), -89, 89)
        self.climb_applied = self.climb
        self.draw *= exp(-11 * dt)
        follow = 1 - exp(-12 * dt)
        self.sway += (Vec3(-mouse.velocity[0] * 1.6, -mouse.velocity[1] * 1.6, 0) - self.sway) * follow
        if player.grounded:
            self.stride += player.flat_speed * dt * 0.75
        bob = min(player.flat_speed / T.RUN_SPEED, 1.5) * (0.4 if player.sliding or not player.grounded else 1)

        rest = VIEW_POSITION + (SCOPE_POSITION - VIEW_POSITION) * self.scope
        hip = 1 - self.scope
        ready = 1 - clamp(self.cooldown / self.wait, 0, 1)
        # a reload that takes its own time tips the gun down and brings it back up
        dip = sin(pi * ready) if self.reloading and weapon.stat('reload') else 0.0
        self.view.position = rest + Vec3(
            clamp(self.sway.x, -0.05, 0.05) + sin(self.stride) * 0.007 * bob * hip,
            clamp(self.sway.y, -0.05, 0.05) - abs(sin(self.stride)) * 0.008 * bob * hip
            - 0.02 * self.kick - 0.3 * self.draw - 0.4 * self.stow - 0.13 * dip,
            -0.12 * self.kick)
        self.view.rotation_x = -9 * self.kick + 50 * self.draw + 40 * self.stow + 28 * dip
        self.view.rotation_z = -clamp(self.sway.x, -0.05, 0.05) * 120 * hip
        self.view.visible = self.scope < 0.75      # the scope overlay takes over

        weapon.animate(clamp(self.kick / weapon.kick, 0, 1), ready, dt)

    def fire(self, alt=False):
        """`alt`: the shot the scope key fires, for a weapon that has one."""
        weapon = self.weapon
        if weapon.rounds <= 0:
            if not self.endless:
                return
            weapon.rounds = weapon.mag
        self.reloading = False
        # keep the fraction of a frame the shot was late, so fast weapons hold their rate
        self.wait = weapon.spend()
        self.cooldown = self.wait + max(min(self.cooldown, 0.0), -T.MAX_DT)
        self.fire_buffer = self.alt_buffer = 0.0
        origin = camera.world_position
        direction = camera.forward
        muzzle = self.view.world_position + camera.up * weapon.muzzle[0] + direction * weapon.muzzle[1]
        if alt:
            weapon.alt_fire(origin, direction, muzzle)
        else:
            weapon.fire(origin, direction, muzzle)

        game = self.game
        self.kick = weapon.kick
        game.player.fov_kick = max(game.player.fov_kick, weapon.kick * 2)
        game.juice.shake(weapon.shake)
        game.sfx.play(weapon.sound, pitch=uniform(0.94, 1.06))
        self.muzzle_flash.enabled = True
        self.muzzle_flash.color = weapon.colour
        self.muzzle_flash.rotation_z = uniform(0, 360)
        self.muzzle_flash.scale = uniform(0.11, 0.17) * weapon.kick ** 0.5 * weapon.flash
        self.flash_time = 0.05 * weapon.flash
        if weapon.rounds <= 0:
            self.reload()       # the last round: reload without being asked

    # --- hitscan ---

    def hitscan(self, origin, direction, muzzle, damage, reach, colour, pierce=False, width=TRACER_WIDTH,
                life=TRACER_TIME, slug=None):
        """Trace one bullet. Damage is collected in self.pending so a shot of many
        pellets shows one number per enemy; call apply_hits() afterwards."""
        game = self.game
        pierce = pierce or game.player.rush.overdrive      # other bullets only pierce in Overdrive
        wall = raycast(origin, direction, distance=reach)
        limit = wall.distance if wall.hit else reach
        if wall.hit:
            game.beacon.struck(wall.entity)
        hits = game.enemies.ray_hits(origin, direction, limit)
        if not pierce:
            hits = hits[:1]
        for distance, enemy in hits:
            entry = self.pending.setdefault(enemy, [0.0, direction, origin + direction * distance])
            entry[0] += damage
        stopped = bool(hits) and not pierce
        end = origin + direction * (hits[0][0] if stopped else limit)
        self.show_tracer(muzzle, end, colour, width, life, slug)
        if not stopped and wall.hit:
            game.particles.sparks(end, wall.world_normal, colour)
        return end

    def apply_hits(self, push=4.0):
        """Deal the collected damage. Returns [(hit point, killed), ...], nearest first."""
        game = self.game
        multiplier = game.player.rush.damage_multiplier
        hits = []
        for enemy, (damage, direction, point) in list(self.pending.items()):
            amount = damage * multiplier
            killed = game.enemies.damage(enemy, amount, (direction[0] * push, 2.5, direction[2] * push))
            game.on_hit(enemy, amount, point, killed)
            hits.append((point, killed))
        self.pending.clear()
        if hits:
            game.hud.hit_marker(any(killed for _, killed in hits))
            game.sfx.play('hit', volume=0.7, pitch=0.8 + 0.5 * game.player.rush.fraction)
        return hits

    def show_tracer(self, start, end, colour, width=TRACER_WIDTH, life=TRACER_TIME, slug=None):
        """Draw one shot. `slug` is the (width, length) of the bullet at its head; None is a bare beam."""
        length = (end - start).length()
        if length < 0.5:
            return
        tracer = self.tracers[self.tracer_cursor]
        self.tracer_cursor = (self.tracer_cursor + 1) % TRACER_POOL
        travel = clamp(length / SLUG_SPEED, 0.045, 0.14) if slug else 0.0
        tracer.update(live=True, age=0.0, travel=travel, life=life, width=width, length=length, start=Vec3(*start),
                      along=(end - start) / length, end=Vec3(*end), colour=colour, slug_size=slug)
        trail, bullet = tracer['trail'], tracer['slug']
        trail.position = start
        trail.look_at(end)
        trail.scale = (width, width, length if not slug else 0.01)
        tracer['from'] = min(SLUG_START, length * 0.3) if slug else 0.0
        trail.color = colour
        trail.enabled = True
        bullet.enabled = bool(slug)
        if slug:
            bullet.position = start
            bullet.look_at(end)
            bullet.scale = (slug[0], slug[0], slug[1])
            bullet.color = colour

    def update_tracer(self, tracer, dt):
        tracer['age'] += dt
        age, travel, trail = tracer['age'], tracer['travel'], tracer['trail']
        if age < travel:
            # the bullet is still on its way, with a short streak behind it. Nothing is drawn
            # back to the gun, so the shot does not seem to bend when the player moves.
            first = tracer['from']
            reached = first + (tracer['length'] - first) * age / travel
            tail = max(reached - STREAK * tracer['width'], first)
            trail.position = tracer['start'] + tracer['along'] * tail
            trail.scale_z = max(reached - tail, 0.01)
            tracer['slug'].position = tracer['start'] + tracer['along'] * max(reached - tracer['slug_size'][1], 0)
            return
        if tracer['slug'].enabled:
            # it has landed: the streak goes with it
            tracer['slug'].enabled = False
            tracer['live'] = False
            trail.enabled = False
            self.show_impact(tracer['end'], tracer['colour'], tracer['slug_size'][0] * 3.5)
            return
        fade = 1 - (age - travel) / tracer['life']
        if fade <= 0:
            tracer['live'] = False
            trail.enabled = False
            return
        # thins out as it fades, but never to nothing
        trail.scale_x = trail.scale_y = tracer['width'] * (0.15 + 0.85 * fade)

    def show_impact(self, position, colour, size):
        impact = self.impacts[self.impact_cursor]
        self.impact_cursor = (self.impact_cursor + 1) % IMPACT_POOL
        impact['age'], impact['size'] = 0.0, size
        star_ = impact['star']
        star_.position = position
        star_.rotation_z = uniform(0, 360)
        star_.color = colour
        star_.scale = size * 0.5
        star_.enabled = True

    # --- rockets ---

    def launch_rocket(self, position, direction, weapon, remote=False):
        """Fly a rocket or a grenade for `weapon`, which says how fast and how big, what it looks
        like, and whose `burst` it ends in. A `remote` one sticks to whatever it hits and waits
        to be set off (see `detonate`)."""
        free = [r for r in self.rockets if not r['live']]
        # with every slot taken, the oldest rocket in flight gives way; a stuck grenade never does
        rocket = free[0] if free else next((r for r in self.rockets if not r['stuck']), self.rockets[0])
        rocket.update(live=True, age=0.0, pos=Vec3(*position), vel=Vec3(*direction) * weapon.stat('speed'),
                      life=T.ROCKET_LIFE, weapon=weapon, remote=remote, stuck=False, host=None, offset=None,
                      blink=0.0)
        body = rocket['entity']
        body.position = position
        body.look_at(position + direction)
        body.scale = weapon.stat('size')
        looks = rocket['looks']
        key = (type(weapon), remote)
        if key not in looks:
            looks[key] = weapon.sticky_look(body) if remote else Entity(parent=body, model=weapon.shell_model())
        rocket['spin'] = looks[key]
        for look in looks.values():
            look.enabled = look is rocket['spin']
        body.enabled = True

    def remotes(self):
        """The sticky grenades out, stuck or still flying."""
        return [r for r in self.rockets if r['live'] and r['remote']]

    def detonate(self, rocket):
        rocket['live'] = False
        rocket['entity'].enabled = False
        rocket['weapon'].burst(rocket['pos'])

    def stick(self, rocket, wall, enemy):
        """A remote grenade has hit `wall` (a raycast hit) or `enemy`: it stays there."""
        body = rocket['entity']
        rocket['stuck'] = True
        rocket['life'] = T.STICKY_LIFE
        rocket['vel'] = Vec3(0, 0, 0)
        if enemy is not None:
            rocket['host'] = enemy
            rocket['offset'] = rocket['pos'] - Vec3(enemy.x, enemy.y, enemy.z)
        elif wall is not None:
            normal = Vec3(*wall.world_normal)
            rocket['pos'] = Vec3(*wall.world_point) + normal * 0.12
            body.look_at(rocket['pos'] - normal)        # nose into the surface, lying on it
        body.position = rocket['pos']
        game = self.game
        game.sfx.play('stick')
        game.particles.burst(rocket['pos'], rocket['weapon'].colour, count=8, speed=3, size=0.05, life=0.25, up=1)
        if not self.told_sticky:
            self.told_sticky = True
            game.hud.notice(f'{key_name(T.KEY_SCOPE)} AGAIN TO SET IT OFF')

    def update_stuck(self, rocket, dt):
        rocket['life'] -= dt
        host = rocket['host']
        if host is not None:
            if host.alive and not host.hidden:
                rocket['pos'] = Vec3(host.x, host.y, host.z) + rocket['offset']
            else:
                rocket['host'] = None       # it stays where its host was
        body = rocket['entity']
        body.position = rocket['pos']
        rocket['blink'] -= dt
        lamp = rocket['spin'].lamp
        if rocket['blink'] <= 0:
            rocket['blink'] = T.STICKY_BLINK
            lamp.color = color.white
            self.game.sfx.play('beep', volume=0.3)
        elif rocket['blink'] < T.STICKY_BLINK * 0.6:
            lamp.color = color.hsv(0, 0, 0.35)
        if rocket['life'] <= 0:
            self.detonate(rocket)

    def update_rocket(self, rocket, dt):
        if rocket['stuck']:
            self.update_stuck(rocket, dt)
            return
        rocket['life'] -= dt
        pos, vel = rocket['pos'], rocket['vel']
        weapon = rocket['weapon']
        if weapon.drop:
            vel.y -= weapon.drop * dt
            rocket['entity'].look_at(pos + vel)
        step = vel * dt
        distance = step.length()
        direction = step / distance if distance > 1e-5 else Vec3(0, 0, 1)
        wall = raycast(pos, direction, distance=distance + 0.3)
        reach = wall.distance if wall.hit else distance
        bodies = self.game.enemies.ray_hits(pos, direction, reach)
        burst = rocket['life'] <= 0 or wall.hit or bool(bodies)
        if bodies:
            pos += direction * bodies[0][0]
        elif wall.hit:
            pos += direction * max(wall.distance - 0.3, 0)
        else:
            pos += step
        rocket['pos'] = pos
        body = rocket['entity']
        body.position = pos
        rocket['spin'].rotation_z += 720 * dt

        # exhaust: a hot flame that dies at once and smoke that hangs in the air
        particles = self.game.particles
        tail = pos - direction * 0.5
        rocket['age'] += dt
        if not weapon.trail:
            rocket['age'] = 0.0
        for _ in range(2 if rocket['age'] > 0.07 else 0):       # not until it has cleared the launcher
            particles.emit(tail, -direction * uniform(4, 10) + Vec3(uniform(-2, 2), uniform(-2, 2), uniform(-2, 2)),
                           (1, uniform(0.55, 0.9), 0.2, 1), uniform(0.1, 0.18), uniform(0.08, 0.16), gravity=0)
        if rocket['age'] > 0.07:
            particles.emit(tail, Vec3(uniform(-1, 1), uniform(0, 1.5), uniform(-1, 1)), (0.85, 0.85, 0.9, 1),
                           uniform(0.12, 0.2), uniform(0.4, 0.7), gravity=-2)
        if burst and rocket['remote'] and rocket['life'] > 0:
            self.stick(rocket, None if bodies else wall, bodies[0][1] if bodies else None)
        elif burst:
            rocket['live'] = False
            body.enabled = False
            rocket['weapon'].burst(pos)
