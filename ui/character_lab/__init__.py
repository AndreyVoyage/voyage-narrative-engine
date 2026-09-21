"""PySide6 desktop shell for the NARRATIVE Character Lab."""

from .app import create_character_lab_config, create_character_lab_service, main
from .main_window import CharacterLabMainWindow

__all__ = [
    "CharacterLabMainWindow",
    "create_character_lab_config",
    "create_character_lab_service",
    "main",
]
