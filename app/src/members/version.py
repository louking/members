from os import environ
from re import fullmatch

__version__ = environ['APP_VER']    # from .env
__docversion__ = __version__ if fullmatch(r'\d+\.\d+\.\d+', __version__) else 'latest'