"""Register additional language catalogs here."""

from . import en, ru


DEFAULT_LANGUAGE = "ru"
CATALOGS = {"ru": ru, "en": en}
LANGUAGES = {code: catalog.NAME for code, catalog in CATALOGS.items()}
