"""The levels, played in order and then round again, harder each lap. Each is a map and a list of
rounds. Add a level by adding a `Level`; its map is one of game/maps, its enemies of game/foes."""
from collections import namedtuple

# name: shown beside the level's number     map: a key of game.maps.MAPS
# boss: the miniboss the beacon calls after round 3, or None
Level = namedtuple('Level', 'name map rounds boss', defaults=(None,))

# kind: a key of game.foes; it comes giant, and speed, hp and power multiply what a giant of
# its kind would have (see Enemy.make_boss)
Boss = namedtuple('Boss', 'kind name speed hp power')

# enemies: how many the round sends in all        alive: the most in the arena at once
# interval: seconds between spawns                mix: kind -> share of the round's enemies
# green: share that can be parried                glowing, golden: how many of them are special
# hp: times T.ASTRO_HP                            snipers, elites: sent in besides
Round = namedtuple('Round', 'enemies alive interval mix green glowing golden hp snipers elites',
                   defaults=(0, 0))

BRAWLERS = {'brawler': 1.0}


def crew(throwers):
    return {'brawler': 1 - throwers, 'thrower': throwers}


def crocs(snappers, lobbers):
    return {'croc': 1 - snappers - lobbers, 'snapper': snappers, 'lobber': lobbers}


def cavers(monkeys, miners):
    return {'golem': 1 - monkeys - miners, 'monkey': monkeys, 'miner': miners}


LEVELS = [
    Level('THE SHIP', 'blender', boss=Boss('thrower', 'GIANT THROWER', 1.5, 6.0, 1.2), rounds=[      # brawlers only until round 3
        Round(enemies=10, alive=5, interval=0.9, mix=BRAWLERS, green=0.20, glowing=2, golden=0, hp=1.0),
        Round(enemies=14, alive=7, interval=0.8, mix=BRAWLERS, green=0.25, glowing=3, golden=0, hp=1.0),
        Round(enemies=18, alive=8, interval=0.7, mix=crew(0.25), green=0.30, glowing=3, golden=1, hp=1.1),
        Round(enemies=24, alive=10, interval=0.6, mix=crew(0.35), green=0.35, glowing=4, golden=1, hp=1.2),
        Round(enemies=30, alive=12, interval=0.5, mix=crew(0.40), green=0.40, glowing=5, golden=2, hp=1.3),
    ]),
    Level('THE JUNGLE', 'jungle', boss=Boss('lobber', 'GIANT CROCODILE', 1.2, 8.0, 1.2), rounds=[
        # crocodiles; the first sniper in round 2, an elite from round 4
        Round(enemies=12, alive=6, interval=0.9, mix=crocs(0.3, 0.0), green=0.25, glowing=2, golden=0, hp=1.0),
        Round(enemies=16, alive=7, interval=0.8, mix=crocs(0.4, 0.0), green=0.30, glowing=3, golden=1, hp=1.1,
              snipers=1),
        Round(enemies=20, alive=9, interval=0.7, mix=crocs(0.35, 0.15), green=0.30, glowing=3, golden=1, hp=1.2,
              snipers=1),
        Round(enemies=26, alive=11, interval=0.6, mix=crocs(0.35, 0.2), green=0.35, glowing=4, golden=1, hp=1.3,
              snipers=1, elites=1),
        Round(enemies=32, alive=13, interval=0.5, mix=crocs(0.4, 0.2), green=0.40, glowing=5, golden=2, hp=1.4,
              snipers=2, elites=1),
    ]),
    Level('THE CRYSTAL CAVE', 'cave', boss=Boss('miner', 'GIANT MINER', 1.3, 5.2, 1.3), rounds=[
        # golems, monkeys overhead and miners underfoot
        Round(enemies=14, alive=7, interval=0.9, mix=cavers(0.2, 0.2), green=0.25, glowing=2, golden=1, hp=1.1,
              snipers=1),
        Round(enemies=18, alive=8, interval=0.8, mix=cavers(0.25, 0.25), green=0.30, glowing=3, golden=1, hp=1.2,
              snipers=1),
        Round(enemies=22, alive=10, interval=0.7, mix=cavers(0.25, 0.3), green=0.35, glowing=3, golden=1, hp=1.3,
              snipers=2, elites=1),
        Round(enemies=28, alive=12, interval=0.6, mix=cavers(0.3, 0.3), green=0.35, glowing=4, golden=2, hp=1.4,
              snipers=2, elites=1),
        Round(enemies=34, alive=14, interval=0.5, mix=cavers(0.3, 0.35), green=0.40, glowing=5, golden=2, hp=1.5,
              snipers=3, elites=1),
    ]),
]
