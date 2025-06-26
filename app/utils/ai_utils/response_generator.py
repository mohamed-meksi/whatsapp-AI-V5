import shelve
import logging
from typing import Dict
from datetime import datetime
from .language_utils import detect_language_from_message
from .conversation_manager import conversation_manager

def check_if_thread_exists(wa_id: str):
    with shelve.open("threads_db") as threads_shelf:
        return threads_shelf.get(wa_id, None)

def store_thread(wa_id: str, thread_id: str):
    with shelve.open("threads_db", writeback=True) as threads_shelf:
        threads_shelf[wa_id] = thread_id

def generate_response(message_body: str, wa_id: str, name: str) -> str:
    """Génère une réponse à partir du message de l'utilisateur avec persistance en base."""
    try:
        detected_language = detect_language_from_message(message_body)
        conversation_manager.detected_language = detected_language
        logging.info(f"Detected language 💬: {detected_language}")

        # Sauvegarder le message utilisateur en base (dans la collection registrations)
        conversation_manager.save_message_to_db(
            wa_id, 
            "user", 
            f"[User: {name}] {message_body}",
            {
                "language": detected_language, 
                "user_name": name,
                "message_type": "user_input"
            }
        )

        chat = conversation_manager.get_or_create_chat(wa_id)
        user_state = conversation_manager.get_user_state(wa_id)
        current_step = user_state["current_step"]

        context_info = (
            f"[INTERNAL CONTEXT - DO NOT MENTION TO USER]\n"
            f"Current step: {current_step}\n"
            f"User state: {user_state}\n"
            f"Detected language: {detected_language}\n"
            f"Please respond in {detected_language}.\n"
            f"[END INTERNAL CONTEXT]\n\n"
            f"User message: {message_body}"
        )

        response = chat.send_message(
            context_info,
            generation_config=conversation_manager.generation_config
        )

        ai_response = response.text
        logging.info(f"Raw AI response: {ai_response}")

        clean_response, tool_results = conversation_manager.process_tool_calls_from_text(ai_response, wa_id)
        
        if tool_results:
            logging.info(f"Tool execution results: {tool_results}")
            
            tool_context = (
                f"[TOOL EXECUTION RESULTS - USE THIS TO GENERATE YOUR RESPONSE]\n"
                f"{tool_results}\n"
                f"[END TOOL RESULTS]\n\n"
                f"Based on the tool execution results above, provide a natural, helpful response to the user in {detected_language}. "
                f"Do not mention internal status updates or tool names. Focus on providing useful information to help the user."
            )
            
            follow_up_response = chat.send_message(
                tool_context,
                generation_config=conversation_manager.generation_config
            )
            
            final_response = follow_up_response.text
            
            # Sauvegarder la réponse de l'assistant en base (dans registrations)
            conversation_manager.save_message_to_db(
                wa_id,
                "assistant", 
                final_response,
                {
                    "language": detected_language, 
                    "had_tool_execution": True,
                    "message_type": "assistant_response_with_tools",
                    "tool_results_summary": tool_results[:200] + "..." if len(tool_results) > 200 else tool_results
                }
            )
            
            return final_response
        else:
            # Sauvegarder la réponse de l'assistant en base (dans registrations)
            conversation_manager.save_message_to_db(
                wa_id,
                "assistant",
                clean_response,
                {
                    "language": detected_language, 
                    "had_tool_execution": False,
                    "message_type": "assistant_response_simple"
                }
            )
            
            return clean_response

    except Exception as e:
        logging.error(f"Error generating response for {wa_id}: {e}")
        
        if conversation_manager.detected_language == "fr":
            error_response = "Désolé, j'ai rencontré un problème technique. Pouvez-vous reformuler votre question ?"
        elif conversation_manager.detected_language == "ar":
            error_response = "عذراً، واجهت مشكلة تقنية. هل يمكنك إعادة صياغة سؤالك؟"
        else:
            error_response = "Sorry, I encountered a technical issue. Could you please rephrase your question?"
        
        # Sauvegarder même les messages d'erreur (dans registrations)
        conversation_manager.save_message_to_db(
            wa_id,
            "assistant",
            error_response,
            {
                "error": True, 
                "error_message": str(e),
                "message_type": "error_response",
                "language": conversation_manager.detected_language
            }
        )
            
        return error_response

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