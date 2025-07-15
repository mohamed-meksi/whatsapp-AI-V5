import logging
import json
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import os
from bson import json_util
from bson.json_util import dumps
from threading import Thread
load_dotenv()

from flask import Blueprint, request, jsonify, current_app

from .decorators.security import signature_required
from .utils.whatsapp_utils import (
    process_whatsapp_message,
    is_valid_whatsapp_message,
)

MONGODB_URL = os.getenv('MONGODB_URL')
DATABASE_NAME = os.getenv('DATABASE_NAME')

webhook_blueprint = Blueprint("webhook", __name__)

def debug_separator(title: str, level: str = "INFO"):
    """Crée une séparation visuelle pour le débogage"""
    separator = "━" * 60  # Utilisation de ━ pour une meilleure visibilité
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

def log_compact_json(title: str, data: dict, max_length: int = 100):
    """Affiche les données JSON de manière compacte"""
    try:
        json_str = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        if len(json_str) > max_length:
            json_str = json_str[:max_length] + "..."
        logging.info(f"📋 {title}: {json_str}")
    except Exception as e:
        logging.info(f"📋 {title}: [Erreur d'affichage: {e}]")

def log_user_info(wa_id: str, name: str, message_text: str):
    """Affiche les informations utilisateur de manière claire"""
    logging.info(f"👤 Utilisateur: {name} ({wa_id})")
    if len(message_text) > 50:
        message_text = message_text[:50] + "..."
    logging.info(f"💬 Message: {message_text}")

def process_message_async(app, body):
    """
    Process the WhatsApp message asynchronously with proper application context
    """
    debug_separator("DÉBUT DU TRAITEMENT ASYNCHRONE DU MESSAGE", "INFO")
    
    with app.app_context():
        try:
            logging.info("📱 Contexte Flask appliqué avec succès")
            logging.info(f"📋 Body du message reçu: {json.dumps(body, indent=2)}")
            
            debug_separator("APPEL DE process_whatsapp_message", "INFO")
            process_whatsapp_message(body)
            
            debug_separator("TRAITEMENT ASYNCHRONE TERMINÉ AVEC SUCCÈS", "INFO")
            
        except Exception as e:
            debug_separator("ERREUR DANS LE TRAITEMENT ASYNCHRONE", "ERROR")
            logging.error(f"❌ Erreur lors du traitement asynchrone: {e}")
            logging.error(f"📋 Body du message: {body}")
            logging.error(f"🔍 Type d'erreur: {type(e).__name__}")
            import traceback
            logging.error(f"📍 Traceback complet:\n{traceback.format_exc()}")

def handle_message():
    """
    Handle incoming webhook events from the WhatsApp API.

    This function processes incoming WhatsApp messages and other events,
    such as delivery statuses. If the event is a valid message, it gets
    processed. If the incoming payload is not a recognized WhatsApp event,
    an error is returned.

    Every message send will trigger 4 HTTP requests to your webhook: message, sent, delivered, read.

    Returns:
        response: A tuple containing a JSON response and an HTTP status code.
    """
    debug_separator("WEBHOOK REÇU", "INFO")
    
    # Étape 1: Récupération du body
    logging.info("🔄 Récupération du body...")
    body = request.get_json()
    
    if not body:
        debug_separator("ERREUR: BODY VIDE", "ERROR")
        logging.error("❌ Aucun body JSON reçu")
        return jsonify({"status": "error", "message": "No JSON body provided"}), 400

    try:
        # Étape 2: Extraction des données de base
        logging.info("🔍 Extraction des données...")
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        # Étape 3: Vérification du type d'événement
        if value.get("statuses"):
            debug_separator("STATUT WHATSAPP", "WARNING")
            status_info = value.get("statuses", [{}])[0]
            status_type = status_info.get("status", "unknown")
            recipient = status_info.get("recipient_id", "unknown")
            logging.warning(f"📊 Statut: {status_type} pour {recipient}")
            return jsonify({"status": "ok"}), 200

        # Étape 4: Validation du message
        logging.info("🔍 Validation du message...")
        if is_valid_whatsapp_message(body):
            logging.info("✅ Message valide détecté")
            
            # Étape 5: Extraction des informations du message
            messages = value.get("messages", [])
            if messages:
                message = messages[0]
                message_type = message.get("type")
                
                if message_type == "text":
                    debug_separator("TRAITEMENT MESSAGE TEXTE", "INFO")
                    
                    # Extraction des informations du message
                    try:
                        contacts = value.get("contacts", [{}])
                        if contacts:
                            wa_id = contacts[0].get("wa_id", "unknown")
                            name = contacts[0].get("profile", {}).get("name", "unknown")
                        else:
                            wa_id = "unknown"
                            name = "unknown"
                        
                        message_text = message.get("text", {}).get("body", "")
                        
                        # Affichage compact des infos utilisateur
                        log_user_info(wa_id, name, message_text)
                        
                    except Exception as extract_error:
                        logging.error(f"❌ Erreur extraction: {extract_error}")
                    
                    # Lancement du traitement asynchrone
                    logging.info("🚀 Lancement traitement async...")
                    app = current_app._get_current_object()
                    Thread(target=process_message_async, args=(app, body)).start()
                    logging.info("✅ Thread lancé")
                    
                else:
                    logging.warning(f"⚠️ Type non supporté: {message_type}")
            else:
                logging.warning("⚠️ Aucun message trouvé")
            
            debug_separator("RÉPONSE ENVOYÉE", "INFO")
            logging.info("📤 Confirmation webhook envoyée")
            print("━" * 60)
            return jsonify({"status": "ok"}), 200
            
        else:
            debug_separator("ÉVÉNEMENT NON-WHATSAPP", "ERROR")
            logging.error("❌ Événement non-WhatsApp détecté")
            # Affichage compact du body pour diagnostic
            log_compact_json("Body reçu", body)
            return (
                jsonify({"status": "error", "message": "Not a WhatsApp API event"}),
                404,
            )
            
    except json.JSONDecodeError as json_error:
        debug_separator("ERREUR JSON", "ERROR")
        logging.error(f"❌ Décodage JSON échoué: {json_error}")
        return jsonify({"status": "error", "message": "Invalid JSON provided"}), 400
        
    except Exception as general_error:
        debug_separator("ERREUR GÉNÉRALE", "ERROR")
        logging.error(f"❌ Erreur: {general_error}")
        logging.error(f"🔍 Type: {type(general_error).__name__}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500


# Required webhook verifictaion for WhatsApp
def verify():
    # Parse params from the webhook verification request
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    
    print("mode: ", mode)
    print("token: ", token)
    print("challenge: ", challenge)
    print("current_app.config['VERIFY_TOKEN']: ", current_app.config["VERIFY_TOKEN"])
    # Check if a token and mode were sent
    if mode and token:
        # Check the mode and token sent are correct
        if mode == "subscribe" and token == current_app.config["VERIFY_TOKEN"]:
            # Respond with 200 OK and challenge token from the request
            logging.info("WEBHOOK_VERIFIED")
            return challenge, 200
        else:
            # Responds with '403 Forbidden' if verify tokens do not match
            logging.info("VERIFICATION_FAILED")
            return jsonify({"status": "error", "message": "Verification failed"}), 403
    else:
        # Responds with '400 Bad Request' if verify tokens do not match
        logging.info("MISSING_PARAMETER")
        return jsonify({"status": "error", "message": "Missing parameters"}), 400


@webhook_blueprint.route("/webhook", methods=["GET"])
def webhook_get():
    return verify()

@webhook_blueprint.route("/webhook", methods=["POST"])
@signature_required
def webhook_post():
    return handle_message()


@webhook_blueprint.route("/user-info", methods=["GET"])
def user_info():
    try:
        client = MongoClient(MONGODB_URL)
        db = client[DATABASE_NAME]
        registrations_collection = db.registrations
        registrations = registrations_collection.find()
        
        # Convert MongoDB cursor to JSON-serializable format using json_util
        registrations_list = json.loads(dumps(list(registrations)))
        
        return jsonify({
            "status": "ok", 
            "registrations": registrations_list
        }), 200
    except Exception as e:
        logging.error(f"Error getting user info: {e}")
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500
    finally:
        client.close()  # Properly close the MongoDB connection



