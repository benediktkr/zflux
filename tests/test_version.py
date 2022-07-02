import configparser

from zflux import __version__

def test_zflux_version():
    pyproject = configparser.ConfigParser()
    pyproject.read("pyproject.toml")
    assert __version__ == pyproject['tool.poetry']['version'].strip('"')
