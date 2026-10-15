"""The Chain and the score: the numbers the Balatro-style feedback hangs on.

Each kill within CHAIN_WINDOW of the last climbs the chain a tier, up to CHAIN_TOP. Letting the
window lapse drops it to nothing; being hit takes CHAIN_HURT_DROP tiers off. A kill scores
(SCORE_KILL x the enemy's worth + style bonuses) x chain x the Rush damage multiplier.

This is only the arithmetic. `Session` in main.py turns what these methods return into sound,
pixels and HUD (see `Session.on_kill` and `Session.chain_lost` in main.py, and ui/score.py).
"""
from data import tuning as T


class Chain:
    def __init__(self):
        self.tier = 0           # 0 is no chain; the first kill makes it x1
        self.timer = 0.0        # time left to keep it going
        self.score = 0          # this level so far: its kill points and style points together
        self.base_points = 0    # what the kills themselves were worth, chained and rushed
        self.style_points = 0   # what the style bonuses added, chained and rushed
        self.kills = 0          # this level
        self.best = 0           # the highest tier reached this level
        self.round_score = 0
        self.round_kills = 0
        self.round_best = 0     # the highest tier reached this round
        self.multi = 0          # kills in the current MULTI_WINDOW, besides the first
        self.multi_timer = 0.0

    @property
    def fraction(self):
        """How much of the window is left, 0-1."""
        return max(0.0, self.timer / T.CHAIN_WINDOW) if self.tier else 0.0

    def worth(self, enemy):
        """What killing this enemy is worth before bonuses and multipliers."""
        if getattr(enemy, 'boss', None) is not None:
            return T.SCORE_KILL * T.SCORE_BOSS
        return T.SCORE_KILL * T.SCORE_SPECIAL.get(getattr(enemy, 'special', None), 1)

    def kill(self, worth, rush, airborne=False, sliding=False):
        """A kill worth `worth`, with the Rush multiplier at `rush`. Returns (points, styles, climbed):
        styles is a list of the bonus names earned, climbed is True when the tier went up."""
        before = self.tier
        self.tier = min(self.tier + 1, T.CHAIN_TOP)
        self.timer = T.CHAIN_WINDOW
        styles = []
        bonus = 0
        if airborne:
            styles.append('AIR')
            bonus += T.STYLE_AIR
        if sliding:
            styles.append('SLIDE')
            bonus += T.STYLE_SLIDE
        if self.multi_timer > 0:
            self.multi += 1
            styles.append(f'MULTI x{self.multi + 1}')
            bonus += T.STYLE_MULTI * self.multi
        else:
            self.multi = 0
        self.multi_timer = T.MULTI_WINDOW
        base = round(worth * self.tier * rush)
        extra = round(bonus * self.tier * rush)
        points = base + extra
        self.score += points
        self.base_points += base
        self.style_points += extra
        self.kills += 1
        self.best = max(self.best, self.tier)
        self.round_score += points
        self.round_kills += 1
        self.round_best = max(self.round_best, self.tier)
        return points, styles, self.tier > before

    def hurt(self):
        """The player was hit. Returns the tier that was lost if the chain broke, else 0."""
        if not self.tier:
            return 0
        lost = self.tier
        self.tier = max(0, self.tier - T.CHAIN_HURT_DROP)
        return lost if self.tier == 0 else 0

    def update(self, dt):
        """Returns the tier that was lost if the window ran out this frame, else 0."""
        self.multi_timer -= dt
        if not self.tier:
            return 0
        self.timer -= dt
        if self.timer > 0:
            return 0
        lost, self.tier = self.tier, 0
        return lost

    def new_round(self):
        self.round_score = self.round_kills = self.round_best = 0

    def reset(self):
        """A level starting over: nothing carried."""
        self.tier = 0
        self.timer = 0.0
        self.score = self.base_points = self.style_points = self.kills = self.best = 0
        self.multi = 0
        self.multi_timer = 0.0
        self.new_round()
