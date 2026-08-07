"""Vocabulaire canonique de maturité d'un projet.

Le même enum est utilisé par le profil porteur et par le projet. Les anciennes
valeurs de l'API restent acceptées pendant la migration, mais ne sont plus émises.
"""

from __future__ import annotations

from enum import Enum


class ProjectStage(str, Enum):
    IDEA = "idea"
    VALIDATION = "validation"
    MVP = "mvp"
    TRACTION = "traction"
    SCALE = "scale"

    @classmethod
    def _missing_(cls, value: object) -> ProjectStage | None:
        if not isinstance(value, str):
            return None
        legacy = {
            "prototype": cls.MVP,
            "first_customers": cls.TRACTION,
            "growing": cls.SCALE,
        }
        return legacy.get(value.lower())
