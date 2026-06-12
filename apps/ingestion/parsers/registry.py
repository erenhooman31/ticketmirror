from .getyourguide import GetYourGuideParser
from .klook import KlookParser
from .sputnik8 import Sputnik8Parser
from .tiqets import TiqetsParser
from .tripster import TripsterParser
from .viator import ViatorParser

_registry = {}


def register_parser(parser_class) -> None:
    _registry[parser_class.provider_code] = parser_class


def get_parser(provider_code: str):
    parser_class = _registry.get(provider_code)
    if parser_class is None:
        return None
    return parser_class()


for parser in (
    GetYourGuideParser,
    KlookParser,
    Sputnik8Parser,
    TiqetsParser,
    TripsterParser,
    ViatorParser,
):
    register_parser(parser)
