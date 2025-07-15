import logging
from flask import current_app, jsonify
import json
import requests
import time
import hashlib

from app.services.openai_service import generate_response
import re

# Cache simple pour éviter les messages doubles
message_cache = {}
CACHE_DURATION = 20  # 20 secondes

def debug_separator(title: str, level: str = "INFO"):
    """Crée une séparation visuelle pour le débogage"""
    separator = "━" * 60
    if level == "ERROR":
        logging.error(f"\n┌{separator}┐")
        logging.error(f"│ 🔴 {title:<56} │")
        logging.error(f"└{separator}┘")
    elif level == "WARNING":
        logging.warning(f"\n┌{separator}┐")
        logging.warning(f"│ 🟡 {title:<56} │")
        logging.warning(f"└{separator}┘")
    else:
        logging.info(f"\n┌{separator}┐")
        logging.info(f"│ 🔵 {title:<56} │")
        logging.info(f"└{separator}┘")

def log_compact_data(emoji: str, title: str, data: str, max_length: int = 80):
    """Affiche les données de manière compacte"""
    if len(data) > max_length:
        data = data[:max_length] + "..."
    logging.info(f"{emoji} {title}: {data}")

def get_message_hash(wa_id: str, message_body: str, timestamp: int) -> str:
    """Génère un hash unique pour un message."""
    logging.info(f"🔐 Génération du hash pour le message")
    logging.info(f"👤 WA_ID: {wa_id}")
    logging.info(f"💬 Message: {message_body}")
    logging.info(f"⏰ Timestamp: {timestamp}")
    
    hash_input = f"{wa_id}_{message_body}_{timestamp}"
    message_hash = hashlib.md5(hash_input.encode()).hexdigest()
    
    logging.info(f"🔐 Hash généré: {message_hash}")
    return message_hash

def is_duplicate_message(wa_id: str, message_body: str, timestamp: int) -> bool:
    """Vérifie si le message est un doublon."""
    message_hash = get_message_hash(wa_id, message_body, timestamp)
    current_time = time.time()
    
    # Nettoyer le cache des anciens messages
    keys_to_remove = [key for key, cached_time in message_cache.items() 
                      if current_time - cached_time > CACHE_DURATION]
    
    for key in keys_to_remove:
        del message_cache[key]
    
    # Vérifier si le message est un doublon
    if message_hash in message_cache:
        debug_separator("DOUBLON DÉTECTÉ", "WARNING")
        logging.warning(f"⚠️ Message doublon: {wa_id}")
        return True
    
    # Ajouter le message au cache
    message_cache[message_hash] = current_time
    logging.info(f"✅ Message validé (cache: {len(message_cache)})")
    return False

def log_http_response(response):
    """Log détaillé de la réponse HTTP"""
    debug_separator("RÉPONSE HTTP REÇUE", "INFO")
    logging.info(f"📊 Status: {response.status_code}")
    logging.info(f"📋 Content-type: {response.headers.get('content-type')}")
    logging.info(f"📄 Body: {response.text}")
    
    if response.status_code == 200:
        logging.info("✅ Réponse HTTP réussie")
    else:
        logging.warning(f"⚠️ Réponse HTTP avec code: {response.status_code}")

def get_text_message_input(recipient, text):
    """Prépare le payload pour envoyer un message texte"""
    debug_separator("PRÉPARATION DU MESSAGE", "INFO")
    logging.info(f"👤 Destinataire: {recipient}")
    logging.info(f"💬 Texte: {text}")
    
    message_data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    
    json_payload = json.dumps(message_data)
    logging.info(f"📋 Payload JSON généré: {json_payload}")
    return json_payload

def send_message(data):
    """Envoie un message via l'API WhatsApp"""
    debug_separator("ENVOI MESSAGE", "INFO")
    
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"

    logging.info(f"🌐 API URL configurée")
    logging.info(f"👤 Destinataire: {current_app.config['RECIPIENT_WAID']}")
    
    try:
        logging.info("🚀 Envoi en cours...")
        
        response = requests.post(url, data=data, headers=headers, timeout=10)
        
        if response.status_code == 200:
            logging.info("✅ Message envoyé avec succès")
        else:
            logging.warning(f"⚠️ Réponse HTTP: {response.status_code}")
        
        response.raise_for_status()
        
    except requests.Timeout:
        debug_separator("ERREUR: TIMEOUT", "ERROR")
        logging.error("❌ Timeout lors de l'envoi")
        return jsonify({"status": "error", "message": "Request timed out"}), 408
        
    except requests.RequestException as e:
        debug_separator("ERREUR: REQUÊTE", "ERROR")
        logging.error(f"❌ Échec requête: {str(e)[:100]}")
        return jsonify({"status": "error", "message": "Failed to send message"}), 500
        
    else:
        return response

def process_text_for_whatsapp(text):
    """Traite le texte pour le format WhatsApp"""
    original_length = len(text)
    
    # Remove brackets
    text = re.sub(r"\【.*?\】", "", text).strip()
    
    # Pattern to find double asterisks including the word(s) in between
    text = re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)
    
    logging.info(f"🔧 Texte formaté ({original_length} → {len(text)} chars)")
    return text

def process_whatsapp_message(body):
    """Process incoming WhatsApp message with duplicate detection."""
    debug_separator("TRAITEMENT MESSAGE", "INFO")
    
    try:
        # Extraction des données du message
        wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
        name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]
        message = body["entry"][0]["changes"][0]["value"]["messages"][0]
        message_body = message["text"]["body"]
        message_timestamp = message.get("timestamp", int(time.time()))

        # Affichage compact des infos
        logging.info(f"👤 {name} ({wa_id})")
        log_compact_data("💬", "Message", message_body, 60)

        # Vérifier si c'est un message en doublon
        if is_duplicate_message(wa_id, message_body, message_timestamp):
            logging.warning(f"⚠️ Message doublon ignoré")
            return
        
        print(f"\n📱 NOUVEAU MESSAGE de {name}")
        print(f"💬 {message_body}")
        print("━" * 60)

        # Génération de réponse IA
        logging.info("🤖 Génération réponse IA...")
        response = generate_response(message_body, wa_id, name)
        
        if not response or len(response.strip()) == 0:
            logging.error(f"❌ Réponse IA vide")
            return
        
        # Traitement et envoi
        formatted_response = process_text_for_whatsapp(response)
        data = get_text_message_input(current_app.config["RECIPIENT_WAID"], formatted_response)
        send_result = send_message(data)
        
        debug_separator("MESSAGE TRAITÉ", "INFO")
        logging.info("✅ Traitement terminé avec succès")
        
    except KeyError as e:
        debug_separator("ERREUR: CLÉ MANQUANTE", "ERROR")
        logging.error(f"❌ Clé manquante: {e}")
        
    except Exception as e:
        debug_separator("ERREUR TRAITEMENT", "ERROR")
        logging.error(f"❌ Erreur: {str(e)[:100]}")

def is_valid_whatsapp_message(body):
    """Check if the incoming webhook event has a valid WhatsApp message structure."""
    try:
        is_valid = (
            body.get("object")
            and body.get("entry")
            and body["entry"][0].get("changes")
            and body["entry"][0]["changes"][0].get("value")
            and body["entry"][0]["changes"][0]["value"].get("messages")
            and body["entry"][0]["changes"][0]["value"]["messages"][0]
            and body["entry"][0]["changes"][0]["value"]["messages"][0].get("type") == "text"
        )
        
        if is_valid:
            logging.info("✅ Structure message valide")
        else:
            logging.warning("⚠️ Structure message invalide")
            
        return is_valid
        
    except (KeyError, IndexError, TypeError) as e:
        logging.error(f"❌ Erreur validation: {e}")
        return False