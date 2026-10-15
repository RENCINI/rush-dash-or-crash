"""Works out each weapon's numbers from the branch in the player's hands and the nodes bought in
its tree, and spends keys and chips on them. The tables are in data/trees.py; what the player
owns is a data.progress.Progress.

Weapons read their numbers with `stat(weapon, key)` and ask for a perk with `perk(weapon, id)`.
Chances are rolled with `roll`, so a test can make them certain.
"""
from random import random

from data import tuning as T
from data.trees import BASE, TREES

progress = None
values = {weapon: dict(stats) for weapon, stats in BASE.items()}


def use(saved):
    """Read and spend from this Progress from now on."""
    global progress
    progress = saved
    rebuild()


def stat(weapon, key):
    return values[weapon][key]


def perk(weapon, name):
    """True if the branch in hand has this perk bought."""
    return values[weapon].get(name, 0) > 0


def roll(chance):
    return random() < chance


def find(weapon, branch_id):
    return next((b for b in TREES.get(weapon, ()) if b.id == branch_id), None)


def branch(weapon):
    """The branch in the player's hands for a weapon, or None."""
    return find(weapon, progress.branches.get(weapon)) if progress is not None else None


def unlocked(weapon, branch_id):
    return branch_id in progress.unlocked.get(weapon, ())


def all_unlocked():
    return all(unlocked(weapon, b.id) for weapon, branches in TREES.items() for b in branches)


def levels(weapon, branch_id):
    return progress.nodes.get(f'{weapon}/{branch_id}', {})


def numbers(weapon, of):
    """A weapon's numbers as branch `of` with the nodes bought for it, or plain if `of` is None."""
    stats = dict(BASE[weapon])
    if of is not None:
        stats.update(of.base)
        for node in of.nodes:
            level = node_level(weapon, of, node)
            for key, step in node.effects.items():
                stats[key] = stats.get(key, 0) + step * level
    stats['interval'] = max(stats['interval'], 0.03)
    return stats


def rebuild():
    """Work every number out again. Call after anything in the progress changes."""
    for weapon in BASE:
        values[weapon] = numbers(weapon, branch(weapon))


# --- the shop ---

def node_level(weapon, of, node):
    return min(levels(weapon, of.id).get(node.id, 0), len(node.costs))


def node_cost(weapon, of, node):
    """Chips for the node's next level, or None once it is full."""
    level = node_level(weapon, of, node)
    return node.costs[level] if level < len(node.costs) else None


def node_open(weapon, of, node):
    """A node can be bought once every node it hangs from has a level."""
    owned = levels(weapon, of.id)
    return all(owned.get(needed, 0) > 0 for needed in node.requires)


def unlock_branch(weapon, branch_id):
    """Open a branch for good: one key from a golden enemy, and chips. It goes straight into
    the player's hands."""
    if find(weapon, branch_id) is None or unlocked(weapon, branch_id):
        return False
    if progress.tokens < 1 or progress.chips < T.BRANCH_COST:
        return False
    progress.tokens -= 1
    progress.chips -= T.BRANCH_COST
    progress.unlocked.setdefault(weapon, []).append(branch_id)
    progress.branches[weapon] = branch_id
    progress.save()
    rebuild()
    return True


def equip_branch(weapon, branch_id):
    """Carry an unlocked branch, or the plain weapon if `branch_id` is None."""
    if branch_id is None:
        progress.branches.pop(weapon, None)
    elif unlocked(weapon, branch_id):
        progress.branches[weapon] = branch_id
    else:
        return False
    progress.save()
    rebuild()
    return True


def buy_node(weapon, branch_id, node_id):
    of = find(weapon, branch_id)
    if of is None or not unlocked(weapon, branch_id):
        return False
    node = next((n for n in of.nodes if n.id == node_id), None)
    if node is None or not node_open(weapon, of, node):
        return False
    cost = node_cost(weapon, of, node)
    if cost is None or progress.chips < cost:
        return False
    progress.chips -= cost
    owned = progress.nodes.setdefault(f'{weapon}/{branch_id}', {})
    owned[node.id] = node_level(weapon, of, node) + 1
    progress.save()
    rebuild()
    return True
