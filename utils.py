from typing import Any

colour_map = {
    'black': '30',
    'red': '31',
    'green': '32',
    'yellow': '33',
    'blue': '34',
    'purple': '35',
    'ultramarine': '36',
    'white': '37',
}

def print_colour(s: Any, colour: str='green', way: int=0, **kwargs):
    print(f'\033[{way};{colour_map[colour]};m{s}', **kwargs)