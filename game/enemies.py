"""Everything alive in the arena that is not the player: the manager that spawns the enemies,
moves them, hurts them and flies what they throw. The species themselves are in game/foes."""
from math import ceil, cos, radians, sin, sqrt
from random import choice, uniform

from ursina import Entity, Vec3, time

from data import tuning as T
from game import mods
from game.foes import astronauts, cave, crocodiles, snipers
from game.foes.base import ALLY_HALOS, DEATH_TIME, FIRE, FROST, Shot, clone
from ui.hud import glow_texture

SHOT_POOL = 40
FOES = (astronauts, crocodiles, cave, snipers)


class Enemies(Entity):
    KINDS = {cls.kind: cls for module in FOES for cls in module.KINDS}
    SHOTS = {name: model for module in FOES for name, model in module.SHOTS.items()}

    def __init__(self, game):
        super().__init__()
        self.game = game
        self.pool = []
        self.alive = []
        self.allies = []            # converted enemies: on the player's side until their time is up
        self.suits = {}             # (kind, green, gold) -> that body's meshes, copied for each enemy
        self.halo_texture = glow_texture()
        self.shot_meshes = {}       # kind of shot -> its mesh, copied for each one
        self.shot_pool = []
        self.markers = []           # whatever is in the air; the game hands these out as its projectiles
        self.mix = None             # kind -> share of those alive, when a round says who comes
        self.status_timer = T.STATUS_TICK
        self.corpses = []           # killed this moment: seen white for two frames, then gone

    # --- spawning ---

    def spawn(self, kind=None, x=None, z=None, green=None, special=None, hp_scale=1.0, size=None):
        """Put an enemy in the arena. Anything left out is picked for you. `special` is
        'glow' or 'gold'; a golden one is never green."""
        if len(self.alive) >= T.ENEMY_CAP:
            return None
        if kind is None:
            kind = self.pick_kind()
        species = self.KINDS[kind]
        if not species.DROPS:
            special = None
        gold = special == 'gold'
        if green is None:
            green = uniform(0, 1) < T.GREEN_SHARE
        green = bool(green) and not gold and species.PARRY
        door = x is None and species.DOOR
        if door:
            x, z = self.pick_spawn_point()
        elif x is None:
            x = z = 0.0     # it finds its own place: see its `spawn`
        enemy = next((e for e in self.pool if not e.alive and e.ally is None and e.dead_time <= 0 and e.kind == kind
                      and e.green == green and e.gold == gold), None)
        if enemy is None:
            enemy = species(self.game, green, self.suit(kind, green, gold), gold)
            self.pool.append(enemy)
        enemy.spawn(x, z, special, hp_scale, size)
        self.alive.append(enemy)
        if not enemy.hidden:
            # it comes in in a puff of whatever the place is made of: steam, leaves or dust
            self.game.pixels.scatter((enemy.x, enemy.y + 0.5, enemy.z), self.game.map.DUST, count=18, speed=4,
                                     size=0.09, life=0.7, gravity=-0.5, up=1.5, spread=0.5)
        self.game.sfx.play('spawn', volume=0.35, pitch=uniform(0.9, 1.2))
        return enemy

    def spawn_boss(self, boss, x, z, hp_scale=1.0):
        """The level's miniboss, a giant of its kind, at (x, z): see Enemy.make_boss."""
        enemy = self.spawn(boss.kind, x, z, green=False, hp_scale=hp_scale, size=T.BOSS_SIZE)
        if enemy is None:
            return None
        enemy.make_boss(boss)
        enemy.x, enemy.z = x, z
        # it rises out of a column of light and gold
        for k in range(6):
            self.game.pixels.scatter((x, enemy.y + k * 1.4, z), 'gold' if k % 2 else 'hurt', count=14, speed=3,
                                     size=0.14, life=1.0, gravity=-3, up=4, spread=1.2)
        if hasattr(enemy, 'come_up'):
            enemy.come_up()         # a miner bursts out of the ground where the beacon was
        return enemy

    def pick_kind(self):
        """Whichever kind is furthest short of its share of those alive."""
        if self.mix is None:
            throwers = sum(1 for e in self.alive if e.kind == 'thrower')
            return 'thrower' if throwers < round(T.THROWER_SHARE * (len(self.alive) + 1)) else 'brawler'
        counts = {kind: 0 for kind in self.mix}
        for enemy in self.alive:
            if enemy.kind in counts:
                counts[enemy.kind] += 1
        total = sum(counts.values()) + 1
        return max(self.mix, key=lambda kind: self.mix[kind] * total - counts[kind])

    def suit(self, kind, green, gold=False):
        if (kind, green, gold) not in self.suits:
            self.suits[kind, green, gold] = self.KINDS[kind].models(green, gold)
        return self.suits[kind, green, gold]

    def shot_mesh(self, kind):
        if kind not in self.shot_meshes:
            self.shot_meshes[kind] = self.SHOTS[kind]()
        return self.shot_meshes[kind]

    def pick_spawn_point(self):
        """Just inside one of the map's entries, which opens: any that is not too near the player."""
        game = self.game
        player, arena = game.player, game.map
        away = [door for door in arena.entries
                if (door['spot'].x - player.x) ** 2 + (door['spot'].z - player.z) ** 2 > T.SPAWN_MIN_DISTANCE ** 2]
        door = choice(away or arena.entries)
        arena.open_entry(door)
        # not all on one spot, when several come through together
        a = radians(door['angle'])
        along = uniform(-1.2, 1.2)
        return door['spot'].x + cos(a) * along, door['spot'].z - sin(a) * along

    def throw(self, owner, position, velocity, ink, kind='marker', **how):
        """Launch something: a marker pen, unless `kind` says otherwise. `how` is Shot.launch's.
        Returns it, or None if too much is in the air already."""
        marker = next((m for m in self.shot_pool if not m.live and m.kind == kind), None)
        if marker is None:
            if len(self.markers) >= SHOT_POOL:
                return None
            marker = Shot(kind, clone(self.shot_mesh(kind)))
            self.shot_pool.append(marker)
        if owner.might != 1:
            how['damage'] = how.get('damage', T.MARKER_DAMAGE) * owner.might
        if owner.boss is not None:
            how['scale'] = how.get('scale', 1.0) * T.BOSS_SHOT_SIZE
        marker.launch(owner, position, velocity, ink, **how)
        self.markers.append(marker)
        self.game.sfx.play('throw', volume=0.5, pitch=uniform(0.9, 1.1))
        return marker

    def convert(self, enemy, role, seconds, **numbers):
        """Turn a living enemy into an ally: a 'fighter' that hunts the others, or a 'healer' that
        follows the player. Bullets and blasts no longer find it. Returns False if it is dead.
        `numbers` are Enemy.convert's: how fast it heals, how hard it punches."""
        if not enemy.alive or enemy.boss is not None:
            return False        # a miniboss can't be talked round
        self.game.on_convert(enemy)
        enemy.alive = False
        self.alive.remove(enemy)
        self.allies.append(enemy)
        enemy.convert(role, seconds, **numbers)
        return True

    def guard(self):
        """The share of a hit on the player that gets through: less beside a healer, with aegis."""
        if not mods.perk('BUZZER', 'aegis'):
            return 1.0
        player = self.game.player
        near = any(a.ally == 'healer' and (a.x - player.x) ** 2 + (a.z - player.z) ** 2 < a.heal_reach ** 2
                   for a in self.allies)
        return T.AEGIS_SHARE if near else 1.0

    def clear(self):
        """Empty the arena: enemies, allies and the pens in the air."""
        for enemy in self.alive + self.allies + self.corpses:
            enemy.alive = False
            enemy.ally = None
            enemy.dead_time = 0.0
            enemy.retire()
        self.alive.clear()
        self.allies.clear()
        self.corpses.clear()
        for marker in self.markers:
            marker.finish()
        self.markers.clear()

    def input(self, key):
        if key == T.KEY_SPAWN_MANY:
            while len(self.alive) < T.ENEMY_CAP:
                self.spawn()

    # --- frame ---

    def update(self):
        dt = min(time.dt, T.MAX_DT)
        if dt <= 0:
            return
        player, arena = self.game.player, self.game.map
        for enemy in list(self.alive):      # one may add to the list, or blow itself up
            if enemy.alive:
                enemy.update(dt, player, arena, self.alive)
        for ally in list(self.allies):
            self.update_ally(ally, dt, player, arena)
        self.status_timer -= dt
        if self.status_timer <= 0:
            self.status_timer += T.STATUS_TICK
            self.tick_status()
        for corpse in list(self.corpses):
            corpse.dead_time -= dt
            if corpse.dead_time <= 0:
                corpse.entity.enabled = False
                self.corpses.remove(corpse)
        for marker in list(self.markers):
            # a pen that kills the player restarts the level, which has already cleared the list
            if not marker.update(dt, self.game) and marker in self.markers:
                self.markers.remove(marker)

    def update_ally(self, ally, dt, player, arena):
        ally.ally_time -= dt
        if ally.ally_time <= 0:
            self.dismiss(ally)
            return
        left = ceil(ally.ally_time)
        if left != ally.tag_shown:
            ally.tag_shown = left
            ally.tag.text = f'{ally.ally.upper()}  {left}'
            ally.tag.origin = (0, 0)        # centred again on the new words
        target = player
        if ally.ally == 'fighter' and self.alive:
            target = min(self.alive, key=lambda e: (e.x - ally.x) ** 2 + (e.z - ally.z) ** 2)
        ally.update(dt, target, arena, self.alive)

    def dismiss(self, ally):
        """An ally's time is up: it goes, and says so."""
        game = self.game
        role, centre, tint = ally.ally, ally.centre, ALLY_HALOS[ally.ally]
        self.allies.remove(ally)
        ally.ally = None
        ally.retire()
        game.particles.burst(centre, tint, count=40, speed=9, life=0.7, white=0.4)
        game.hud.notice(f'YOUR {role.upper()} IS GONE')
        game.sfx.play('convert', volume=0.5, pitch=0.7)
        if role == 'fighter' and mods.perk('BUZZER', 'legion'):
            game.explode(centre, T.LEGION_RADIUS, T.LEGION_DAMAGE, tint, look='legion')
        elif role == 'healer' and mods.perk('BUZZER', 'blessing'):
            game.player.heal(T.BLESSING_HEAL)
            game.popups.show(centre + Vec3(0, 1.5, 0), f'+{T.BLESSING_HEAL} HP', tint, size=1.8)
            game.hud.heal_flash(T.BLESSING_HEAL)

    def tick_status(self):
        """Burn and poison deal their damage a couple of times a second."""
        game = self.game
        for enemy in list(self.alive):
            if not enemy.alive:     # caught in the blast of one that died earlier in this loop
                continue
            amount = 0.0
            for name in ('burn', 'poison'):
                if getattr(enemy, name + '_time') <= 0:
                    continue
                setattr(enemy, name + '_time', getattr(enemy, name + '_time') - T.STATUS_TICK)
                amount += getattr(enemy, name) * T.STATUS_TICK      # what it looks like is the enemy's own (Enemy.update)
            if enemy.burn_time > 0 and mods.perk('POPPER', 'wildfire'):
                for _, other in self.in_radius(enemy.centre, T.WILDFIRE_REACH):
                    if other.burn_time <= 0:
                        other.ignite(enemy.burn * T.WILDFIRE_SHARE, enemy.burn_time)
            if amount:
                killed = self.damage(enemy, amount, flinch=False)
                game.on_hit(enemy, amount, enemy.centre, killed)

    # --- being shot ---

    def ray_hits(self, origin, direction, max_distance):
        """Enemies a ray passes through, nearest first, as (distance, enemy)."""
        hits = []
        for enemy in self.alive:
            if enemy.hidden:
                continue
            radius = enemy.radius
            ox, oy, oz = enemy.x - origin[0], enemy.y + enemy.CENTRE * enemy.size - origin[1], enemy.z - origin[2]
            along = ox * direction[0] + oy * direction[1] + oz * direction[2]
            if along < 0 or along > max_distance + radius:
                continue
            off = ox * ox + oy * oy + oz * oz - along * along
            if off < radius * radius:
                entry = along - sqrt(radius * radius - off)
                if entry <= max_distance:
                    hits.append((max(entry, 0.0), enemy))
        hits.sort(key=lambda h: h[0])
        return hits

    def in_radius(self, position, radius):
        """(distance, enemy) for every enemy whose body reaches into the sphere."""
        found = []
        for enemy in self.alive:
            if enemy.hidden:
                continue
            d = (enemy.centre - position).length() - enemy.radius
            if d < radius:
                found.append((max(d, 0.0), enemy))
        return found

    def die(self, enemy):
        """Killed: the body is seen two frames more, white and swollen, while it bursts into pixels
        of what it is made of."""
        if not enemy.hidden:
            enemy.entity.enabled = True
            enemy.dead_time = DEATH_TIME
            enemy.paint()
            enemy.entity.setScale(enemy.entity.getScale() * 1.15)
            self.corpses.append(enemy)
        big = enemy.size * (2.4 if enemy.boss is not None else 1.0)
        main, accent = enemy.death_looks()
        at = enemy.centre
        pixels = self.game.pixels
        pixels.scatter(at, main, count=int(30 * big), speed=7 * big ** 0.5, size=0.085 * big ** 0.5, life=0.9,
                       gravity=16, up=4, spread=0.45 * big)
        pixels.scatter(at, accent, count=int(14 * big), speed=9 * big ** 0.5, size=0.08 * big ** 0.5, life=0.7,
                       gravity=12, up=5, spread=0.3 * big)
        if enemy.boss is not None:
            pixels.ring((enemy.x, enemy.y, enemy.z), 9.0, 'gold')
            pixels.show(at, 5.0, 'rocket', shape=False)

    def damage(self, enemy, amount, push=None, flinch=True):
        """Returns True if this killed it. `flinch=False` is for damage that keeps coming."""
        if not enemy.alive or enemy.hidden:
            return False
        if enemy.stun > 0 and mods.perk('POPPER', 'overload'):
            amount *= T.OVERLOAD_BONUS
        if enemy.poison_time > 0 and mods.perk('BOOMER', 'corrode'):
            amount *= T.CORRODE_BONUS
        enemy.hp -= amount
        enemy.flash = 0.07
        if flinch:
            enemy.squash = -0.25
        if push is not None:
            enemy.shove(push[0], push[1], push[2])
        if enemy.hp > 0:
            return False
        enemy.alive = False
        enemy.retire()
        self.alive.remove(enemy)
        self.die(enemy)
        game = self.game
        game.on_kill(enemy)
        centre = enemy.centre
        enemy.died()
        if enemy.burn_time > 0 and mods.perk('POPPER', 'combust'):
            game.explode(centre, T.COMBUST_RADIUS, T.COMBUST_DAMAGE, FIRE, quiet=True, look='dragon')
            game.sfx.play('explode', volume=0.5, pitch=1.4)
        if enemy.poison_time > 0 and mods.perk('BOOMER', 'plague'):
            game.clouds.add(centre, T.PLAGUE_RADIUS, enemy.poison, T.PLAGUE_TIME)
        if enemy.slow_time > 0 and mods.perk('SCATTER', 'shatter'):
            for _, other in self.in_radius(centre, T.SHATTER_RADIUS):
                other.chill(enemy.slow, enemy.slow_time)
            game.explode(centre, T.SHATTER_RADIUS, T.SHATTER_DAMAGE, FROST, quiet=True, look='frost')
            game.sfx.play('splat', volume=0.6, pitch=1.8)
        return True
