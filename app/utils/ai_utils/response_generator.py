import shelve
import logging
from typing import Dict, Tuple
from datetime import datetime
from .language_utils import detect_language_from_message
from .conversation_manager import conversation_manager
import google.generativeai as genai
import os
from dotenv import load_dotenv
import sys
import requests
import json

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logging.error("GEMINI_API_KEY not found in environment variables.")
    sys.exit("GEMINI_API_KEY not configured. Exiting.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

def analyze_user_response(message: str, context: str) -> Dict:
    """
    Utilise l'IA pour analyser la réponse de l'utilisateur et extraire les informations pertinentes.
    
    Args:
        message: Le message de l'utilisateur
        context: Le contexte de la conversation (étape actuelle, etc.)
    
    Returns:
        Dict contenant les informations extraites et analysées
    """
    prompt = f"""Analyze this user message and extract relevant information.
Context: {context}
User message: {message}

Extract and return a JSON with:
1. If location mentioned:
   - Detected city name (raw form)
   - Any context about the location
2. If program/education mentioned:
   - Type of program/education
   - Specific interests/requirements
   - Level/experience mentioned
3. Other relevant information found

Return format:
{{
    "location": {{
        "raw_city": string or null,
        "context": string or null
    }},
    "program": {{
        "type": string or null,
        "interests": list of strings,
        "level": string or null
    }},
    "other_info": {{
        "key": "value"
    }}
}}"""

    try:
        response = model.generate_content(prompt)
        result = response.text
        # Extraire le JSON de la réponse
        import json
        import re
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if not json_match:
            logging.error("No JSON found in AI response")
            return {}
            
        analysis = json.loads(json_match.group())
        
        # Si une ville est mentionnée, la valider
        if analysis.get("location", {}).get("raw_city"):
            city_name = analysis["location"]["raw_city"]
            is_valid, confidence, normalized_name = validate_moroccan_city(city_name)
            
            # Mettre à jour l'analyse avec les informations validées
            analysis["location"].update({
                "city": normalized_name,
                "confidence": confidence,
                "is_valid_moroccan_city": is_valid,
                "raw_city": city_name  # Garder la version originale
            })
        
        return analysis
        
    except Exception as e:
        logging.error(f"Error analyzing user response: {e}")
        return {}

def debug_separator(title: str, level: str = "INFO"):
    """Crée une séparation visuelle pour le débogage"""
    separator = "=" * 80
    if level == "ERROR":
        logging.error(f"\n{separator}")
        logging.error(f"🔴 {title}")
        logging.error(f"{separator}")
    elif level == "WARNING":
        logging.warning(f"\n{separator}")
        logging.warning(f"🟡 {title}")
        logging.warning(f"{separator}")
    else:
        logging.info(f"\n{separator}")
        logging.info(f"🔵 {title}")
        logging.info(f"{separator}")

def check_if_thread_exists(wa_id: str):
    debug_separator("VÉRIFICATION DE L'EXISTENCE DU THREAD", "INFO")
    logging.info(f"👤 Vérification du thread pour WA_ID: {wa_id}")
    
    with shelve.open("threads_db") as threads_shelf:
        thread_id = threads_shelf.get(wa_id, None)
        if thread_id:
            logging.info(f"✅ Thread existant trouvé: {thread_id}")
        else:
            logging.info("❌ Aucun thread existant trouvé")
        return thread_id

def store_thread(wa_id: str, thread_id: str):
    debug_separator("SAUVEGARDE DU THREAD", "INFO")
    logging.info(f"👤 WA_ID: {wa_id}")
    logging.info(f"🆔 Thread ID: {thread_id}")
    
    with shelve.open("threads_db", writeback=True) as threads_shelf:
        threads_shelf[wa_id] = thread_id
        logging.info("✅ Thread sauvegardé avec succès")

def generate_response(message_body: str, wa_id: str, name: str) -> str:
    """Génère une réponse à partir du message de l'utilisateur."""
    try:
        debug_separator("GÉNÉRATION DE RÉPONSE", "INFO")
        logging.info(f"👤 Utilisateur: {name} ({wa_id})")
        logging.info(f"💬 Message: {message_body}")
        
        # Détection de la langue
        detected_language = detect_language_from_message(message_body)
        conversation_manager.detected_language = detected_language
        logging.info(f"🌐 Langue détectée: {detected_language}")
        
        # Continuer le flux normal - la vérification d'inscription se fera dans l'étape appropriée
        debug_separator("FLUX NORMAL", "INFO")

        # Étape 1: Analyse IA du message
        debug_separator("ÉTAPE 1: ANALYSE IA DU MESSAGE", "INFO")
        user_state = conversation_manager.get_user_state(wa_id)
        current_step = user_state["current_step"]
        
        context = f"""Current step: {current_step}
User state: {user_state}
Detected language: {detected_language}"""
        
        analysis_result = analyze_user_response(message_body, context)
        logging.info(f"📊 Analyse IA: {analysis_result}")

        # Si une ville est mentionnée avec confiance
        if analysis_result.get("location", {}).get("city") and analysis_result["location"]["confidence"] > 0.8:
            city = analysis_result["location"]["city"]
            if analysis_result["location"]["is_valid_moroccan_city"]:
                conversation_manager.update_user_info(wa_id, "city", city)
                logging.info(f"🏙️ Ville validée et enregistrée: {city}")

        # Si un programme est mentionné
        if analysis_result.get("program", {}).get("type"):
            program_type = analysis_result["program"]["type"]
            conversation_manager.update_user_info(wa_id, "program", program_type)
            logging.info(f"📚 Programme détecté et enregistré: {program_type}")

        # Étape 2: Sauvegarde du message utilisateur en base
        debug_separator("ÉTAPE 2: SAUVEGARDE DU MESSAGE UTILISATEUR", "INFO")
        user_message_metadata = {
            "language": detected_language,
            "user_name": name,
            "message_type": "user_input",
            "ai_analysis": analysis_result
        }
        
        conversation_manager.save_message_to_db(
            wa_id, 
            "user", 
            f"[User: {name}] {message_body}",
            user_message_metadata
        )

        # Étape 3: Préparation du contexte enrichi
        debug_separator("ÉTAPE 3: PRÉPARATION DU CONTEXTE", "INFO")
        context_info = (
            f"[INTERNAL CONTEXT - DO NOT MENTION TO USER]\n"
            f"Current step: {current_step}\n"
            f"User state: {user_state}\n"
            f"Detected language: {detected_language}\n"
            f"AI Analysis: {json.dumps(analysis_result, indent=2)}\n"
            f"[END INTERNAL CONTEXT]\n\n"
            f"User message: {message_body}"
        )

        # Étape 4: Envoi du message à l'IA
        debug_separator("ÉTAPE 4: ENVOI DU MESSAGE À L'IA", "INFO")
        chat = conversation_manager.get_or_create_chat(wa_id)
        response = chat.send_message(
            context_info,
            generation_config=conversation_manager.generation_config
        )

        ai_response = response.text
        logging.info(f"🤖 Réponse brute de l'IA: {ai_response}")

        # Étape 5: Traitement des appels d'outils
        debug_separator("ÉTAPE 5: TRAITEMENT DES APPELS D'OUTILS", "INFO")
        clean_response, tool_results = conversation_manager.process_tool_calls_from_text(ai_response, wa_id)
        
        if tool_results:
            debug_separator("TRAITEMENT AVEC OUTILS EXÉCUTÉS", "INFO")
            logging.info(f"🔧 Résultats d'exécution des outils: {tool_results}")
            
            # Create context for the AI to generate a natural response based on tool results
            tool_context = (
                f"[TOOL EXECUTION RESULTS - USE THIS TO GENERATE YOUR RESPONSE]\n"
                f"{tool_results}\n"
                f"[END TOOL RESULTS]\n\n"
                f"Based on the tool execution results above, provide a natural, helpful response to the user in {detected_language}. "
                f"Do not mention internal status updates or tool names. Focus on providing useful information to help the user."
            )
            logging.info(f"📋 Contexte des outils: {tool_context}")
            
            debug_separator("GÉNÉRATION DE LA RÉPONSE FINALE AVEC OUTILS", "INFO")
            follow_up_response = chat.send_message(
                tool_context,
                generation_config=conversation_manager.generation_config
            )
            
            final_response = follow_up_response.text
            logging.info(f"✅ Réponse finale avec outils: {final_response}")
            
            # Clean any remaining tool calls from the final response
            final_clean_response, _ = conversation_manager.process_tool_calls_from_text(final_response, wa_id)
            logging.info(f"🧹 Réponse finale nettoyée: {final_clean_response}")
            
            # Sauvegarde de la réponse avec outils
            debug_separator("SAUVEGARDE DE LA RÉPONSE AVEC OUTILS", "INFO")
            assistant_metadata = {
                "language": detected_language, 
                "had_tool_execution": True,
                "message_type": "assistant_response_with_tools",
                "tool_results_summary": tool_results[:200] + "..." if len(tool_results) > 200 else tool_results
            }
            logging.info(f"📋 Métadonnées de la réponse: {assistant_metadata}")
            
            conversation_manager.save_message_to_db(
                wa_id,
                "assistant", 
                final_clean_response,
                assistant_metadata
            )
            logging.info("✅ Réponse avec outils sauvegardée")
            
            debug_separator("GÉNÉRATION TERMINÉE AVEC OUTILS", "INFO")
            return final_clean_response
        else:
            debug_separator("TRAITEMENT SANS OUTILS - VÉRIFICATION FALLBACK", "INFO")
            logging.info("🔍 Aucun outil exécuté, vérification des appels d'outils dans les blocs de code...")
            
            # If no tool calls were found, check if the response contains tool syntax that wasn't processed
            import re
            
            # Check for tool calls in code blocks
            code_block_pattern = r'```[^`]*?([a-zA-Z_]+)\([^)]*\)[^`]*?```'
            code_block_matches = re.findall(code_block_pattern, clean_response)
            logging.info(f"🔍 Correspondances dans les blocs de code: {code_block_matches}")
            
            # Vérifier si le message concerne une recherche de programme
            program_search_keywords = [
                "bootcamp", "formation", "programme", "cours", "développement",
                "development", "web", "mobile", "data", "science", "cybersécurité",
                "cybersecurity", "full stack", "fullstack"
            ]
            
            message_lower = message_body.lower()
            is_program_search = any(keyword in message_lower for keyword in program_search_keywords)
            
            if is_program_search:
                debug_separator("RECHERCHE DE PROGRAMMES DÉTECTÉE", "INFO")
                logging.info("🔍 Message concernant une recherche de programme détecté")
                
                # D'abord obtenir tous les programmes disponibles
                available_sessions_tool = conversation_manager.tool_manager.get_tool("get_available_sessions")
                if available_sessions_tool:
                    try:
                        sessions_result = available_sessions_tool.execute()
                        sessions_data = json.loads(sessions_result)
                        
                        if sessions_data["status"] == "success":
                            # Ensuite obtenir les détails spécifiques si un programme correspond
                            matching_programs = []
                            for program in sessions_data["programs"]:
                                program_name = program["program_name"].lower()
                                if any(keyword in program_name for keyword in message_lower.split()):
                                    matching_programs.append(program)
                            
                            if matching_programs:
                                # Obtenir les détails pour chaque programme correspondant
                                program_details = []
                                program_details_tool = conversation_manager.tool_manager.get_tool("get_program_details")
                                
                                for program in matching_programs:
                                    try:
                                        details_result = program_details_tool.execute(f"{program['program_name']} - {program['location']}")
                                        details_data = json.loads(details_result)
                                        if details_data["status"] == "success":
                                            program_details.append(details_data)
                                    except Exception as e:
                                        logging.error(f"Erreur lors de l'obtention des détails du programme: {e}")
                                
                                # Générer une réponse basée sur les résultats
                                tool_context = (
                                    f"[TOOL EXECUTION RESULTS - USE THIS TO GENERATE YOUR RESPONSE]\n"
                                    f"Available programs: {json.dumps(sessions_data, indent=2)}\n"
                                    f"Matching programs details: {json.dumps(program_details, indent=2)}\n"
                                    f"[END TOOL RESULTS]\n\n"
                                    f"Based on the tool execution results above, provide a natural, helpful response to the user in {detected_language}. "
                                    f"Present the matching programs in a clear, formatted way. If no exact match is found, suggest similar programs."
                                )
                            else:
                                # Aucun programme correspondant exactement, suggérer des alternatives
                                tool_context = (
                                    f"[TOOL EXECUTION RESULTS - USE THIS TO GENERATE YOUR RESPONSE]\n"
                                    f"Available programs: {json.dumps(sessions_data, indent=2)}\n"
                                    f"[END TOOL RESULTS]\n\n"
                                    f"The user asked about programs that don't exactly match our offerings. "
                                    f"Based on the available programs above, provide a helpful response in {detected_language} "
                                    f"suggesting relevant alternatives that might interest them."
                                )
                            
                            debug_separator("GÉNÉRATION DE RÉPONSE BASÉE SUR LES PROGRAMMES", "INFO")
                            follow_up_response = chat.send_message(
                                tool_context,
                                generation_config=conversation_manager.generation_config
                            )
                            
                            final_response = follow_up_response.text
                            logging.info(f"✅ Réponse finale avec programmes: {final_response}")
                            
                            # Sauvegarde de la réponse
                            program_search_metadata = {
                                "language": detected_language,
                                "had_tool_execution": True,
                                "message_type": "program_search_response",
                                "matching_programs": len(matching_programs),
                                "total_programs": len(sessions_data["programs"])
                            }
                            
                            conversation_manager.save_message_to_db(
                                wa_id,
                                "assistant",
                                final_response,
                                program_search_metadata
                            )
                            logging.info("✅ Réponse de recherche de programmes sauvegardée")
                            
                            debug_separator("GÉNÉRATION TERMINÉE AVEC RECHERCHE DE PROGRAMMES", "INFO")
                            return final_response
                            
                    except Exception as e:
                        logging.error(f"❌ Erreur lors de la recherche de programmes: {e}")
            
            if code_block_matches:
                debug_separator("EXÉCUTION FALLBACK DES OUTILS", "INFO")
                # Try to extract and execute the tool calls from code blocks
                for tool_name in code_block_matches:
                    if tool_name in ['get_available_sessions', 'get_bootcamp_info']:
                        logging.info(f"🔧 Outil trouvé dans le bloc de code: {tool_name}")
                        tool = conversation_manager.tool_manager.get_tool(tool_name)
                        if tool:
                            try:
                                logging.info(f"🚀 Exécution de l'outil: {tool_name}")
                                tool_result = tool.execute()
                                logging.info(f"✅ Résultat de l'outil: {tool_result}")
                                
                                # Generate response based on the tool result
                                tool_context = (
                                    f"[TOOL EXECUTION RESULTS - USE THIS TO GENERATE YOUR RESPONSE]\n"
                                    f"{tool_result}\n"
                                    f"[END TOOL RESULTS]\n\n"
                                    f"Based on the tool execution results above, provide a natural, helpful response to the user in {detected_language}. "
                                    f"Present the bootcamp information in a clear, formatted way."
                                )
                                
                                debug_separator("GÉNÉRATION DE RÉPONSE BASÉE SUR LES OUTILS FALLBACK", "INFO")
                                follow_up_response = chat.send_message(
                                    tool_context,
                                    generation_config=conversation_manager.generation_config
                                )
                                
                                final_response = follow_up_response.text
                                logging.info(f"✅ Réponse finale fallback: {final_response}")
                                
                                # Sauvegarde de la réponse fallback
                                fallback_metadata = {
                                    "language": detected_language, 
                                    "had_tool_execution": True,
                                    "message_type": "assistant_response_with_tools_fallback",
                                    "tool_results_summary": str(tool_result)[:200] + "..." if len(str(tool_result)) > 200 else str(tool_result)
                                }
                                
                                conversation_manager.save_message_to_db(
                                    wa_id,
                                    "assistant", 
                                    final_response,
                                    fallback_metadata
                                )
                                logging.info("✅ Réponse fallback sauvegardée")
                                
                                debug_separator("GÉNÉRATION TERMINÉE AVEC FALLBACK", "INFO")
                                return final_response
                                
                            except Exception as e:
                                logging.error(f"❌ Erreur lors de l'exécution de l'outil fallback {tool_name}: {e}")
            
            debug_separator("NETTOYAGE FINAL DE LA RÉPONSE", "INFO")
            # Remove any remaining code blocks or tool syntax from the response
            logging.info("🧹 Suppression des blocs de code restants...")
            clean_response = re.sub(r'```[^`]*```', '', clean_response)
            clean_response = re.sub(r'`[^`]+`', '', clean_response)
            clean_response = clean_response.strip()
            logging.info(f"🧹 Réponse après nettoyage: {clean_response}")
            
            # If the response is empty after cleaning, ask AI to generate a minimal response
            if len(clean_response.strip()) < 10:
                debug_separator("GÉNÉRATION DE RÉPONSE MINIMALE", "WARNING")
                logging.warning("⚠️ Réponse trop courte, génération d'une réponse minimale...")
                
                minimal_context = (
                    f"The user sent: '{message_body}' but I couldn't process it properly. "
                    f"Please provide a brief, helpful response in {detected_language} asking them to clarify or rephrase their question."
                )
                
                minimal_response = chat.send_message(
                    minimal_context,
                    generation_config=conversation_manager.generation_config
                )
                clean_response = minimal_response.text
                logging.info(f"✅ Réponse minimale générée: {clean_response}")
            
            # Sauvegarde de la réponse simple
            debug_separator("SAUVEGARDE DE LA RÉPONSE SIMPLE", "INFO")
            simple_metadata = {
                "language": detected_language, 
                "had_tool_execution": False,
                "message_type": "assistant_response_simple"
            }
            
            conversation_manager.save_message_to_db(
                wa_id,
                "assistant",
                clean_response,
                simple_metadata
            )
            logging.info("✅ Réponse simple sauvegardée")
            
            debug_separator("GÉNÉRATION TERMINÉE SANS OUTILS", "INFO")
            return clean_response

    except Exception as e:
        debug_separator("ERREUR LORS DE LA GÉNÉRATION", "ERROR")
        logging.error(f"❌ Erreur lors de la génération de réponse pour {wa_id}: {e}")
        import traceback
        logging.error(f"📍 Traceback complet:\n{traceback.format_exc()}")
        
        # En cas d'erreur, essayer de générer une réponse d'erreur via l'AI
        try:
            debug_separator("GÉNÉRATION DE RÉPONSE D'ERREUR", "WARNING")
            logging.warning("⚠️ Tentative de génération d'une réponse d'erreur...")
            
            error_context = (
                f"I encountered a technical error while processing the user's message. "
                f"Please provide a brief, polite apology in {conversation_manager.detected_language} "
                f"and ask them to try again. Keep it short and helpful."
            )
            
            error_chat = conversation_manager.get_or_create_chat(wa_id)
            error_response = error_chat.send_message(
                error_context,
                generation_config=conversation_manager.generation_config
            )
            
            final_error_response = error_response.text
            logging.info(f"✅ Réponse d'erreur générée: {final_error_response}")
            
            # Sauvegarde de la réponse d'erreur
            error_metadata = {
                "error": True, 
                "error_message": str(e),
                "message_type": "error_response",
                "language": conversation_manager.detected_language
            }
            
            conversation_manager.save_message_to_db(
                wa_id,
                "assistant",
                final_error_response,
                error_metadata
            )
            logging.info("✅ Réponse d'erreur sauvegardée")
            
            return final_error_response
            
        except Exception as nested_error:
            logging.error(f"Failed to generate AI error response: {nested_error}")
            
            # Fallback ultime uniquement si l'AI ne peut pas répondre du tout
            if conversation_manager.detected_language == "fr":
                fallback_response = "Désolé, problème technique. Réessayez plus tard."
            elif conversation_manager.detected_language == "ar":
                fallback_response = "عذراً، مشكلة تقنية. حاول مرة أخرى لاحقاً."
            else:
                fallback_response = "Sorry, technical issue. Please try again later."
            
            # Sauvegarder même les messages d'erreur (dans registrations)
            conversation_manager.save_message_to_db(
                wa_id,
                "assistant",
                fallback_response,
                {
                    "error": True, 
                    "error_message": str(e),
                    "message_type": "fallback_error_response",
                    "language": conversation_manager.detected_language
                }
            )
                
            return fallback_response

def validate_moroccan_city(city_name: str) -> Tuple[bool, float, str]:
    """
    Valide si une ville est au Maroc en utilisant l'API de géocodage Nominatim.
    
    Args:
        city_name: Nom de la ville à valider
        
    Returns:
        Tuple[bool, float, str]: (est_valide, confiance, nom_normalisé)
    """
    try:
        # Utiliser Nominatim (OpenStreetMap) pour le géocodage
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": f"{city_name}, Morocco",
            "format": "json",
            "countrycodes": "ma",
            "limit": 1
        }
        headers = {
            "User-Agent": "WhatsAppAI/1.0"  # Requis par Nominatim
        }
        
        response = requests.get(url, params=params, headers=headers)
        results = response.json()
        
        if results:
            result = results[0]
            # Vérifier si c'est bien au Maroc
            if "Morocco" in result.get("display_name", ""):
                # Calculer un score de confiance basé sur l'importance
                confidence = min(float(result.get("importance", 0.5)), 1.0)
                # Retourner le nom normalisé depuis OSM
                normalized_name = result.get("name", city_name)
                return True, confidence, normalized_name
        
        return False, 0.0, city_name
        
    except Exception as e:
        logging.error(f"Erreur lors de la validation de la ville {city_name}: {e}")
        return False, 0.0, city_name

# Fonction utilitaire pour analyser les conversations d'un utilisateur
def get_user_conversation_summary(wa_id: str) -> Dict:
    """Récupère un résumé des conversations de l'utilisateur."""
    try:
        stats = conversation_manager.get_user_conversation_stats(wa_id)
        profile = conversation_manager.get_user_full_profile(wa_id)
        
        summary = {
            "user_id": wa_id,
            "conversation_stats": stats,
            "current_step": profile.get("session_data", {}).get("current_step", "unknown") if profile else "unknown",
            "registration_status": profile.get("status", "not_registered") if profile else "not_registered",
            "last_activity": profile.get("last_message_at") if profile else None,
            "total_conversations": stats.get("total_messages", 0)
        }
        
        return summary
    except Exception as e:
        logging.error(f"Error getting conversation summary for {wa_id}: {e}")
        return {"error": str(e)}

# Fonction pour nettoyer les anciennes conversations
def cleanup_old_user_conversations(days_to_keep: int = 30) -> Dict:
    """Nettoie les anciennes conversations pour tous les utilisateurs."""
    try:
        cleaned_count = conversation_manager.cleanup_old_conversations(days_to_keep)
        return {
            "success": True,
            "cleaned_users": cleaned_count,
            "days_kept": days_to_keep
        }
    except Exception as e:
        logging.error(f"Error cleaning up conversations: {e}")
        return {"success": False, "error": str(e)}

# Fonction pour exporter les conversations d'un utilisateur
def export_user_conversations(wa_id: str, format_type: str = "json") -> Dict:
    """Exporte les conversations d'un utilisateur dans le format spécifié."""
    try:
        profile = conversation_manager.get_user_full_profile(wa_id)
        if not profile:
            return {"error": "User not found"}
        
        conversations = profile.get("conversations", [])
        
        if format_type == "json":
            export_data = {
                "user_id": wa_id,
                "export_date": datetime.utcnow().isoformat(),
                "total_messages": len(conversations),
                "conversations": conversations
            }
            return {"success": True, "data": export_data}
        
        elif format_type == "csv":
            # Conversion en format CSV-friendly
            csv_data = []
            for conv in conversations:
                csv_data.append({
                    "timestamp": conv.get("timestamp", "").isoformat() if conv.get("timestamp") else "",
                    "role": conv.get("role", ""),
                    "message": conv.get("message", ""),
                    "language": conv.get("metadata", {}).get("language", ""),
                    "message_type": conv.get("metadata", {}).get("message_type", "")
                })
            return {"success": True, "data": csv_data}
        
        else:
            return {"error": "Unsupported format type"}
            
    except Exception as e:
        logging.error(f"Error exporting conversations for {wa_id}: {e}")
        return {"error": str(e)}