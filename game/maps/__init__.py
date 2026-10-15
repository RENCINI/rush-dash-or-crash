"""The arenas, by the name a level asks for them by (data/levels.py)."""
from game.maps.blender import Blender
from game.maps.cave import Cave
from game.maps.jungle import Jungle

MAPS = {'blender': Blender, 'jungle': Jungle, 'cave': Cave}
