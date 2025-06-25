from langdetect import detect

def detect_language_from_message(message: str) -> str:
    """Détecte la langue du message utilisateur."""
    detected_language = detect(message) 
    if detected_language in ["ar", "fr", "en"]:
        return detected_language
    else:
        return "en"