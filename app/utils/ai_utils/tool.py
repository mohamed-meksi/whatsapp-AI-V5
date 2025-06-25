import logging
from typing import Callable, Dict, Any

class Tool:
    """Représente un outil callable pour l'IA."""
    def __init__(self, name: str, func: Callable, description: Dict[str, str]):
        self.name = name
        self.func = func
        self.description = description

    def get_description(self, lang: str = "en") -> str:
        """Retourne la description de l'outil pour la langue spécifiée, ou l'anglais si non trouvée."""
        return self.description.get(lang, self.description.get("en", "No description available."))

    def execute(self, *args, **kwargs) -> Any:
        """Exécute la fonction enveloppée."""
        try:
            logging.info(f"Executing tool '{self.name}' with args: {args}, kwargs: {kwargs}")
            result = self.func(*args, **kwargs)
            logging.info(f"Tool '{self.name}' executed, result: {result}")
            return result
        except Exception as e:
            logging.error(f"Error executing tool '{self.name}': {e}")
            return f"Error: Could not execute tool '{self.name}' - {str(e)}" 