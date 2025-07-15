import logging
from typing import Dict, Optional
from .tool_manager import ToolManager
import google.generativeai as genai
import os
import sys
from dotenv import load_dotenv
import re

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logging.error("GEMINI_API_KEY not found in environment variables.")
    sys.exit("GEMINI_API_KEY not configured. Exiting.")

genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel('gemini-1.5-flash')

generation_config = {
    "temperature": 0.7,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

class ConversationManager:
    """Gère les sessions de chat, l'historique et le traitement des outils avec persistance en base."""
    def __init__(self):
        from services.database_service import db_service
        self.db_service = db_service
        
        self.chats = {}  
        self.user_states = {}
        self.ordered_steps = [
            "motivation",
            "program_selection", 
            "collect_personal_info",
            "verify_information",  
            "confirm_enrollment",
            "enrollment_complete",
            "already_registered"  
        ]
        self.tool_manager = ToolManager(self)
        self.detected_language: str = "en"

    def get_user_state(self, user_id: str):
        """Récupère ou initialise l'état de l'utilisateur depuis la base de données."""
        if user_id not in self.user_states:
            # Tenter de charger depuis la base
            session_data = self.db_service.get_user_session(user_id)
            if session_data and 'session_data' in session_data:
                self.user_states[user_id] = session_data['session_data']
            else:
                # Créer un nouvel état utilisateur avec le wa_id automatiquement
                self.user_states[user_id] = {
                    "current_step": self.ordered_steps[0],
                    "personal_info": {
                        "wa_id": user_id  
                    },
                    "program": None,
                    "level": None,
                }
                # Sauvegarder immédiatement
                self._save_user_state(user_id)
        
        return self.user_states[user_id]

    def _save_user_state(self, user_id: str):
        """Sauvegarde l'état utilisateur en base de données."""
        if user_id in self.user_states:
            self.db_service.save_user_session(user_id, self.user_states[user_id])

    def get_current_step(self, user_id: str) -> str:
        """Retourne l'étape actuelle pour un utilisateur."""
        return self.get_user_state(user_id)["current_step"]

    def set_current_step(self, user_id: str, step_name: str) -> str:
        """Définit l'étape actuelle pour un utilisateur."""
        if step_name in self.ordered_steps:
            self.get_user_state(user_id)["current_step"] = step_name
            self._save_user_state(user_id)  # Sauvegarder en base
            logging.info(f"User {user_id} is now at step 🚶🏻‍♂️: {step_name}")
            return f"Step successfully set to {step_name}."
        logging.warning(f"Error: Step '{step_name}' is not a valid step for user {user_id}.")
        return f"Error: Failed to set step to {step_name} (invalid step name)."

    def advance_step(self, user_id: str) -> str:
        """Avance l'utilisateur à l'étape suivante dans le parcours."""
        current_state = self.get_user_state(user_id)
        current_step_name = current_state["current_step"]
        try:
            current_index = self.ordered_steps.index(current_step_name)
            if current_index < len(self.ordered_steps) - 1:
                next_step = self.ordered_steps[current_index + 1]
                self.set_current_step(user_id, next_step)
                return f"Successfully advanced to step 🚶🏻‍♂️: {next_step}."
            else:
                logging.info(f"User {user_id} is already at the last step 🚶🏻‍♂️: {current_step_name}")
                return f"Already at final step: {current_step_name}."
        except ValueError:
            logging.error(f"Current step '{current_step_name}' not found in ordered_steps for user {user_id}. Resetting to first step 🚶🏻‍♂️.")
            self.set_current_step(user_id, self.ordered_steps[0])
            return f"Error: Current step invalid. Reset to {self.ordered_steps[0]}."

    def update_user_info(self, user_id: str, field: str, value: str) -> str:
        """Met à jour une information spécifique pour l'utilisateur."""
        state = self.get_user_state(user_id)
        if field == "program":
            state["program"] = value
        elif field == "level":
            state["level"] = value
        else:
            state["personal_info"][field] = value
        
        self._save_user_state(user_id)  # Sauvegarder en base
        logging.info(f"Info utilisateur {user_id} mise à jour 📝: {field} = {value}")
        return f"User info '{field}' updated to '{value}'."

    def verify_user_information(self, user_id: str) -> Dict:
        """Vérifie et retourne les informations de l'utilisateur pour confirmation."""
        state = self.get_user_state(user_id)
        personal_info = state.get("personal_info", {})
        
        # Vérifier que toutes les informations requises sont présentes
        required_fields = {
            "full_name": "nom complet",
            "email": "adresse email", 
            "phone": "numéro de téléphone",
            "age": "âge"
        }
        
        missing_fields = []
        user_info = {}
        
        for field, field_name in required_fields.items():
            if field not in personal_info or not personal_info[field]:
                missing_fields.append(field_name)
            else:
                user_info[field] = personal_info[field]
        
        #  Ajouter automatiquement le wa_id s'il n'est pas déjà présent
        if "wa_id" not in personal_info:
            personal_info["wa_id"] = user_id
            user_info["wa_id"] = user_id
            self._save_user_state(user_id)
        else:
            user_info["wa_id"] = personal_info["wa_id"]
        
        return {
            "is_complete": len(missing_fields) == 0,
            "missing_fields": missing_fields,
            "user_info": user_info
        }

    def get_or_create_chat(self, wa_id: str):
        """Récupère une session de chat existante ou en crée une nouvelle."""
        self.get_user_state(wa_id)

        if wa_id not in self.chats:
            # Charger l'historique depuis la base de données (collection registrations)
            conversation_history = self.db_service.get_conversation_history(wa_id, limit=5)  # Réduit de 20 à 5 messages
            
            # Convertir l'historique pour Gemini
            gemini_history = []
            
            initial_system_context_template = (
                "You are a helpful and professional educational assistant for a Full Stack Web Development Bootcamp. "
                "Your primary goal is to guide potential students through the bootcamp information and registration process. "
                "You are based in Casablanca, Morocco. "
                "**IMPORTANT: For language detection, use simple keyword matching first (bonjour/hello/مرحبا) before full detection.** "
                "**PRIORITY 1: Quick language detection - French for 'bonjour/salut/merci', Arabic for 'مرحبا/شكرا', English for 'hi/hello/thanks'. Only use full detection if unclear.** "
                "**PRIORITY 2: When user asks about a program or bootcamp:** "
                "1. Use get_bootcamp_info(program_name, location) to get specific program details "
                "2. If not found, use search_programs(search_term) to find similar programs "
                "3. Always suggest alternatives if the exact program is not found "
                "4. Provide complete information about available programs, including start dates, duration, and price "
                "**PRIORITY 3: When user reaches step 'collect_personal_info', IMMEDIATELY check if they are already registered using check_user_registration tool before collecting any information.** "
                "**PRIORITY 4: If check_user_registration returns 'COLLECTE D'INFORMATIONS BLOQUÉE', 'تم حظر جمع المعلومات', or 'INFORMATION COLLECTION BLOCKED', do NOT proceed with collecting personal information. Display the registration details and offer help.** "
                "**PRIORITY 5: If check_user_registration returns 'NOUVELLE_INSCRIPTION', 'تسجيل_جديد', or 'NEW_REGISTRATION', proceed with normal information collection.** "
                "**PRIORITY 6: NEVER respond with 'we don't offer this program' without first checking available programs. Always show alternative programs that might interest the user.** "
                "**PRIORITY 7: If a user asks for information that an AVAILABLE TOOL can provide, you ABSOLUTELY MUST call that tool using the `{{tool_name:arg1,arg2,...}}` syntax. This tool call MUST be the ONLY thing in your response. DO NOT add any conversational text.** "
                "**PRIORITY 8: If a tool does not require arguments, use `{{tool_name}}`.** "
                "**PRIORITY 9: NEVER use code blocks (```) around tool calls. Tool calls should be direct: {{tool_name}} or {{tool_name:arg1,arg2}}** "
                "**PRIORITY 10: For registration, ALWAYS use verify_registration_info tool first to confirm information with user before calling register_student tool.** "
                "**PRIORITY 11: NEVER ask for WhatsApp number (wa_id) as it is automatically collected from the WhatsApp API. When user confirms their information with 'yes', proceed directly to registration using the wa_id from their state.** "
                "Do not make up information. If you lack information for a tool, ask for it clearly. "
                "Be friendly, encouraging, and provide thorough answers in the user's language.\n\n"
                "--- Available Tools ---\n"
                "{tool_descriptions}\n"
                "-----------------------\n\n"
            )

            # Obtenir les descriptions des outils avant de formater le prompt système
            tool_descriptions_for_prompt = self.tool_manager.get_tool_descriptions("fr")

            # Formater le prompt système avec les descriptions des outils
            system_prompt = initial_system_context_template.format(
                tool_descriptions=tool_descriptions_for_prompt
            )

            # Ajouter le prompt système
            gemini_history.append({
                "role": "user",
                "parts": [system_prompt]
            })

            # Ajouter l'historique de conversation depuis la collection registrations
            for conv in conversation_history:
                role = "user" if conv["role"] == "user" else "model"
                gemini_history.append({
                    "role": role,
                    "parts": [conv["message"]]
                })

            try:
                self.chats[wa_id] = model.start_chat(history=gemini_history)
                logging.info(f"Chat restored for {wa_id} with {len(conversation_history)} previous messages 🤖💬.")
            except Exception as e:
                logging.error(f"Error starting chat for {wa_id}: {str(e)}")
                raise

        return self.chats[wa_id]

    def save_message_to_db(self, user_id: str, role: str, message: str, metadata: Dict = None):
        """Sauvegarde un message dans la base de données (collection registrations)."""
        success = self.db_service.save_conversation_message(user_id, role, message, metadata)
        if not success:
            logging.error(f"Failed to save message to database for user {user_id}")

    def clear_user_conversation(self, user_id: str) -> bool:
        """Efface l'historique de conversation d'un utilisateur."""
        success = self.db_service.delete_conversation_history(user_id)
        if success and user_id in self.chats:
            del self.chats[user_id]  # Supprimer aussi de la mémoire
        return success

    def get_user_conversation_stats(self, user_id: str) -> Dict:
        """Récupère les statistiques de conversation pour un utilisateur."""
        return self.db_service.get_conversation_stats(user_id)

    def get_user_full_profile(self, user_id: str) -> Optional[Dict]:
        """Récupère le profil complet de l'utilisateur avec conversations."""
        return self.db_service.get_user_profile_with_conversations(user_id)

    def cleanup_old_conversations(self, days_to_keep: int = 30) -> int:
        """Nettoie les anciennes conversations."""
        return self.db_service.cleanup_old_conversations(days_to_keep)

    def process_tool_calls_from_text(self, text: str, user_id: str) -> tuple[str, Optional[str]]:
        """Extrait et exécute les appels d'outils d'une chaîne de texte donnée."""
        # Enhanced regex pattern to catch tool calls more reliably
        tool_call_pattern = r'\{\{([a-zA-Z_]+)(?::([^}]+))?\}\}'
        matches = list(re.finditer(tool_call_pattern, text))
        
        # Also check for single brace pattern
        if not matches:
            tool_call_pattern = r'\{([a-zA-Z_]+)(?::([^}]+))?\}'
            matches = list(re.finditer(tool_call_pattern, text))
        
        tool_execution_results = []
        clean_text_parts = []
        last_idx = 0

        for match in matches:
            tool_call_str = match.group(0)
            tool_name = match.group(1)
            args_str = match.group(2) if len(match.groups()) > 1 and match.group(2) else ""

            parsed_args = []
            if args_str:
                for arg_item in args_str.split(','):
                    arg_item = arg_item.strip()
                    if '=' in arg_item:
                        parts = arg_item.split('=', 1)
                        if len(parts) == 2:
                            value = parts[1].strip().strip('"\'') 
                            parsed_args.append(value)
                        else:
                            parsed_args.append("")
                    else:
                        parsed_args.append(arg_item)
            
            args = parsed_args 

            tool = self.tool_manager.get_tool(tool_name)
            if tool:
                try:
                    if tool_name == "set_user_step":
                        raw_result = tool.execute(user_id, *args)
                    elif tool_name in ["get_user_step", "advance_to_next_step"]:
                        raw_result = tool.execute(user_id)
                    elif tool_name == "update_user_info":
                        raw_result = tool.execute(*args)  # wa_id est déjà dans args
                    elif tool_name == "register_student":
                        if len(args) == 6:  # Si on a les 6 arguments de base
                            raw_result = tool.execute(*args, user_id)  # Ajouter le wa_id comme 7ème argument
                        elif len(args) == 7:  # Si l'IA a déjà inclus le wa_id
                            raw_result = tool.execute(*args)  # Utiliser les 7 arguments tels quels
                        else:
                            raw_result = f"Error: register_student requires 6 arguments (location, first_name, last_name, email, phone, age) plus wa_id, but received {len(args)} from tool call '{tool_call_str}' parsed as: {args}."
                    elif tool_name == "get_program_details":
                        if len(args) == 1:
                            program_name_and_location = args[0]
                            raw_result = tool.execute(program_name_and_location)
                        else:
                            raw_result = f"Error: get_program_details requires 1 argument (program_name_and_location), but received {len(args)} from tool call '{tool_call_str}'."
                    elif tool_name == "verify_registration_info":
                        if len(args) == 6:  # Si on a les 6 arguments de base
                            raw_result = tool.execute(*args, user_id)  # Ajouter le wa_id comme 7ème argument
                        elif len(args) == 7:  # Si l'IA a déjà inclus le wa_id
                            raw_result = tool.execute(*args)  # Utiliser les 7 arguments tels quels
                        else:
                            raw_result = f"Error: verify_registration_info requires 6 arguments (location, first_name, last_name, email, phone, age) plus wa_id, but received {len(args)} from tool call '{tool_call_str}' parsed as: {args}."
                    elif tool_name == "check_user_registration":
                        # Cet outil n'a besoin que du wa_id, qui est le user_id
                        raw_result = tool.execute(user_id)
                    else:
                        raw_result = tool.execute(*args)

                    if tool_name in ["set_user_step", "advance_to_next_step", "update_user_info"]:
                        if isinstance(raw_result, str) and raw_result.startswith("Error:"):
                            result_for_ai = f"Internal_Error: Step management failed for {tool_name} with result: {raw_result}"
                        elif isinstance(raw_result, str) and (raw_result.startswith("Successfully") or raw_result.startswith("Already at final step") or raw_result.startswith("User info")):
                            result_for_ai = f"Internal_Status: {raw_result}"
                        else:
                            result_for_ai = f"Internal_Status: Step tool {tool_name} returned unexpected result: {raw_result}"
                    else:
                        result_for_ai = raw_result

                    tool_execution_results.append(result_for_ai)
                    logging.info(f"Tool {tool_name} executed successfully")
                    
                except Exception as ex:
                    logging.error(f"Error executing tool {tool_name} with args {args}: {ex}")
                    tool_execution_results.append(f"Internal_Error: Exception during tool '{tool_name}' execution: {str(ex)}")
            else:
                logging.warning(f"Attempted to call unknown tool: {tool_name}")
                tool_execution_results.append(f"Error: Tool '{tool_name}' not found.")

            clean_text_parts.append(text[last_idx:match.start()])
            last_idx = match.end()

        clean_text_parts.append(text[last_idx:])
        clean_text = "".join(clean_text_parts).strip()
        combined_tool_result = "\n".join(tool_execution_results) if tool_execution_results else None

        return clean_text, combined_tool_result

    def set_user_step(self, *, user_id: str, step: str) -> str:
        """Définit l'étape actuelle pour un utilisateur.
        
        Args:
            user_id: L'ID de l'utilisateur
            step: Le nom de l'étape à définir
            
        Returns:
            str: Message de confirmation ou d'erreur
        """
        try:
            # Nettoyage des arguments
            user_id = str(user_id).strip()
            step = str(step).strip()
            
            if not user_id or not step:
                return "Erreur : L'ID utilisateur et l'étape sont requis"
            
            if step not in self.ordered_steps:
                return f"Erreur : Étape '{step}' invalide. Les étapes valides sont : {', '.join(self.ordered_steps)}"
            
            state = self.get_user_state(user_id)
            state["current_step"] = step
            self._save_user_state(user_id)
            
            logging.info(f"Étape définie pour l'utilisateur {user_id} : {step}")
            return f"Étape définie sur : {step}"
            
        except Exception as e:
            logging.error(f"Erreur lors de la définition de l'étape pour l'utilisateur {user_id}: {str(e)}")
            return f"Erreur lors de la définition de l'étape : {str(e)}"

# Instance globale du gestionnaire de conversation
conversation_manager = ConversationManager() 
conversation_manager.generation_config = generation_config