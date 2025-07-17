from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

def detect_language_from_message(message: str) -> str:
    """Détecte la langue du message utilisateur."""
    try:
        detected_language = detect(message) 
        if detected_language in ["ar", "fr", "en"]:
            return detected_language
        else:
            return "ar"  
    except LangDetectException:
        return "ar"  