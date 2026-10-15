"""Each weapon's numbers and the two branches it can be turned into, each with a skill tree.

A branch replaces some of its weapon's numbers and adds its own. Its tree is eight nodes: most
move one number a little for each level bought, and two are perks, which switch on something new
(the code for each is found by searching for its id). game/mods.py works out the totals.
"""
from collections import namedtuple

from data import tuning as T

# id: what is saved    effects: {number: added per level}    requires: ids that need a level first
# costs: chips for each level    at: (column, row) on the shop's board    show: how the number is printed
Node = namedtuple('Node', 'id label blurb effects requires costs at show')
Branch = namedtuple('Branch', 'id name blurb base nodes')

STAT_COSTS = (10, 15, 22)
LINK_COSTS = (18, 26)
PERK_COSTS = (60,)
# where the eight nodes sit and what each needs: a root, two paths of two that each end in a perk,
# and a link between the paths that needs the first node of both
SHAPE = (((0, 0), ()), ((1, 1), (0,)), ((2, 1), (1,)), ((3, 1), (2,)),
         ((1, -1), (0,)), ((2, -1), (4,)), ((3, -1), (5,)), ((2, 0), (1, 4)))
PERKS = (3, 6)
LINK = 7


def tree(*specs):
    """Eight nodes in the order of SHAPE. A number's is (id, label, number, step, show); a perk's
    is (id, label, what it does)."""
    nodes = []
    for i, spec in enumerate(specs):
        at, needs = SHAPE[i]
        requires = tuple(specs[n][0] for n in needs)
        if i in PERKS:
            name, label, blurb = spec
            nodes.append(Node(name, label, blurb, {name: 1}, requires, PERK_COSTS, at, ''))
        else:
            name, label, number, step, show = spec
            nodes.append(Node(name, label, '', {number: step}, requires, LINK_COSTS if i == LINK else STAT_COSTS,
                              at, show))
    return tuple(nodes)


def ammo(weapon):
    mag, reserve, reload = T.AMMO[weapon]
    return {'mag': mag, 'reserve': reserve, 'reload': reload}


BASE = {
    'POPPER': {'damage': T.POPPER_DAMAGE, 'interval': T.POPPER_INTERVAL, 'range': T.POPPER_RANGE, **ammo('POPPER')},
    'SCATTER': {'damage': T.SCATTER_DAMAGE, 'interval': T.SCATTER_INTERVAL, 'pellets': T.SCATTER_PELLETS,
                'spread': T.SCATTER_SPREAD, 'range': T.SCATTER_RANGE, 'recoil': T.SCATTER_RECOIL, **ammo('SCATTER')},
    'BOOMER': {'damage': T.ROCKET_DAMAGE, 'interval': T.ROCKET_INTERVAL, 'radius': T.ROCKET_RADIUS,
               'speed': T.ROCKET_SPEED, 'recoil': T.ROCKET_RECOIL, 'self_damage': T.ROCKET_SELF_DAMAGE, 'size': 1.0,
               **ammo('BOOMER')},
    'BUZZER': {'damage': T.BUZZER_DAMAGE, 'interval': T.BUZZER_INTERVAL, 'spread': T.BUZZER_SPREAD,
               'range': T.BUZZER_RANGE, **ammo('BUZZER')},
    'LONGSHOT': {'damage': T.LONGSHOT_DAMAGE, 'interval': T.LONGSHOT_INTERVAL, 'range': T.LONGSHOT_RANGE,
                 'quick_bonus': T.LONGSHOT_QUICK_BONUS, 'quick_window': T.LONGSHOT_QUICK_WINDOW,
                 'quick_refund': T.LONGSHOT_QUICK_KILL_REFUND, 'rechamber': T.LONGSHOT_RECHAMBER,
                 'quick_interval': None,        # None: a quickscope reloads no faster than any other shot
                 **ammo('LONGSHOT')},
}

TREES = {
    'SCATTER': (
        Branch('impulse', 'IMPULSE', 'A GRENADE LAUNCHER. ITS BLASTS HURL ENEMIES\nAWAY AND THROW YOU WITHOUT HURTING YOU.',
               {'damage': 45, 'interval': 0.55, 'radius': 5.0, 'knock': 24.0, 'self_knock': 32.0, 'speed': 38.0,
                'size': 0.9, 'mag': 4, 'reserve': 28, 'reload': 1.6},
               tree(('charge', 'DAMAGE', 'damage', 6, '{:.0f}'),
                    ('wave', 'BLAST', 'radius', 0.5, '{:.1f}m'),
                    ('shove', 'THROW', 'knock', 3.0, '{:.0f}'),
                    ('aftershock', 'AFTERSHOCK', 'EVERY BLAST GOES OFF\nA SECOND TIME.'),
                    ('breech', 'FIRE RATE', 'interval', -0.05, '{:.2f}s'),
                    ('springs', 'YOUR OWN LIFT', 'self_knock', 3.0, '{:.0f}'),
                    ('concuss', 'CONCUSS', 'WHATEVER A BLAST THROWS\nIS STUNNED FOR A SECOND.'),
                    ('drum', 'GRENADES LOADED', 'mag', 1, '{:.0f}'))),
        Branch('ice', 'ICE', 'A DOUBLE BARREL OF FROST.\nWHATEVER IT HITS IS SLOWED.',
               {'damage': 8, 'chill': 0.45, 'chill_time': 2.5},
               tree(('shard', 'PELLET DAMAGE', 'damage', 1, '{:.0f}'),
                    ('frost', 'SLOW', 'chill', 0.08, '{:.0%}'),
                    ('winter', 'SLOW LASTS', 'chill_time', 0.5, '{:.1f}s'),
                    ('deep_freeze', 'DEEP FREEZE', 'A SLOWED ENEMY HIT AGAIN\nFREEZES SOLID FOR A SECOND.'),
                    ('hail', 'PELLETS', 'pellets', 1, '{:.0f}'),
                    ('reach', 'RANGE', 'range', 8.0, '{:.0f}m'),
                    ('shatter', 'SHATTER', 'A SLOWED ENEMY THAT DIES BURSTS\nINTO ICE THAT SLOWS THE REST.'),
                    ('lever', 'RELOAD', 'reload', -0.1, '{:.1f}s'))),
    ),
    'POPPER': (
        Branch('flame', 'FLAMETHROWER', 'HOLD TO SPRAY A CONE OF FIRE.\nWHATEVER IT TOUCHES KEEPS BURNING.',
               {'damage': 10, 'interval': 0.1, 'range': 12.0, 'cone': 14.0, 'burn': 8.0, 'burn_time': 3.0,
                'mag': 80, 'reserve': 480, 'reload': 1.4},
               tree(('heat', 'FLAME DAMAGE', 'damage', 2, '{:.0f}'),
                    ('fuel', 'BURN PER SECOND', 'burn', 2.0, '{:.0f}'),
                    ('tar', 'BURN TIME', 'burn_time', 0.5, '{:.1f}s'),
                    ('wildfire', 'WILDFIRE', 'FIRE JUMPS FROM A BURNING ENEMY\nTO THE ONES STANDING NEAR IT.'),
                    ('hose', 'REACH', 'range', 1.5, '{:.1f}m'),
                    ('nozzle', 'CONE WIDTH', 'cone', 2.0, '{:.0f} deg'),
                    ('combust', 'COMBUST', 'AN ENEMY THAT DIES\nBURNING BLOWS UP.'),
                    ('pressure', 'SPRAY RATE', 'interval', -0.01, '{:.2f}s'))),
        Branch('taser', 'TASER', 'EACH SHOT ARCS ON TO THE ENEMIES\nNEAREST THE ONE IT HIT, AND STUNS.',
               {'damage': 16, 'interval': 0.22, 'range': 60.0, 'arcs': 3, 'arc_reach': 8.0, 'arc_share': 0.7,
                'stun': 0.25, 'mag': 10, 'reload': 1.1},
               tree(('volts', 'SHOCK DAMAGE', 'damage', 3, '{:.0f}'),
                    ('arcs', 'ARCS', 'arcs', 1, '{:.0f}'),
                    ('span', 'ARC REACH', 'arc_reach', 1.5, '{:.1f}m'),
                    ('fork', 'FORK', 'EVERY ARC SPLITS AND\nSTRIKES A SECOND ENEMY.'),
                    ('stun', 'STUN', 'stun', 0.1, '{:.2f}s'),
                    ('carry', 'ARC DAMAGE', 'arc_share', 0.08, '{:.0%}'),
                    ('overload', 'OVERLOAD', 'STUNNED ENEMIES TAKE 30% MORE\nDAMAGE FROM EVERYTHING.'),
                    ('capacitor', 'FIRE RATE', 'interval', -0.02, '{:.2f}s'))),
    ),
    'LONGSHOT': (
        Branch('dragon', 'DRAGON', 'HUGE DAMAGE, SLOW TO RECHARGE.\nIN OVERDRIVE ITS HITS BURST AND IT RELOADS FASTER.',
               {'damage': 300, 'interval': 1.8, 'od_bonus': 1.5, 'od_radius': 4.0, 'od_blast': 60, 'od_refund': 0.4,
                'mag': 3, 'reserve': 15, 'reload': 2.0},
               tree(('fang', 'DAMAGE', 'damage', 30, '{:.0f}'),
                    ('fury', 'OVERDRIVE DAMAGE', 'od_bonus', 0.1, 'x{:.1f}'),
                    ('breath', 'OVERDRIVE BLAST', 'od_radius', 0.6, '{:.1f}m'),
                    ('always_lit', 'ALWAYS LIT', 'ITS HITS BURST OUTSIDE\nOVERDRIVE TOO, AT HALF SIZE.'),
                    ('lungs', 'RECHARGE', 'interval', -0.1, '{:.1f}s'),
                    ('second_wind', 'OVERDRIVE RELOAD', 'od_refund', 0.06, '-{:.0%}'),
                    ('ember', 'EMBER', 'WHATEVER IT HITS\nIS LEFT BURNING.'),
                    ('hoard', 'BLAST DAMAGE', 'od_blast', 15, '{:.0f}'))),
        Branch('semi', 'SEMI-AUTO', 'SLOW TO COCK FROM THE HIP. QUICKSCOPES HIT\nTWICE AS HARD AND FIRE ALMOST AUTOMATICALLY.',
               {'damage': 90, 'interval': 0.8, 'quick_interval': 0.16, 'quick_bonus': 2.0, 'quick_window': 0.45,
                'quick_refund': 0.0, 'rechamber': 0.3, 'mag': 8, 'reserve': 48, 'reload': 1.4},
               tree(('load', 'DAMAGE', 'damage', 8, '{:.0f}'),
                    ('focus', 'QUICKSCOPE DAMAGE', 'quick_bonus', 0.15, 'x{:.2f}'),
                    ('patience', 'QUICKSCOPE WINDOW', 'quick_window', 0.05, '{:.2f}s'),
                    ('chain', 'CHAIN', 'EACH QUICKSCOPE HIT IN A ROW\nHITS 15% HARDER, UP TO FIVE.'),
                    ('action', 'COCKING TIME', 'interval', -0.06, '{:.2f}s'),
                    ('trigger', 'QUICKSCOPE CYCLE', 'quick_interval', -0.015, '{:.3f}s'),
                    ('adrenaline', 'ADRENALINE', 'A QUICKSCOPE KILL\nFILLS A QUARTER OF YOUR RUSH.'),
                    ('glass', 'SCOPE RECOVERY', 'rechamber', -0.04, '{:.2f}s'))),
    ),
    'BOOMER': (
        Branch('tiger', 'TIGER', 'A BIG ROCKET AND A BIG BLAST.\nIT HURTS YOU TOO IF YOU STAND IN IT.',
               {'damage': 130, 'interval': 1.2, 'radius': 11.0, 'speed': 55.0, 'self_damage': 30, 'size': 2.2,
                'reserve': 10},
               tree(('claws', 'DAMAGE', 'damage', 12, '{:.0f}'),
                    ('roar', 'BLAST', 'radius', 0.5, '{:.1f}m'),
                    ('pounce', 'ROCKET SPEED', 'speed', 5.0, '{:.0f}m/s'),
                    ('cluster', 'CLUSTER', 'THREE SMALLER BLASTS GO OFF\nROUND THE BIG ONE.'),
                    ('breech', 'RELOAD', 'interval', -0.06, '{:.2f}s'),
                    ('padding', 'DAMAGE TO YOU', 'self_damage', -5, '{:.0f}'),
                    ('blast_suit', 'BLAST SUIT', 'YOUR OWN BLASTS NO LONGER HURT,\nAND THROW YOU HALF AS FAR AGAIN.'),
                    ('payload', 'WARHEAD', 'damage', 10, '{:.0f}'))),
        Branch('poison', 'POISON', 'A SMALL ROCKET THAT STINGS WHAT IT HITS AND LEAVES\nA WIDE CLOUD. IT NEVER HURTS YOU.',
               {'damage': 60, 'radius': 4.5, 'self_damage': 0, 'size': 0.7, 'cloud': 18.0, 'cloud_radius': 10.0,
                'cloud_time': 6.0, 'reserve': 12},
               tree(('venom', 'CLOUD PER SECOND', 'cloud', 3.0, '{:.0f}'),
                    ('bloom', 'CLOUD SIZE', 'cloud_radius', 0.8, '{:.1f}m'),
                    ('linger', 'CLOUD TIME', 'cloud_time', 0.8, '{:.1f}s'),
                    ('plague', 'PLAGUE', 'A POISONED ENEMY THAT DIES\nLEAVES A CLOUD OF ITS OWN.'),
                    ('pump', 'RELOAD', 'interval', -0.05, '{:.2f}s'),
                    ('sting', 'IMPACT DAMAGE', 'damage', 10, '{:.0f}'),
                    ('corrode', 'CORRODE', 'POISONED ENEMIES TAKE 25% MORE\nDAMAGE FROM EVERYTHING.'),
                    ('jet', 'ROCKET SPEED', 'speed', 6.0, '{:.0f}m/s'))),
    ),
    'BUZZER': (
        Branch('dark', 'DARKNESS', 'FASTER. A BULLET MAY STEAL HEALTH, OR TURN\nAN ENEMY INTO A FIGHTER ON YOUR SIDE.',
               {'damage': 8, 'interval': 0.045, 'steal_chance': 0.02, 'steal': 10, 'convert_chance': 0.002,
                'ally_time': 30.0, 'ally_damage': T.ALLY_DAMAGE, 'mag': 50, 'reserve': 400},
               tree(('bite', 'DAMAGE', 'damage', 1, '{:.0f}'),
                    ('thirst', 'STEAL CHANCE', 'steal_chance', 0.006, '{:.1%}'),
                    ('gulp', 'HEALTH STOLEN', 'steal', 2, '{:.0f}'),
                    ('feast', 'FEAST', 'EVERY KILL WITH IT\nGIVES YOU 3 HEALTH.'),
                    ('call', 'FIGHTER CHANCE', 'convert_chance', 0.001, '{:.2%}'),
                    ('oath', 'FIGHTER STAYS', 'ally_time', 5.0, '{:.0f}s'),
                    ('legion', 'LEGION', 'A FIGHTER BLOWS UP\nWHEN ITS TIME IS UP.'),
                    ('fists', 'FIGHTER PUNCH', 'ally_damage', 8, '{:.0f}'))),
        Branch('light', 'LIGHT', 'SLOWER, HARDER HITS. A BULLET MAY TURN\nAN ENEMY INTO A HEALER THAT FOLLOWS YOU.',
               {'damage': 18, 'interval': 0.1, 'convert_chance': 0.005, 'heal': 4.0, 'ally_time': 30.0,
                'heal_radius': T.ALLY_HEAL_RADIUS, 'mag': 30, 'reserve': 240},
               tree(('ray', 'DAMAGE', 'damage', 2, '{:.0f}'),
                    ('grace', 'HEALER CHANCE', 'convert_chance', 0.0015, '{:.2%}'),
                    ('vigil', 'HEALER STAYS', 'ally_time', 4.0, '{:.0f}s'),
                    ('blessing', 'BLESSING', 'A HEALER GIVES YOU 25 HEALTH\nAS IT LEAVES.'),
                    ('balm', 'HEALING PER SECOND', 'heal', 1.0, '{:.0f}'),
                    ('halo', 'HEALING REACH', 'heal_radius', 1.5, '{:.1f}m'),
                    ('aegis', 'AEGIS', 'WITH A HEALER NEAR YOU,\nHITS HURT 40% LESS.'),
                    ('pulse', 'FIRE RATE', 'interval', -0.008, '{:.3f}s'))),
    ),
}
