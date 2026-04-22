import configparser
from pathlib import Path

from openai import OpenAI

_config = configparser.ConfigParser()
_config.read(Path(__file__).parent / "config.ini")

MODEL = _config["model"]["name"]
DEFAULT_TEMPERATURE = _config["model"].getfloat("default_temperature")

client = OpenAI(
    api_key=_config["api"]["api_key"],
    base_url=_config["api"]["base_url"],
)
