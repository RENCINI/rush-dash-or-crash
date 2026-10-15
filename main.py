import sys
from pathlib import Path
from random import uniform

from ursina import Entity, Ursina, Vec3, application, clamp, destroy, mouse, time, window

from audio.mixer import Sfx
from data import controls
from data import tuning as T
from data.levels import LEVELS
from data.progress import Progress
from data.settings import Settings
from fx.blast import Blasts
from fx.juice import Juice
from fx.particles import Particles
from fx.pixels import Pixels
from fx.popups import Popups
from fx.postfx import PostFx
from fx import shaders
from game import mods
from game.clouds import Clouds
from game.director import Director
from game.enemies import Enemies
from game.heart import RunawayHeart
from game.beacon import Beacon
from game.chain import Chain
from game.katana import PARRY_GREEN, Katana
from game.maps import MAPS
from game.pickups import Pickups
from game.player import Player
from game.weapons import Arsenal
from ui.hud import GOLD, Hud, rush_colour
from ui.menus import Menu
from ui.score import tier_colour
from ui.shop import Shop
from ui.tally import Tally

# player event -> (sound, volume, pitch)
CHIP_STREAK = 0.6       # chips picked up this close together ring higher and higher

MOVE_SOUNDS = {
    'jump': ('jump', 0.5, 1.0), 'double_jump': ('jump', 0.5, 1.35), 'wall_kick': ('jump', 0.6, 1.7),
    'dash': ('dash', 0.9, 1.0), 'slide': ('slide', 0.6, 1.0), 'pad': ('pad', 0.8, 1.0),
    'boost': ('boost', 0.7, 1.0), 'hurt': ('hurt', 0.9, 1.0), 'death': ('overdrive_end', 1.0, 0.6),
}


class Session(Entity):
    """Owns the running match and connects gameplay to sound and effects."""

    def __init__(self, mute=False, settings=None):
        super().__init__()
        self.settings = settings or Settings()
        # what has been earned is kept beside the settings, for good
        self.progress = Progress(self.settings.path.with_name('progress.json'))
        mods.use(self.progress)
        self.menu = None
        self.kills = 0
        self.chain = Chain()
        self.chip_streak = 0
        self.chip_timer = 0.0
        self.was_overdrive = False
        self.sfx = Sfx(mute)
        self.map = MAPS['blender']()
        window.color = self.map.sky
        self.player = Player(self.map.spawn_position, self.map.spawn_yaw)
        self.player.on_event = self.on_player_event
        self.map.player = self.player
        self.juice = Juice()
        self.postfx = PostFx(self.settings.effects)
        self.particles = Particles()
        self.blasts = Blasts()
        self.pixels = Pixels()
        self.popups = Popups()
        self.enemies = Enemies(self)
        self.projectiles = self.enemies.markers     # what the katana may send back
        self.arsenal = Arsenal(self)
        self.arsenal.equip()
        self.katana = Katana(self)
        self.player.parry = self.katana.try_parry
        self.player.guard = self.enemies.guard
        self.pickups = Pickups(self)
        self.clouds = Clouds(self)
        self.hud = Hud(self)
        self.heart = RunawayHeart(self)
        self.beacon = Beacon(self)
        self.director = Director(self)
        self.shop = Shop(self)
        self.tally = Tally(self)
        # the music fades on under the menus, when this entity's update is all that runs
        self.ticker = Entity(ignore_paused=True)
        self.ticker.update = self.tick_music
        self.apply_settings()

    def apply_settings(self):
        """Push what was picked on the menu into the sound, the controls, the weapons and the HUD."""
        settings = self.settings
        self.sfx.volume = settings.volume
        self.postfx.switch(settings.effects)
        controls.apply(settings.keys, settings.sensitivity)
        self.hud.show_controls()
        self.arsenal.repaint(settings.hue)
        self.katana.repaint(settings.hue)
        self.player.legs.repaint(settings.hue)
        self.hud.set_player(settings.name, settings.hue)

    def load_map(self, name):
        """Swap the arena for another, and stand the player where that one starts."""
        if self.map.name == name:
            return
        destroy(self.map)
        self.map = MAPS[name]()
        self.map.player = self.player
        window.color = self.map.sky
        self.player.spawn_position = Vec3(*self.map.spawn_position)
        self.player.spawn_yaw = self.map.spawn_yaw
        self.player.respawn()

    def pause(self, paused):
        """Freeze the match under the menu, or let it run again."""
        application.paused = paused
        mouse.locked = not paused
        self.hud.enabled = not paused
        self.postfx.set('pause', 1.0 if paused else 0.0)
        if paused:
            self.progress.save()            # chips picked up since the last round ended
            application.time_scale = 1      # a hitstop can't end itself while frozen
            self.sfx.set_wind(0)
        self.sfx.set_hum(0 if paused else self.was_overdrive)

    def begin(self):
        """The title screen was closed: start the level, unless one is already under way. One that
        is under way starts over if another was picked, or the save deleted, on the menu."""
        director = self.director
        if director.auto and (not director.running or (director.changed and director.state != 'won')):
            director.start()

    def erase(self):
        """Delete the save: chips, keys, levels, branches and what was bought for them."""
        self.kills = 0
        self.progress.wipe()
        mods.rebuild()
        self.refresh_weapons()
        self.director.changed = True

    def open_shop(self):
        """A level was cleared: freeze the arena under its tally, then the upgrade shop."""
        self.pause(True)
        chain, director = self.chain, self.director
        self.tally.open({'level': director.level, 'name': director.plan.name, 'kills': chain.kills,
                         'base': chain.base_points, 'style': chain.style_points, 'best': chain.best,
                         'time': director.level_time})

    def tally_closed(self, score):
        self.shop.open(after_level=True)

    def tick_music(self):
        playing = self.director.running or self.tally.is_open or self.chain.tier > 0
        self.sfx.set_music(self.chain.tier, playing=playing, duck=T.MUSIC_DUCK if application.paused else 1.0)
        self.sfx.update_music(time.dt_unscaled)

    def reset_chain(self):
        """A level starting, or starting again: no chain, no score."""
        self.chain.reset()
        self.hud.score.reset()
        self.postfx.edge((1, 1, 1), 0)

    def shop_closed(self, after_level):
        if after_level and self.menu is not None and self.progress.cleared == len(LEVELS) \
                and self.director.pick is None:
            # the last level, for the first time: from now on the menu offers any level, or endless
            self.menu.open('YOU BEAT THE GAME   PICK A MODE')
        elif after_level:
            self.pause(False)
            self.begin()
        elif self.menu is not None:
            self.menu.open()

    def refresh_weapons(self):
        """Something was bought: hand over the new branch, if there is one."""
        if self.arsenal.equip():
            self.hud.refresh_weapons()

    def input(self, key):
        # with a menu, ESC opens it and the menu handles the key itself
        if key == 'escape' and self.menu is None:
            mouse.locked = not mouse.locked

    def update(self):
        self.chip_timer -= time.dt
        lost = self.chain.update(time.dt)
        if lost:
            self.chain_lost(lost)
        if self.chip_timer <= 0:
            self.chip_streak = 0
        speed = self.player.speed
        self.sfx.set_wind(clamp((speed - T.WIND_START) / (T.WIND_FULL - T.WIND_START), 0, 1))
        overdrive = self.player.rush.overdrive
        if overdrive != self.was_overdrive:
            self.was_overdrive = overdrive
            self.sfx.play('overdrive' if overdrive else 'overdrive_end')
            self.sfx.set_hum(1 if overdrive else 0)
            if overdrive:
                self.juice.shake(0.5)
                self.postfx.pulse('flash', 0.35, 0.12)
            self.postfx.set('saturation', T.OVERDRIVE_SATURATION if overdrive else 1.0)
            self.postfx.set('aberration', T.OVERDRIVE_ABERRATION if overdrive else 0.0)
        fast = clamp((speed - T.RUN_SPEED) / (T.FOV_FULL_SPEED - T.RUN_SPEED), 0, 1)
        self.postfx.set('radial', T.SPEED_SMEAR * fast * (1.5 if overdrive else 1.0))

    # --- events ---

    def on_player_event(self, name, value):
        if name == 'land':
            if value > 6:
                self.sfx.play('land', volume=clamp(value / 25, 0.2, 1))
            if value > 16:
                self.juice.shake(clamp(value / 50, 0, 0.5))
            return
        sound, volume, pitch = MOVE_SOUNDS[name]
        self.sfx.play(sound, volume, pitch)
        if name == 'hurt':
            self.juice.shake(T.SHAKE_HURT)
            self.hud.hurt_flash(value)
            lost = self.chain.hurt()
            if lost:
                self.chain_lost(lost)
            elif self.chain.tier:
                self.chain_climbed(self.chain.tier, quiet=True)     # knocked down a step or two
        elif name == 'death':
            # dying costs the level: back to its first round, with everything earned kept
            self.kills = 0
            self.progress.save()
            self.director.on_death()

    def on_hit(self, enemy, amount, point, killed):
        tint = rush_colour(self.player.rush.fraction)
        self.rally(amount * T.RALLY_SHARE)
        self.popups.show(point, str(round(amount)), tint, size=0.9 + min(amount / 60, 1.2))
        self.particles.sparks(point, (0, 0.6, 0), enemy.colour, count=5, speed=7)

    def on_quickscope(self, point, killed):
        """A Longshot hit fired just as the scope came up."""
        self.popups.show(point + Vec3(0, 1.3, 0), 'QUICKSCOPE!', GOLD, size=1.7)
        self.particles.burst(point, GOLD, count=22, speed=10, life=0.5, white=0.5)
        self.sfx.play('quickscope')
        self.hud.quickscope()
        self.juice.hitstop(T.HITSTOP_QUICKSCOPE)
        if killed:
            self.juice.shake(0.45)

    def on_parry(self, point, projectile=False):
        """The katana caught something green. Each parry earns a drive charge."""
        self.player.drive = min(self.player.drive + 1, T.DRIVE_MAX)
        self.popups.show(point + Vec3(0, 1.3, 0), 'PARRY!', PARRY_GREEN, size=1.7)
        self.particles.burst(point, PARRY_GREEN, count=26, speed=11, life=0.5, white=0.5)
        self.sfx.play('parry')
        if projectile:
            self.sfx.play('reflect')
        self.hud.parry()
        self.juice.hitstop(T.HITSTOP_PARRY)
        self.juice.shake(T.SHAKE_PARRY)

    def drop(self, enemy):
        """What a special enemy leaves behind."""
        if enemy.boss is not None:
            self.pickups.drop(enemy.centre, chips=T.BOSS_CHIPS)
        elif enemy.special == 'glow':
            self.pickups.drop(enemy.centre, chips=T.GLOW_CHIPS)
        elif enemy.special == 'gold':
            self.pickups.drop(enemy.centre, chips=T.GOLD_CHIPS, tokens=1, ammo=T.AMMO_CRATES)

    def collect_chip(self):
        self.progress.chips += 1
        self.chip_streak += 1
        self.chip_timer = CHIP_STREAK
        self.sfx.play('chip', volume=0.6, pitch=1 + 0.06 * min(self.chip_streak, 12))
        self.hud.chip()

    def collect_token(self):
        """A golden enemy's token: a key that opens one weapon branch in the shop."""
        if mods.all_unlocked():
            self.progress.chips += T.SPARE_TOKEN_CHIPS
            self.hud.notice(f'EVERY BRANCH IS OPEN: +{T.SPARE_TOKEN_CHIPS} CHIPS')
        else:
            self.progress.tokens += 1
            self.hud.notice(f'BRANCH KEY x{self.progress.tokens}   SPEND IT IN THE SHOP')
        self.sfx.play('token')
        self.juice.shake(0.3)

    def collect_ammo(self):
        """A golden enemy's crate: ammunition for one weapon that is short of it."""
        weapon = self.arsenal.give_ammo()
        if weapon is None:
            self.progress.chips += T.SPARE_AMMO_CHIPS
        else:
            self.hud.ammo_gain(weapon)
        self.sfx.play('reload', volume=0.8, pitch=1.3)

    def on_convert(self, enemy):
        """A weapon turned this enemy into an ally. It still leaves what its kill would have."""
        self.drop(enemy)

    def rally(self, amount):
        """Damage dealt in Overdrive wins back health just lost: see Player.rally."""
        player = self.player
        if player.rush.overdrive and player.rally > 0:
            gained = player.win_back(amount)
            if gained > 0:
                self.hud.health.rallied(gained)

    def on_kill(self, enemy):
        self.kills += 1
        self.rally(T.RALLY_KILL)
        self.drop(enemy)
        centre = enemy.centre
        player, chain = self.player, self.chain
        points, styles, climbed = chain.kill(chain.worth(enemy), player.rush.damage_multiplier,
                                             airborne=not player.grounded, sliding=player.sliding)
        tier = chain.tier
        self.particles.burst(centre, enemy.colour, count=46)
        # each tier of the chain plays the kill a step further up the scale
        self.sfx.play('kill', pitch=2 ** (T.CHAIN_SCALE[min(tier, len(T.CHAIN_SCALE) - 1)] / 12) * uniform(0.99, 1.01))
        self.juice.hitstop(min(T.HITSTOP_KILL + tier * T.HITSTOP_KILL_TIER, T.HITSTOP_KILL_MAX))
        self.juice.shake(T.SHAKE_KILL + tier * T.SHAKE_KILL_TIER)
        self.postfx.pulse('aberration', 0.002 + 0.0004 * tier, 0.12)
        self.hud.score.kill(centre + Vec3(0, 0.6, 0), points, styles)
        if climbed:
            self.chain_climbed(tier)
        if self.player.rush.overdrive:
            self.explode(centre, T.OVERDRIVE_KILL_BLAST_RADIUS, T.OVERDRIVE_KILL_BLAST_DAMAGE, enemy.colour,
                         quiet=True)

    def chain_climbed(self, tier, quiet=False):
        """The chain went up a tier (or, `quiet`, was knocked down to this one): the badge slams,
        the edge of the screen glows a step brighter, and one more layer of music comes in."""
        if not quiet:
            self.sfx.play('tier', volume=0.7, pitch=1 + 0.04 * (tier - 1))
            self.hud.score.chain_up(tier)
        else:
            self.hud.score.chain_up(tier)
            self.hud.score.slam = 0.3
        self.postfx.edge(tier_colour(tier), min(T.CHAIN_EDGE * tier, T.CHAIN_EDGE_MAX))

    def chain_lost(self, tier):
        """The chain broke: it deflates, the badge shatters and the colour drains for a moment."""
        self.sfx.play('deflate', volume=0.4 + 0.06 * min(tier, 10))
        self.hud.score.chain_lost()
        self.postfx.pulse('saturation', 0.25, 0.4)
        self.postfx.edge((1, 1, 1), 0)

    def explode(self, position, radius, damage, colour, player_knock=0.0, quiet=False, self_damage=0.0, throw=None,
                lift=False, look=None):
        """Damage and push everything in a sphere. The player is only thrown, unless
        `self_damage` is given: then being inside the radius costs up to that much health.
        `throw` is how hard enemies are flung, if not as hard as usual. With `lift` the player is
        thrown up as well as away, nearly as hard at the edge as in the middle. `look` makes it a
        rocket's explosion of pixels (see fx/pixels.py) in place of a shock ring."""
        position = Vec3(*position)
        for distance, enemy in self.enemies.in_radius(position, radius):
            if not enemy.alive:     # already killed by a chain blast
                continue
            falloff = 1 - 0.6 * distance / radius
            away = enemy.centre - position
            away = away.normalized() if away.length() > 0.01 else Vec3(0, 1, 0)
            amount = damage * falloff * (1 if quiet else self.player.rush.damage_multiplier)
            flung = throw or (9 if quiet else 14)
            killed = self.enemies.damage(enemy, amount, (away.x * flung, max(7, flung * 0.5), away.z * flung))
            self.on_hit(enemy, amount, enemy.centre, killed)

        self.particles.burst(position, colour, count=24 if quiet else 60, speed=radius * 3.2, life=0.7,
                             white=0.5)
        to_player = self.player.centre - position
        distance = to_player.length()
        if player_knock and 0.01 < distance < radius * 1.3:
            reach = distance / (radius * 1.3)
            if lift:
                way = to_player / distance
                way.y = max(way.y, 0.0) + T.IMPULSE_LIFT
                way = way.normalized()
                if way.y < T.IMPULSE_LIFT_MIN:
                    way = Vec3(way.x, 0, way.z).normalized() * (1 - T.IMPULSE_LIFT_MIN ** 2) ** 0.5 \
                        + Vec3(0, T.IMPULSE_LIFT_MIN, 0)
                self.player.add_impulse(way * player_knock * (1 - 0.5 * reach * reach))
            else:
                self.player.add_impulse(to_player / distance * player_knock * (1 - reach))
        if self_damage and distance < radius:
            self.player.take_damage(self_damage * (1 - 0.6 * distance / radius))
        self.beacon.blasted(position, radius)
        if look:
            self.pixels.show(position, radius, look)
        if not quiet:
            # shock ring, a second ring of dark smoke, and a white screen when it goes off close by
            if not look:
                self.blasts.show(position, radius, colour)
                self.particles.burst(position, (0.3, 0.3, 0.36), count=34, speed=radius * 1.6, size=0.17, life=1.0,
                                     up=3, white=0)
            if distance < radius * 2.5:
                self.hud.blast()
            self.sfx.play('explode', volume=clamp(1.3 - distance / 50, 0.3, 1), pitch=uniform(0.9, 1.1))
            self.juice.hitstop(T.HITSTOP_BLAST if distance < radius * 3 else 0)
            self.juice.shake(T.SHAKE_BLAST * clamp(1.4 - distance / 30, 0, 1))


def build(mute=False, menu=False, settings=None, level=None, **kwargs):
    """`level` plays that level, over and over, whatever the save says. Chips and keys picked up
    there are kept, but it does not count as cleared."""
    app = Ursina(title='RUSH', development_mode=False, **kwargs)
    application.asset_folder = Path(__file__).resolve().parent
    # Ursina's default shader recomputes fog inputs for every entity every frame; ours is unlit
    shaders.install()
    if getattr(window, 'fps_counter', None):
        window.fps_counter.enabled = True
    if getattr(window, 'exit_button', None):
        window.exit_button.enabled = False
    app.session = Session(mute, settings)
    if level:
        app.session.director.forced = (level - 1) % len(LEVELS)
    if menu:
        app.session.menu = Menu(app.session)
        app.session.menu.open()
    return app


if __name__ == '__main__':
    # `py main.py --level 2` plays level 2
    start = int(sys.argv[sys.argv.index('--level') + 1]) if '--level' in sys.argv else None
    app = build(menu=True, borderless=False, level=start)
    app.run()
