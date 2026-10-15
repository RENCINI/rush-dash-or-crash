"""What the player has earned, kept in progress.json until they delete it: chips, keys, levels
cleared, and each weapon's branches and the nodes bought in their trees."""
import json
from pathlib import Path

from data import tuning as T


def counts(saved):
    """{name: {id: whole number}} out of whatever the file held."""
    out = {}
    if isinstance(saved, dict):
        for weapon, entries in saved.items():
            if isinstance(weapon, str) and isinstance(entries, dict):
                kept = {key: value for key, value in entries.items()
                        if isinstance(key, str) and isinstance(value, int) and not isinstance(value, bool) and value > 0}
                if kept:
                    out[weapon] = kept
    return out


class Progress:
    def __init__(self, path):
        self.path = Path(path)
        self.clear()
        self.load()

    def clear(self):
        """Nothing earned yet."""
        self.chips = 0
        self.tokens = 0         # keys from golden enemies: one opens a branch
        self.cleared = 0        # levels finished
        self.replay = None      # the level picked to play over again, counted from 0; None is endless
        self.unlocked = {}      # weapon -> [branch id, ...]
        self.branches = {}      # weapon -> the unlocked branch in the player's hands, if any
        self.nodes = {}         # 'WEAPON/branch' -> {node id: levels bought}

    def wipe(self):
        """The save was deleted: everything earned is gone, on disk too."""
        self.clear()
        self.save()

    def load(self):
        try:
            saved = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return
        if not isinstance(saved, dict):
            return
        for name in ('chips', 'tokens', 'cleared'):
            value = saved.get(name)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                setattr(self, name, value)
        replay = saved.get('replay')
        if isinstance(replay, int) and not isinstance(replay, bool) and replay >= 0:
            self.replay = replay
        branches = saved.get('branches')
        if isinstance(branches, dict):
            self.branches = {weapon: branch for weapon, branch in branches.items()
                             if isinstance(weapon, str) and isinstance(branch, str)}
        nodes = counts(saved.get('nodes'))
        unlocked = saved.get('unlocked')
        if not isinstance(unlocked, dict):
            # a save from before the trees: a branch was bought for good, and its upgrades were
            # levels of four numbers. The branch is kept and the levels are paid back in chips.
            self.unlocked = {weapon: [branch] for weapon, branch in self.branches.items()}
            for levels in nodes.values():
                self.chips += sum(sum(T.OLD_NODE_COSTS[:level]) for level in levels.values())
            return
        self.unlocked = {weapon: [b for b in owned if isinstance(b, str)] for weapon, owned in unlocked.items()
                         if isinstance(weapon, str) and isinstance(owned, list)}
        self.branches = {weapon: branch for weapon, branch in self.branches.items()
                         if branch in self.unlocked.get(weapon, ())}
        self.nodes = nodes

    def save(self):
        saved = {'chips': self.chips, 'tokens': self.tokens, 'cleared': self.cleared, 'replay': self.replay,
                 'unlocked': self.unlocked, 'branches': self.branches, 'nodes': self.nodes}
        try:
            self.path.write_text(json.dumps(saved, indent=2), encoding='utf-8')
        except OSError:
            pass    # a folder that can't be written to just means nothing is remembered
