from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Job


class JobSource(ABC):
    """Interface commune à toutes les sources d'offres d'emploi."""

    name: str = "base"

    def __init__(self, source_config: dict):
        self.config = source_config or {}

    @abstractmethod
    def search(self, criteria: dict) -> list[Job]:
        """Retourne la liste des offres trouvées pour les critères donnés.

        `criteria` contient au minimum : mots_cles, lieu, type_contrat,
        max_resultats.
        En cas d'erreur réseau ou de structure de page inattendue, une
        source doit afficher un avertissement et retourner une liste vide
        plutôt que de faire planter toute l'application.
        """
        raise NotImplementedError
