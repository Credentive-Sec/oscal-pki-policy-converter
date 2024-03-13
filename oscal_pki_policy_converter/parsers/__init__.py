from typing import Any

from .base_parser import AbstractParser
from .simple_oscal_parser import SimpleOscalParser

def choose_parser(parser_arg: str) -> AbstractParser:
    if parser_arg == "simple":
        return SimpleOscalParser()
    else:
        return AbstractParser()

