"""The two branches of each weapon. Each is its base weapon with a new trick and a view model to
match; its numbers and its tree are its branch's in data/trees.py, read through `self.stat` and
`self.perk`. Perks that act on enemies whoever hurt them are in game/enemies.py.

`VARIANTS` maps (slot, branch id) to the class, for Arsenal.equip.
"""
from math import cos, radians, sin
from random import choice, uniform

from ursina import Entity, Vec3, camera, color, destroy, raycast

from data import tuning as T
from fx.toon import barrel, box, build, placed, slab
from game import mods
from game.weapons import (BOOMER_SIZE, CREAM, DARK, METAL, WOOD, Boomer, Buzzer, Longshot, Popper, Scatter, bolts,
                          both, grip, groove, marks, rocket_model, spread)

FLAMES = ((1, 0.92, 0.35, 1), (1, 0.6, 0.12, 1), (1, 0.3, 0.06, 1))
ARC = color.hsv(190, 0.35, 1)
HEALTH = color.hsv(160, 0.45, 1)


# --- Popper ---

class Flamethrower(Popper):
    """Hold the trigger: a cone of fire that hurts everything in it and leaves it burning."""
    name = 'FLAMETHROWER'
    hue = 22
    accent_hue = 48
    kick = 0.18
    shake = 0.03
    sound = 'flame'
    muzzle = (0.03, 0.35)
    flash = 0.5
    flash_shape = (6, 0.6)      # a tongue of flame at the nozzle, more than a star

    def build_view(self):
        super().build_view()
        self.solid(
            (barrel(0.024, 0.25, 0.34, y=0.03, end_radius=0.044), DARK),        # nozzle
            (barrel(0.034, -0.02, 0.17, y=-0.07), self.accent),                 # fuel can
            (barrel(0.036, 0.05, 0.08, y=-0.07), DARK),
        )
        # flames licking back along the slide, a filler cap and a warning band on the can
        licks = [[(z, 0.004), (z + 0.045, 0.004), (z - 0.012, 0.03 + 0.016 * (i % 2))] for i, z in
                 enumerate((0.14, 0.09, 0.04, -0.01, -0.06))]
        tips = [[(z + 0.008, 0.004), (z + 0.034, 0.004), (z, 0.02 + 0.008 * (i % 2))] for i, z in
                enumerate((0.14, 0.09, 0.04, -0.01, -0.06))]
        self.slide_marks = self.trim(*marks(0.0345, licks, color.hsv(18, 0.85, 1)),
                                     *marks(0.0355, tips, color.hsv(48, 0.8, 1)))
        self.trim(
            (barrel(0.014, -0.035, -0.02, y=-0.07, sides=6), METAL),
            *[(box((0.012, 0.004, 0.016), (x, -0.036, 0.13)), DARK) for x in (-0.018, 0, 0.018)],
            *bolts(0.03, [(0.03, 0.31)], DARK),
        )

    def animate(self, recoil, ready, dt):
        super().animate(recoil, ready, dt)
        self.slide_marks.z = self.slide.z

    def fire(self, origin, direction, muzzle):
        game = self.game
        reach, damage = self.stat('range'), self.stat('damage')
        edge = cos(radians(self.stat('cone')))
        burn = self.stat('burn') * game.player.rush.damage_multiplier
        for enemy in game.enemies.alive:
            to = enemy.centre - origin
            distance = to.length()
            along = to.dot(direction)
            if along <= 0 or distance > reach + enemy.radius:
                continue
            # in the cone, or close enough to its middle that the body is in the way
            if along / distance < edge and distance * distance - along * along > enemy.radius ** 2:
                continue
            clear = distance - enemy.radius
            if clear > 0.1 and raycast(origin, to / distance, distance=clear).hit:
                continue    # behind a wall
            self.arsenal.pending[enemy] = [damage, direction, enemy.centre]
            enemy.ignite(burn, self.stat('burn_time'))
        self.arsenal.apply_hits(push=1.0)
        # a stream of fire that leaves white-hot and cools through yellow and red to smoke, growing
        # and rising as it goes
        start = muzzle + direction * 0.7        # clear of the eye, where squares this close would fill it
        for _ in range(9):
            game.pixels.emit(start, spread(direction, self.stat('cone')) * uniform(0.45, 1) * reach * 3.2, 'flame',
                             uniform(0.04, 0.13), uniform(0.25, 0.45), 0, 7, gravity=-5, drag=2.5)


class Taser(Popper):
    """The shot jumps from the enemy it hits to the ones standing nearest, stunning them all."""
    name = 'TASER'
    hue = 55
    accent_hue = 195
    sound = 'shot_popper'
    trail_look = 'spark'

    def build_view(self):
        super().build_view()
        self.solid(
            (box((0.012, 0.012, 0.07), (-0.02, 0.03, 0.29)), METAL),            # prongs
            (box((0.012, 0.012, 0.07), (0.02, 0.03, 0.29)), METAL),
            (box((0.07, 0.03, 0.05), (0, -0.01, 0.2)), self.accent),            # cell
        )
        # a lightning bolt down each side of the slide, and windings round the barrel
        zag = [[(0.17, 0.052), (0.185, 0.052), (0.115, 0.026), (0.1, 0.026)],
               [(0.13, 0.036), (0.145, 0.036), (0.07, 0.01), (0.055, 0.01)],
               [(0.085, 0.02), (0.1, 0.02), (0.0, -0.004), (0.02, 0.008)]]
        self.slide_marks = self.trim(*marks(0.0345, zag, ARC))
        self.trim(
            *[(barrel(0.019, z, z + 0.008, y=0.03, sides=8), color.hsv(30, 0.7, 0.95)) for z in (0.205, 0.22, 0.235)],
            *bolts(0.036, [(-0.01, 0.2)], CREAM),
        )

    def animate(self, recoil, ready, dt):
        super().animate(recoil, ready, dt)
        self.slide_marks.z = self.slide.z

    def fire(self, origin, direction, muzzle):
        game, arsenal = self.game, self.arsenal
        arsenal.hitscan(origin, direction, muzzle, self.stat('damage'), self.stat('range'), ARC, slug=self.slug)
        struck = list(arsenal.pending)
        if struck:
            reach = self.stat('arc_reach') ** 2
            amount = self.stat('damage') * self.stat('arc_share')
            last = struck[0]
            for _ in range(round(self.stat('arcs'))):
                near = [e for e in game.enemies.alive
                        if e not in struck and (e.centre - last.centre).length_squared() < reach]
                if not near:
                    break
                near.sort(key=lambda e: (e.centre - last.centre).length_squared())
                # fork: the arc splits, and only its first end carries on down the line
                for target in near[:2 if self.perk('fork') else 1]:
                    arsenal.pending[target] = [amount, (target.centre - last.centre).normalized(), target.centre]
                    # lightning, crackling from one to the next, with a star where it strikes
                    game.arcs.show(last.centre, target.centre, ARC, width=0.14, life=0.18)
                    arsenal.show_impact(target.centre, ARC, 0.6)
                    struck.append(target)
                last = near[0]
            for enemy in struck:
                enemy.stagger(self.stat('stun'))
            if len(struck) > 1:
                game.sfx.play('zap', volume=0.8, pitch=uniform(0.9, 1.2))
        arsenal.apply_hits()


# --- Scatter ---

class Impulse(Scatter):
    """A grenade launcher. Its grenades arc, and their blasts are all push: enemies are hurled
    away, and the player is thrown without being hurt."""
    name = 'IMPULSE'
    hue = 262
    accent_hue = 165
    kick = 2.0
    sound = 'shot_rocket'
    muzzle = (0.0, 0.36)
    flash = 1.6
    trail = False               # a grenade has no motor: it leaves a dotted line along its arc
    look = 'impulse'
    drop = T.GRENADE_DROP
    alt = True                  # the scope key fires a sticky grenade, and sets it off
    hold = (0, -0.14, -0.25)
    fore = (0, -0.16, 0.16)

    def build_view(self):
        self.solid(
            (barrel(0.062, 0.02, 0.34), METAL),                                 # fat barrel
            (barrel(0.07, 0.3, 0.345), DARK),
            (barrel(0.052, 0.34, 0.35), DARK),                                  # bore
            (box((0.11, 0.1, 0.12), (0, -0.01, -0.2)), self.paint),             # frame
            (slab([(-0.26, 0.03), (-0.26, -0.05), (-0.46, -0.12), (-0.46, -0.01)], 0.06), WOOD),
            (grip(-0.2, -0.06, width=0.055, drop=0.14), DARK),
            (box((0.05, 0.09, 0.05), (0, -0.1, 0.16)), DARK),                   # fore grip
            (box((0.02, 0.05, 0.02), (0, 0.09, 0.3)), self.accent),             # ladder sight
            (box((0.05, 0.012, 0.02), (0, 0.11, 0.3)), self.accent),
        )
        # the cylinder turns a chamber on for every grenade fired
        self.drum = self.solid(
            (barrel(0.088, -0.14, 0.02, sides=6), self.paint),
            *[(barrel(0.02, 0.02, 0.03, x=x, y=y, sides=6), DARK)
              for x, y in ((0, 0.052), (0.045, 0.026), (0.045, -0.026), (0, -0.052), (-0.045, -0.026), (-0.045, 0.026))],
            (barrel(0.092, -0.08, -0.05, sides=6), self.accent),
        )
        self.turn = 0.0
        # arrows on the barrel that point the way the blast goes, bolts and a seam on the frame
        arrows = [[(z, 0.03), (z + 0.02, 0.03), (z + 0.045, 0.0), (z + 0.02, -0.03), (z, -0.03), (z + 0.025, 0.0)]
                  for z in (0.08, 0.15, 0.22)]
        self.trim(
            *both(lambda side: [(slab(shape[:3] + shape[5:], 0.004, x=side * 0.063), color.hsv(self.accent_hue, 0.6, 0.95))
                                for shape in arrows]),
            *both(lambda side: [(slab(shape[2:], 0.004, x=side * 0.063), color.hsv(self.accent_hue, 0.6, 0.95))
                                for shape in arrows]),
            *bolts(0.057, [(0.02, -0.16), (0.02, -0.24), (-0.04, -0.2)]),
            *groove(0.057, -0.012, -0.25, -0.15),
            *bolts(0.032, [(-0.02, -0.33), (-0.06, -0.41)], CREAM),
        )

    def animate(self, recoil, ready, dt):
        self.drum.rotation_z += (self.turn - self.drum.rotation_z) * min(1.0, 14 * dt)

    def shell_model(self):
        return build([
            (barrel(0.1, -0.13, 0.1, sides=8), color.hsv(self.hue, 0.5, 0.92)),
            (barrel(0.1, 0.1, 0.2, sides=8, end_radius=0.045), CREAM),
            (barrel(0.107, -0.05, 0.0, sides=8), color.hsv(self.accent_hue, 0.6, 0.95)),
            (barrel(0.08, -0.17, -0.13, sides=8), DARK),
        ], outline=0.022)

    def sticky_look(self, parent):
        """The sticky grenade: the same shell with three barbs on its nose and a lamp that blinks
        once it is stuck. The lamp is the entity's `lamp`."""
        barbs = [(placed(barrel(0.025, 0.0, 0.14, sides=5, end_radius=0.005), (0, 0, 0.17), yaw=0, pitch=0), DARK)]
        barbs += [(placed(barrel(0.025, 0.0, 0.14, sides=5, end_radius=0.005), (0.06 * cos(radians(a)), 0.06 * sin(radians(a)), 0.15),
                          yaw=12 * cos(radians(a)), pitch=-12 * sin(radians(a))), DARK) for a in (90, 210, 330)]
        look = Entity(parent=parent, model=build([
            (barrel(0.1, -0.13, 0.1, sides=8), color.hsv(self.accent_hue, 0.55, 0.85)),
            (barrel(0.1, 0.1, 0.18, sides=8, end_radius=0.06), CREAM),
            (barrel(0.107, -0.05, 0.0, sides=8), color.hsv(self.hue, 0.6, 0.95)),
            (barrel(0.08, -0.17, -0.13, sides=8), DARK),
            *barbs,
        ], outline=0.022))
        look.lamp = Entity(parent=look, model=build([(barrel(0.05, -0.2, -0.16, sides=8), color.white)], 0.012),
                           color=color.hsv(0, 0, 0.35))
        return look

    def fire(self, origin, direction, muzzle):
        self.launch(direction, muzzle, remote=False)

    def alt_now(self):
        """A sticky grenade already out goes off now, wherever it is; otherwise it is a shot."""
        out = self.arsenal.remotes()
        for rocket in out:
            self.arsenal.detonate(rocket)
        return bool(out)

    def alt_fire(self, origin, direction, muzzle):
        self.launch(direction, muzzle, remote=True)

    def launch(self, direction, muzzle, remote):
        game, arsenal = self.game, self.arsenal
        self.turn += 60
        arsenal.launch_rocket(muzzle, (direction + camera.up * 0.05).normalized(), self, remote=remote)
        game.player.add_impulse(-direction * T.IMPULSE_KICK)
        arsenal.climb += 1.5
        game.blasts.show(muzzle + direction * 0.4, 0.3, self.colour, life=0.18, core=False)

    def burst(self, position):
        """A grenade this weapon fired has just gone off here."""
        position = Vec3(*position)
        self.blast(position, 1.0)
        if self.perk('aftershock'):
            self.arsenal.later.append([T.AFTERSHOCK_DELAY, lambda: self.blast(position, T.AFTERSHOCK_SHARE)])

    def blast(self, position, share):
        game = self.game
        radius = self.stat('radius')
        if self.perk('concuss'):
            for _, enemy in game.enemies.in_radius(position, radius):
                enemy.stagger(T.CONCUSS_TIME)       # before the blast, which is what throws them
        game.explode(position, radius, self.stat('damage') * share, self.colour,
                     player_knock=self.stat('self_knock') * share, throw=self.stat('knock') * share, lift=True,
                     look='impulse')


class Ice(Scatter):
    """The double barrel loaded with frost: what it hits is slowed."""
    name = 'ICE'
    hue = 196
    accent_hue = 215
    sound = 'shot_scatter'
    slug_look = 'crystal'       # shards of ice, not pellets

    def build_view(self):
        super().build_view()
        self.solid(
            (barrel(0.04, 0.4, 0.46, x=-0.034), CREAM),                         # frosted muzzles
            (barrel(0.04, 0.4, 0.46, x=0.034), CREAM),
            (barrel(0.03, -0.02, 0.1, y=0.05), self.accent),                    # coolant bottle on the rib
            (barrel(0.017, 0.1, 0.14, y=0.05), DARK),
        )
        self.solid(         # icicles under the barrels
            *[(slab([(z, -0.03), (z + 0.03, -0.03), (z + 0.015, -0.075 - 0.02 * (i % 2))], 0.016), CREAM)
              for i, z in enumerate((0.26, 0.3, 0.34, 0.38))])
        # a snowflake on each side of the receiver, and frost creeping back from the muzzles
        self.trim(
            *both(lambda side: [(placed(box((0.004, 0.012, 0.11)), (side * 0.0775, -0.012, -0.1), pitch=turn), CREAM)
                                for turn in (0, 60, 120)]),
            *both(lambda side: [(box((0.005, 0.03, 0.03), (side * 0.0775, -0.012, -0.1)), self.accent)]),
            *[(box((0.02, 0.004, 0.03 + 0.02 * (i % 2)), (x, 0.034, 0.37 - 0.01 * (i % 2))), CREAM)
              for i, x in enumerate((-0.05, -0.02, 0.02, 0.05))],
        )

    def landed(self, pending):
        game = self.game
        slow, seconds, freeze = self.stat('chill'), self.stat('chill_time'), self.perk('deep_freeze')
        for enemy, entry in pending.items():
            enemy.chill(slow, seconds, freeze)
            game.pixels.scatter(entry[2], 'frost', count=8, speed=4, size=0.07, life=0.6, gravity=8, up=2)


# --- Longshot ---

class Dragon(Longshot):
    """One enormous shot. Fired in Overdrive it hits harder still, bursts where it lands and
    is ready again sooner."""
    name = 'DRAGON'
    hue = 2
    accent_hue = 44
    heft = 1.35
    kick = 3.0
    shake = 1.1
    flash = 2.8
    flash_shape = (6, 0.3)
    trail_look = 'dragon'       # embers left hanging all along the shot
    reticle = 'dragon'
    scope_fov = 28.0        # a long glass: it sees further in than the plain rifle's

    def build_scope(self):
        """A long, heavy glass with a flared eye, banded in gold."""
        self.solid(
            (box((0.03, 0.045, 0.04), (0, 0.062, -0.02)), DARK),                # mounts
            (box((0.03, 0.045, 0.04), (0, 0.062, 0.2)), DARK),
            (barrel(0.036, -0.1, 0.3, y=0.115, sides=8), self.paint),           # tube
            (barrel(0.036, 0.3, 0.42, y=0.115, sides=8, end_radius=0.06), DARK),    # the wide front lens
            (barrel(0.052, 0.415, 0.425, y=0.115, sides=8), color.hsv(20, 0.8, 1)),
            (barrel(0.046, -0.17, -0.1, y=0.115, sides=8), DARK),               # eyepiece
            (barrel(0.036, -0.176, -0.17, y=0.115, sides=8), color.hsv(20, 0.8, 1)),
            *[(barrel(0.04, z, z + 0.02, y=0.115, sides=8), self.accent) for z in (-0.04, 0.1, 0.24)],
            (box((0.012, 0.05, 0.05), (0, 0.165, 0.1)), self.accent),           # a fin for a turret
        )

    def build_view(self):
        super().build_view()
        self.solid(
            (box((0.09, 0.05, 0.1), (0, 0.0, 0.76)), self.accent),              # jaw round the muzzle
            (box((0.012, 0.06, 0.05), (-0.03, 0.05, 0.74)), CREAM),             # horns
            (box((0.012, 0.06, 0.05), (0.03, 0.05, 0.74)), CREAM),
            *[(box((0.014, 0.035, 0.05), (0, 0.16, z)), self.accent) for z in (-0.04, 0.04, 0.12)],    # spines
        )

    def build_trim(self):
        """Scales down the receiver, teeth round the muzzle and a slit eye."""
        gold = color.hsv(self.accent_hue, 0.7, 1)
        scales = [[(z, y + 0.014), (z + 0.03, y), (z, y - 0.014)]
                  for row, y in enumerate((0.022, -0.006, -0.034)) for z in
                  [0.16 - 0.045 * i - 0.022 * (row % 2) for i in range(6)]]
        self.trim(
            *marks(0.037, scales, gold),
            *[(slab([(0.77, y), (0.81, y + drop), (0.77, y + 2 * drop)], 0.012, x=x), CREAM)
              for x in (-0.03, 0, 0.03) for y, drop in ((0.025, -0.012), (-0.025, 0.012))],
            *marks(0.031, [[(0.2, -0.02), (0.3, -0.006), (0.4, -0.02), (0.3, -0.034)]], gold),      # the eye
            *marks(0.0325, [[(0.28, -0.03), (0.32, -0.03), (0.32, -0.01), (0.28, -0.01)]], DARK),
            *bolts(0.037, [(0.03, -0.1), (-0.03, -0.1)], DARK),
        )

    def shot_damage(self):
        bonus = self.stat('od_bonus') if self.game.player.rush.overdrive else 1
        return self.stat('damage') * bonus

    def landed(self, hits):
        game = self.game
        if not hits:
            return
        if self.perk('ember'):
            for enemy in self.struck:
                if enemy.alive:
                    enemy.ignite(*T.EMBER_BURN)
        point = hits[0][0]
        if game.player.rush.overdrive:
            game.explode(point, self.stat('od_radius'), self.stat('od_blast'), self.colour, look='dragon')
            self.arsenal.cooldown *= 1 - self.stat('od_refund')
            game.popups.show(point + Vec3(0, 1.8, 0), 'DRAGON FIRE!', self.colour, size=1.6)
        elif self.perk('always_lit'):
            game.explode(point, self.stat('od_radius') * T.ALWAYS_LIT_SHARE, self.stat('od_blast') * T.ALWAYS_LIT_SHARE,
                         self.colour, look='dragon')


class SemiAuto(Longshot):
    """A light rifle that is cocked by hand after a shot from the hip, but fires again almost at
    once after a quickscope: scope, click, scope, click."""
    name = 'SEMI-AUTO'
    hue = 205
    accent_hue = 30
    heft = 0.45
    kick = 1.3
    shake = 0.4
    flash = 1.4
    slug = (0.2, 1.2)
    reticle = 'holo'
    scope_fov = 50.0        # a holo sight barely magnifies: quick to find the target in

    def build_scope(self):
        """An open holo sight: a hood on a short rail, with a pane of glass in it."""
        self.solid(
            (box((0.04, 0.02, 0.2), (0, 0.054, 0.05)), DARK),                   # rail
            (box((0.012, 0.07, 0.07), (-0.032, 0.1, 0.06)), DARK),              # hood
            (box((0.012, 0.07, 0.07), (0.032, 0.1, 0.06)), DARK),
            (box((0.076, 0.012, 0.07), (0, 0.14, 0.06)), DARK),
            (box((0.05, 0.05, 0.006), (0, 0.105, 0.085)), color.hsv(190, 0.5, 1)),      # the glass
            (box((0.03, 0.03, 0.05), (0, 0.075, -0.03)), self.accent),          # emitter
            (box((0.012, 0.03, 0.012), (0, 0.08, 0.2)), self.accent),           # front post
        )

    def build_view(self):
        super().build_view()
        self.solid(
            (box((0.052, 0.13, 0.075), (0, -0.14, 0.08)), self.accent),         # long magazine
            (box((0.056, 0.02, 0.08), (0, -0.2, 0.08)), DARK),
        )
        self.chain = 0          # quickscope hits in a row, for the chain perk
        self.chain_time = 0.0

    def build_trim(self):
        """A vented handguard, a warning flash on the receiver and a row of tally marks."""
        orange = color.hsv(self.accent_hue, 0.75, 1)
        vents = [[(z, 0.006), (z + 0.03, 0.006), (z + 0.022, -0.024), (z - 0.008, -0.024)]
                 for z in (0.22, 0.265, 0.31, 0.355, 0.4)]
        self.trim(
            *marks(0.031, vents, DARK),
            *marks(0.037, [[(-0.1, 0.03), (-0.06, 0.03), (-0.09, -0.03), (-0.13, -0.03)],
                           [(-0.04, 0.03), (0.0, 0.03), (-0.03, -0.03), (-0.07, -0.03)]], orange),
            *marks(0.037, [[(z, 0.03), (z + 0.008, 0.03), (z + 0.008, 0.0), (z, 0.0)] for z in (0.08, 0.1, 0.12, 0.14)],
                   CREAM),
            *bolts(0.037, [(-0.03, 0.17), (0.03, 0.17), (-0.03, 0.05)]),
            *[(barrel(0.024, z, z + 0.012, sides=8), orange) for z in (0.5, 0.66)],
        )

    def animate(self, recoil, ready, dt):
        # cocking: the rifle is rolled over and the handle hauled back and let go
        stroke = self.cycle(ready, 0.2, 0.75, 'bolt')
        self.bolt.z = -0.13 * stroke
        self.bolt.y = 0.03 * min(1.0, stroke * 3)
        self.view.rotation_z = -24 * stroke
        self.view.rotation_x = -7 * stroke
        self.view.y = -0.03 * stroke
        self.chain_time -= dt
        if self.chain_time <= 0:
            self.chain = 0

    def shot_damage(self):
        chained = self.chain if self.perk('chain') and self.arsenal.quick_ready else 0
        return self.stat('damage') * (1 + T.CHAIN_STEP * chained)

    def landed(self, hits):
        game = self.game
        if not (self.quick and hits):
            self.chain = 0
            return
        if self.perk('chain'):
            self.chain = min(self.chain + 1, T.CHAIN_MAX)
            self.chain_time = T.CHAIN_TIME
            if self.chain > 1:
                game.popups.show(hits[0][0] + Vec3(0, 2.0, 0), f'CHAIN x{self.chain}', self.colour, size=1.3)
        if self.perk('adrenaline') and any(killed for _, killed in hits):
            rush = game.player.rush
            rush.value = min(100.0, rush.value + 100 * T.ADRENALINE_RUSH)


# --- Boomer ---

class Tiger(Boomer):
    """A bigger rocket and a bigger blast, which you had better not be standing in."""
    name = 'TIGER'
    hue = 28
    accent_hue = 48
    kick = 3.2
    shake = 0.9
    flash = 2.8
    muzzle = (0.0, 0.62 * BOOMER_SIZE)
    throw = T.TIGER_PLAYER_KNOCK
    look = 'tiger'

    def shell_model(self):
        return rocket_model(self.hue, fat=1.5)

    def build_view(self):
        super().build_view()
        # a fatter tube sleeved over the launcher, a wide mouth, and a warhead to fill it
        self.solid(
            (barrel(0.078, -0.28, 0.44), self.paint),
            (barrel(0.078, 0.44, 0.56, end_radius=0.112), CREAM),
            (barrel(0.09, 0.553, 0.566), DARK),
            (barrel(0.112, -0.46, -0.28, end_radius=0.078), DARK),
            *[(barrel(0.083, z, z + 0.04), DARK) for z in (0.06, 0.16, 0.26, 0.36)],        # stripes
            (box((0.03, 0.03, 0.5), (0, 0.092, 0.08)), DARK),                               # spine
        )
        destroy(self.warhead)
        self.warhead = self.solid(
            (barrel(0.07, 0.5, 0.58), self.accent),
            (barrel(0.07, 0.58, 0.76, end_radius=0.012), CREAM),
            (barrel(0.074, 0.53, 0.55), DARK),
        )

    def build_trim(self):
        """Tiger stripes raked down the sleeve, rivets round both ends, and a snarl painted by the muzzle."""
        stripes = [[(z, 0.05), (z + 0.035, 0.05), (z - 0.015, -0.04)] for z in (-0.2, -0.1, 0.0, 0.1, 0.2, 0.3)]
        self.trim(
            *marks(0.08, stripes, DARK),
            *[(slab([(0.44, y), (0.5, y + 0.012), (0.44, y + 0.024)], 0.01, x=x), CREAM)
              for x in (-0.07, 0.07) for y in (-0.03, 0.006)],                  # teeth
            *[(box((0.012, 0.006, 0.012), (x, 0.081, z)), METAL) for z in (-0.25, 0.41) for x in (-0.03, 0, 0.03)],
            *bolts(0.081, [(0, -0.25), (0, 0.41)]),
        )

    def burst(self, position):
        game = self.game
        suit = self.perk('blast_suit')
        radius, damage = self.stat('radius'), self.stat('damage')
        game.explode(position, radius, damage, self.colour,
                     player_knock=self.throw * (T.BLAST_SUIT_KNOCK if suit else 1),
                     self_damage=0 if suit else max(self.stat('self_damage'), 0), look=self.look)
        if self.perk('cluster'):
            turn = uniform(0, 360)
            for i in range(T.CLUSTER_COUNT):
                a = radians(turn + i * 360 / T.CLUSTER_COUNT)
                at = Vec3(*position) + Vec3(cos(a) * radius * 0.45, 0.3, sin(a) * radius * 0.45)
                game.explode(at, radius * T.CLUSTER_SHARE, damage * T.CLUSTER_SHARE, self.colour, quiet=True)
                game.pixels.show(at, radius * T.CLUSTER_SHARE, 'tiger', shape=False)


class Poison(Boomer):
    """A small rocket that leaves a wide cloud of poison where it lands. It never hurts you."""
    name = 'POISON'
    hue = 62                # toxic yellow: a green launcher would read as "parry this"
    accent_hue = 285
    kick = 2.2
    throw = T.POISON_PLAYER_KNOCK
    look = 'poison'

    def build_view(self):
        super().build_view()
        self.solid(
            (barrel(0.04, 0.0, 0.14, y=-0.1), self.accent),                     # gas bottle
            (barrel(0.02, 0.14, 0.18, y=-0.1), DARK),
        )

    def build_trim(self):
        """Hazard bands on the tube, drips running down from them, and a valve on the bottle."""
        acid = color.hsv(self.hue, 0.75, 1)
        drips = [[(z, 0.03), (z + 0.022, 0.03), (z + 0.011, -0.02 - 0.02 * (i % 2))] for i, z in
                 enumerate((0.19, 0.225, 0.26, 0.295, 0.33))]
        self.trim(
            *marks(0.062, drips, acid),
            *[(box((0.03, 0.005, 0.022), (0, 0.0625, z)), self.accent if i % 2 else CREAM)
              for i, z in enumerate((0.18, 0.205, 0.23, 0.255, 0.28, 0.305, 0.33))],
            *[(box((0.012, 0.006, 0.012), (0, 0.061, z)), METAL) for z in (-0.09, 0.03)],
            *bolts(0.061, [(0, -0.09), (0, 0.03)]),
            (box((0.03, 0.02, 0.012), (0, -0.1, 0.19)), METAL),                 # valve wheel
        )

    def burst(self, position):
        super().burst(position)
        game = self.game
        radius = self.stat('cloud_radius')
        game.clouds.add(position, radius, self.stat('cloud'), self.stat('cloud_time'), ring=False)
        game.pixels.ring(position, radius, 'poison')       # how far the cloud reaches, in pixels
        game.sfx.play('poison')


# --- Buzzer ---

class Turner(Buzzer):
    """A Buzzer whose bullets now and then bring an enemy over to the player's side."""
    role = ''               # 'fighter' or 'healer'
    convert_look = 'white'  # the pixels an enemy bursts in as it changes sides

    def fire(self, origin, direction, muzzle):
        self.turned = []
        super().fire(origin, direction, muzzle)
        game = self.game
        for enemy in self.turned:
            point = enemy.centre
            seconds = self.stat('ally_time')
            if game.enemies.convert(enemy, self.role, seconds, **self.ally_numbers()):
                game.popups.show(point + Vec3(0, 1.8, 0), 'CONVERTED!', self.colour, size=2.2)
                game.pixels.scatter(point, self.convert_look, count=50, speed=10, size=0.08, life=0.8, gravity=4, up=2)
                game.blasts.show(point, 4.0, self.colour, life=0.5, core=False)
                game.hud.notice(f'{self.role.upper()} ON YOUR SIDE FOR {seconds:.0f}s')
                game.hud.hit_marker(True, size=2.2, tint=self.colour)
                game.juice.hitstop(T.HITSTOP_PARRY)
                game.juice.shake(0.4)
                game.sfx.play('convert')

    def landed(self, pending):
        for enemy in pending:
            if mods.roll(self.stat('convert_chance')):
                self.turned.append(enemy)

    def ally_numbers(self):
        """What Astronaut.convert is told about the ally this weapon makes."""
        return {}


class Darkness(Turner):
    """Faster. A bullet may steal health, and once in a long while turns its target into a fighter."""
    name = 'DARKNESS'
    hue = 275
    accent_hue = 350
    role = 'fighter'
    trail_look = 'legion'       # a wisp of violet shadow along each shot
    convert_look = 'legion'

    def build_view(self):
        super().build_view()
        self.solid(
            (box((0.02, 0.05, 0.1), (0, -0.07, 0.27)), self.accent),            # fang under the barrel
            (box((0.085, 0.02, 0.05), (0, 0.06, -0.12)), self.accent),
        )
        # thorns raked back along the top, and a slit eye and claw marks on each side
        self.solid(*[(slab([(z, 0.064), (z + 0.035, 0.064), (z - 0.012, 0.1)], 0.014), self.accent)
                     for z in (-0.04, 0.03, 0.1, 0.17)])
        self.trim(
            *marks(0.0395, [[(-0.02, 0.012), (0.04, 0.026), (0.1, 0.012), (0.04, -0.002)]], self.accent),
            *marks(0.0405, [[(0.03, 0.022), (0.05, 0.022), (0.05, 0.002), (0.03, 0.002)]], DARK),
            *marks(0.0395, [[(z, -0.01), (z + 0.012, -0.01), (z - 0.025, -0.045)] for z in (0.14, 0.165, 0.19)], CREAM),
        )

    def ally_numbers(self):
        return {'punch': self.stat('ally_damage')}

    def fire(self, origin, direction, muzzle):
        super().fire(origin, direction, muzzle)
        kills = sum(1 for _, killed in self.hits if killed)
        if kills and self.perk('feast'):
            self.heal(T.FEAST_HEAL * kills, self.hits[0][0])

    def landed(self, pending):
        super().landed(pending)
        player = self.game.player
        for entry in pending.values():
            if mods.roll(self.stat('steal_chance')):
                stolen = self.stat('steal')
                entry[0] += stolen / player.rush.damage_multiplier      # taken from the enemy as it stands
                self.heal(stolen, entry[2])

    def heal(self, amount, point):
        """Health taken out of an enemy at `point`: it is seen and heard crossing to the player."""
        game = self.game
        game.player.heal(amount)
        game.popups.show(point + Vec3(0, 1.0, 0), f'+{amount:.0f} HP', HEALTH, size=1.8)
        # drops of it, crimson, fly from the wound into the player's chest
        flight = 0.3
        to = camera.world_position - Vec3(0, 0.35, 0) - point
        for _ in range(14):
            start = point + Vec3(uniform(-0.4, 0.4), uniform(-0.4, 0.4), uniform(-0.4, 0.4))
            game.pixels.emit(start, to / flight * uniform(0.85, 1.1), 'heart', uniform(0.06, 0.1), flight, 1, 4, drag=0)
        game.hud.heal_flash(amount)
        game.sfx.play('steal', volume=1.0, pitch=uniform(0.95, 1.1))


class Light(Turner):
    """Slower and harder. A bullet may turn its target into a healer that follows you."""
    name = 'LIGHT'
    hue = 50
    accent_hue = 190
    role = 'healer'
    kick = 0.6
    trail_look = 'gold'         # a glitter of gold along each shot
    convert_look = 'heart'

    def build_view(self):
        super().build_view()
        self.solid(
            (barrel(0.042, 0.3, 0.33), CREAM),                                  # ring round the shroud
            (box((0.085, 0.02, 0.05), (0, 0.06, -0.12)), self.accent),
        )
        # a sun on each side with its rays, and a halo standing over the receiver
        gold = color.hsv(46, 0.7, 1)
        self.trim(
            *both(lambda side: [(placed(box((0.004, 0.008, 0.13)), (side * 0.0395, 0.0, 0.03), pitch=turn), gold)
                                for turn in (0, 45, 90, 135)]),
            *both(lambda side: [(box((0.005, 0.036, 0.036), (side * 0.0395, 0.0, 0.03)), CREAM)]),
            *bolts(0.0395, [(0.03, -0.11), (-0.03, -0.11)], gold),
        )
        self.solid((barrel(0.03, -0.01, 0.0, y=0.105, sides=8), gold),
                   (barrel(0.02, -0.012, 0.002, y=0.105, sides=8), self.paint))

    def ally_numbers(self):
        return {'heal': self.stat('heal'), 'reach': self.stat('heal_radius')}


VARIANTS = {
    ('SCATTER', 'impulse'): Impulse, ('SCATTER', 'ice'): Ice,
    ('POPPER', 'flame'): Flamethrower, ('POPPER', 'taser'): Taser,
    ('LONGSHOT', 'dragon'): Dragon, ('LONGSHOT', 'semi'): SemiAuto,
    ('BOOMER', 'tiger'): Tiger, ('BOOMER', 'poison'): Poison,
    ('BUZZER', 'dark'): Darkness, ('BUZZER', 'light'): Light,
}
