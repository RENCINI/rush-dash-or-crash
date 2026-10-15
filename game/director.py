"""Runs a level: one round after another, each sending in a set number of enemies.

The levels are in data/levels.py. Past the last one written there they come round again, with
more and tougher enemies each lap, so there is always a next level. Once every level has been
cleared the player may instead pick one to play over again (see ui/menus.py).

After round 3 a beacon offers the level's miniboss (see game/beacon.py): killing it gives health
back, the more the quicker. Once a round the runaway heart gets out (see game/heart.py).
"""
from random import sample, shuffle

from ursina import Entity, Vec3, time

from data import tuning as T
from data.levels import LEVELS


class Director(Entity):
    def __init__(self, game):
        super().__init__()
        self.game = game
        self.auto = True        # False keeps the level from starting by itself, for the tests
        self.forced = None      # `py main.py --level N`: that level, counted from 0, whatever the save says
        self.changed = False    # the level to play was changed under a running match
        self.state = 'idle'     # 'intro', 'fight', 'clear', 'boss_intro', 'boss' or 'won'
        self.round = 0          # counted from 0
        self.level_time = 0.0   # seconds played of this level, for its tally
        self.plan = LEVELS[0]
        self.rounds = self.plan.rounds
        self.queue = []         # what the round has still to send in: (kind, green, special)
        self.total = 0
        self.timer = 0.0
        self.spawn_timer = 0.0
        self.alive_cap = 0
        self.hp_scale = 1.0
        self.hearts = True      # False keeps the runaway heart in, for the tests
        self.beacons = True     # False never offers the miniboss, for the tests
        self.boss = None        # the miniboss being fought
        self.boss_time = 0.0
        self.boss_spot = Vec3(0, 0, 0)
        self.beacon_used = False    # the beacon is offered once each time a level is played
        self.heart_sent = True
        self.fight_time = 0.0

    @property
    def beaten(self):
        """Every level has been cleared at least once."""
        return self.game.progress.cleared >= len(LEVELS)

    @property
    def pick(self):
        """The level being played over again, counted from 0, or None on the way through them."""
        if self.forced is not None:
            return self.forced
        replay = self.game.progress.replay
        return replay if self.beaten and replay is not None and replay < len(LEVELS) else None

    @property
    def level(self):
        """The level being played, counted from 1."""
        pick = self.pick
        return self.game.progress.cleared + 1 if pick is None else pick + 1

    @property
    def lap(self):
        """How many times every level has been cleared. A picked level is as it was the first time."""
        return self.game.progress.cleared // len(LEVELS) if self.pick is None else 0

    @property
    def left(self):
        """Enemies between the player and the end of the round."""
        return len(self.queue) + len(self.game.enemies.alive)

    @property
    def running(self):
        return self.state != 'idle'

    # --- starting ---

    def start(self):
        """Begin the level the player has reached, from its first round."""
        game = self.game
        game.enemies.clear()
        game.pickups.clear()
        game.clouds.clear()
        game.heart.clear()
        game.beacon.clear()
        game.hud.health.reset()
        game.hud.boss_bar.hide()
        self.boss = None
        self.beacon_used = False
        game.arsenal.restock()
        game.reset_chain()
        self.level_time = 0.0
        self.changed = False
        self.plan = LEVELS[(self.level - 1) % len(LEVELS)]
        self.rounds = self.plan.rounds
        game.load_map(self.plan.map)
        self.round = 0
        self.begin_round()

    def begin_round(self):
        # every lap round the levels is a notch harder
        extra = self.lap
        plan = self.rounds[self.round]
        total = round(plan.enemies * (1 + T.REPLAY_ENEMIES * extra))
        self.alive_cap = min(plan.alive + T.REPLAY_ALIVE * extra, T.ENEMY_CAP)
        self.hp_scale = plan.hp * (1 + T.REPLAY_HP * extra)

        # shares are rounded to whole enemies; whoever comes first in the mix makes up the number
        first = next(iter(plan.mix))
        kinds = [kind for kind, share in plan.mix.items() if kind != first for _ in range(round(total * share))]
        kinds = kinds[:total] + [first] * (total - len(kinds))
        self.game.enemies.mix = plan.mix
        greens = [i < round(total * plan.green) for i in range(total)]
        shuffle(kinds)
        shuffle(greens)
        specials = [None] * total
        marked = sample(range(total), min(total, plan.glowing + plan.golden))
        for n, i in enumerate(marked):
            specials[i] = 'gold' if n < plan.golden else 'glow'
        self.queue = list(zip(kinds, greens, specials))
        # marksmen come besides; from the second lap every round after a level's first has one more
        snipers = plan.snipers + (T.REPLAY_SNIPERS * extra if self.round else 0)
        elites = plan.elites + (extra if self.round == len(self.rounds) - 1 else 0)
        if snipers or elites:
            self.queue += [('sniper', False, None)] * snipers + [('elite', False, None)] * elites
            shuffle(self.queue)
        self.total = len(self.queue)
        self.heart_sent = False     # the runaway heart gets out once a round
        self.game.chain.new_round()
        self.fight_time = 0.0

        self.state = 'intro'
        self.timer = T.ROUND_INTRO
        self.spawn_timer = 0.0
        self.game.hud.banner(f'ROUND {self.round + 1}', f'LEVEL {self.level}   {self.plan.name}')
        self.game.sfx.play('round_start')

    def call_boss(self, spot):
        """The beacon was shot: the miniboss comes out of where it stood."""
        if self.state != 'clear' or self.plan.boss is None:
            return
        self.boss_spot = Vec3(spot)
        self.state = 'boss_intro'
        self.timer = T.BOSS_INTRO
        self.game.hud.banner('MINIBOSS', self.plan.boss.name)
        self.game.sfx.play('roar')

    def boss_heal(self, seconds):
        """What killing the miniboss in `seconds` gives back."""
        (fast, most), (slow, least) = T.BOSS_HEAL
        t = min(max((seconds - fast) / (slow - fast), 0.0), 1.0)
        return round(most + (least - most) * t)

    def boss_down(self):
        game = self.game
        heal = self.boss_heal(self.boss_time)
        given = game.player.heal(heal)
        game.hud.heal_flash(given)
        game.hud.boss_bar.hide()
        game.hud.banner('MINIBOSS DOWN', f'{self.boss_time:.1f} s    +{heal} HP')
        game.sfx.play('round_clear')
        self.boss = None
        self.state = 'clear'
        self.timer = T.ROUND_BREATHER

    def on_death(self):
        """The player died: the same level again, from its first round. Nothing earned is lost."""
        if not self.running:
            return
        self.start()
        self.game.hud.banner('YOU DIED', f'LEVEL {self.level}   ROUND 1')

    # --- frame ---

    def update(self):
        if self.state == 'idle':
            return
        dt = min(time.dt, T.MAX_DT)
        game = self.game
        self.timer -= dt
        if self.state != 'won':
            self.level_time += dt
        if self.state == 'intro':
            if self.timer <= 0:
                self.state = 'fight'
        elif self.state == 'fight':
            self.fight_time += dt
            down = self.total - self.left
            if self.hearts and not self.heart_sent and self.total and (down >= self.total * T.HEART_AFTER
                                                       or self.fight_time >= T.HEART_LATEST):
                self.heart_sent = True
                if not game.heart.loose and not game.hud.health.busy:
                    game.heart.release()
            self.spawn_timer -= dt
            if self.queue and self.spawn_timer <= 0 and len(game.enemies.alive) < self.alive_cap:
                self.spawn_timer = self.rounds[self.round].interval
                kind, green, special = self.queue.pop()
                game.enemies.spawn(kind, green=green, special=special, hp_scale=self.hp_scale)
            if not self.queue and not game.enemies.alive:
                self.round_cleared()
        elif self.state == 'clear':
            if self.timer <= 0:
                if game.beacon.live:
                    game.beacon.sink()
                self.round += 1
                self.begin_round()
        elif self.state == 'boss_intro':
            if self.timer <= 0:
                self.boss = game.enemies.spawn_boss(self.plan.boss, self.boss_spot.x, self.boss_spot.z, self.hp_scale)
                self.boss_time = 0.0
                self.state = 'boss'
                game.hud.boss_bar.show(self.boss)
                game.juice.shake(0.6)
        elif self.state == 'boss':
            self.boss_time += dt
            if self.boss is None or not self.boss.alive:
                self.boss_down()
        elif self.state == 'won' and self.timer <= 0:
            self.state = 'idle'
            game.open_shop()

    def round_cleared(self):
        game = self.game
        game.pickups.vacuum()
        game.sfx.play('round_clear')
        if self.beacons and self.round + 1 == T.BEACON_AFTER and self.plan.boss is not None \
                and not self.beacon_used and self.round + 1 < len(self.rounds):
            # a chance at the miniboss, for health: shoot the beacon, or let it sink
            self.beacon_used = True
            self.state = 'clear'
            self.timer = T.BEACON_TIME
            game.beacon.raise_up()
            game.hud.banner('ROUND CLEAR', 'SHOOT THE BEACON: A MINIBOSS FOR HEALTH')
        elif self.round + 1 < len(self.rounds):
            self.state = 'clear'
            self.timer = T.ROUND_BREATHER
            game.hud.banner('ROUND CLEAR', f'ROUND {self.round + 2} NEXT')
        else:
            self.state = 'won'
            self.timer = T.LEVEL_WON_PAUSE
            game.hud.banner(f'LEVEL {self.level} CLEAR', 'TO THE UPGRADE SHOP')
            if self.pick is None:
                game.progress.cleared += 1
        game.progress.save()
