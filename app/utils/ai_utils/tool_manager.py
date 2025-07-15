import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, Tuple, List, Any
from .tool import Tool
import re

class ToolManager:
    """Gère la collection d'outils disponibles et leur enregistrement."""
    def __init__(self, conversation_manager):
        self.conversation_manager = conversation_manager
        self.tools: Dict[str, Tool] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        """Enregistre les outils de base que l'IA peut utiliser."""
        from services.database_service import db_service

        # Register basic conversation management tools first
        self.register_tool(
            "get_user_step",
            self.conversation_manager.get_current_step,
            {
                "en": "Get the user's current conversation step.",
                "fr": "Obtenir l'étape actuelle de la conversation de l'utilisateur.",
                "ar": "الحصول على خطوة المحادثة الحالية للمستخدم."
            }
        )
        
        # Fonction wrapper pour set_user_step qui force l'utilisation des arguments nommés
        def set_user_step_wrapper(**kwargs):
            if 'user_id' not in kwargs or 'step' not in kwargs:
                raise ValueError("Les arguments 'user_id' et 'step' sont requis")
            return self.conversation_manager.set_user_step(user_id=kwargs['user_id'], step=kwargs['step'])
        
        # Enregistrement de set_user_step avec le wrapper
        self.register_tool("set_user_step", 
            set_user_step_wrapper,
            {"en": "Set the current step for a user in the conversation flow. Format: {set_user_step:user_id=USER_ID, step=STEP_NAME}",
             "fr": "Définir l'étape actuelle pour un utilisateur dans le flux de conversation. Format: {set_user_step:user_id=USER_ID, step=STEP_NAME}",
             "ar": "تعيين الخطوة الحالية للمستخدم في تدفق المحادثة. Format: {set_user_step:user_id=USER_ID, step=STEP_NAME}"})
        
        self.register_tool("advance_to_next_step", self.conversation_manager.advance_step,
                            {"en": "Advance the user to the next logical step in the conversation flow.",
                             "fr": "Faire avancer l'utilisateur à l'étape logique suivante dans le flux de conversation.",
                             "ar": "الانتقال بالمستخدم إلى الخطوة المنطقية التالية في مسار المحادثة."})

        self.register_tool("update_user_info", 
            lambda wa_id, field, value: self.conversation_manager.update_user_info(wa_id, field, value),
            {"en": "Update a specific piece of user information (e.g., program, level, full_name, email). (args: wa_id: str, field: str, value: str)",
             "fr": "Mettre à jour une information spécifique de l'utilisateur (ex: programme, niveau, nom_complet, email). (arguments: wa_id: str, champ: str, valeur: str)",
             "ar": "تحديث معلومة محددة للمستخدم (مثال: البرنامج، المستوى، الاسم_الكامل، البريد_الإلكتروني). (الحجج: wa_id: str, الحقل: str, القيمة: str)"})

        # Define all the function implementations first
        def get_available_sessions_func():
            programs = db_service.get_all_programs() 
            if not programs:
                return json.dumps({"status": "no_programs_available"})

            formatted_programs = []
            for program in programs:
                start_date = program.get('start_date')
                if isinstance(start_date, str):
                    try:
                        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    except ValueError:
                        start_date = None

                end_date_str = "N/A"
                if start_date and program.get('duration_months'):
                    end_date = start_date + timedelta(days=program['duration_months'] * 30) 
                    end_date_str = end_date.strftime('%Y-%m-%d')

                formatted_programs.append({
                    "id": program.get('id'),
                    "program_name": program.get('program_name'),
                    "location": program.get('location'),
                    "start_date": start_date.strftime('%Y-%m-%d') if start_date else 'N/A',
                    "end_date": end_date_str,
                    "duration_months": program.get('duration_months'),
                    "price": float(program.get('price', 0)),
                    "available_spots": program.get('available_spots', 0),
                    "description": program.get('description')
                })
            return json.dumps({"status": "success", "programs": formatted_programs}, indent=2)

        def get_bootcamp_info_func(program_name: str = None, location: str = None):
            """Obtient les informations d'un bootcamp spécifique ou de tous les bootcamps.
            
            Args:
                program_name: Nom du programme (optionnel)
                location: Lieu du programme (optionnel)
            """
            try:
                if program_name and location:
                    # Chercher un programme spécifique
                    program = db_service.get_program_by_name_and_location(program_name, location)
                    if program:
                        # Convertir les dates en chaînes de caractères
                        if isinstance(program.get('start_date'), datetime):
                            program['start_date'] = program['start_date'].strftime('%Y-%m-%d')
                        if isinstance(program.get('created_at'), datetime):
                            program['created_at'] = program['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                        if isinstance(program.get('updated_at'), datetime):
                            program['updated_at'] = program['updated_at'].strftime('%Y-%m-%d %H:%M:%S')
                        
                        return json.dumps({"status": "success", "program": program}, ensure_ascii=False, indent=2)
                    return json.dumps({"status": "not_found"})
                
                # Si aucun paramètre n'est fourni, retourner tous les programmes (format texte)
                return db_service.format_program_info_for_chat()
                
            except Exception as e:
                logging.error(f"Error in get_bootcamp_info_func: {str(e)}")
                return json.dumps({"status": "error", "message": str(e)})

        def verify_registration_info_func(location: str, first_name: str, last_name: str, email: str, phone: str, age: str, wa_id: str) -> str:
            """Vérifie les informations d'inscription d'un étudiant et procède à l'inscription si tout est correct.
            
            Args:
                location: Lieu du programme
                first_name: Prénom
                last_name: Nom
                email: Adresse email
                phone: Numéro de téléphone
                age: Âge
                wa_id: ID WhatsApp
            """
            # Vérifier si toutes les informations sont présentes
            missing_info = []
            if not email or email == "?":
                missing_info.append("email")
            if not phone or phone == "?":
                missing_info.append("téléphone")
            if not age or age == "?":
                missing_info.append("âge")
            
            if missing_info:
                return f"Il manque les informations suivantes : {', '.join(missing_info)}"
            
            # Vérifier le format de l'email
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                return "L'adresse email n'est pas valide."
            
            # Vérifier le format du numéro de téléphone
            if not re.match(r"^\+?[0-9]{10,}$", phone):
                return "Le numéro de téléphone n'est pas valide."
            
            # Vérifier l'âge
            try:
                age_int = int(age)
                if age_int < 18 or age_int > 100:
                    return "L'âge doit être compris entre 18 et 100 ans."
            except ValueError:
                return "L'âge doit être un nombre entier."
            
            # Si toutes les vérifications sont OK, procéder à l'inscription
            try:
                return register_student_func(location, first_name, last_name, email, phone, age, wa_id)
            except Exception as e:
                logging.error(f"Erreur lors de l'inscription après vérification : {str(e)}")
                return f"Une erreur est survenue lors de l'inscription : {str(e)}"

        def register_student_func(location: str, first_name: str, last_name: str, email: str, phone: str, age: str, wa_id: str):
            try:
                age_int = int(age)

                # Récupérer l'état de l'utilisateur pour vérifier la location
                user_state = self.conversation_manager.get_user_state(wa_id)
                program_info = user_state.get("program") if user_state else None
                stored_location = program_info.get("location", location) if program_info else location
                
                # Utiliser la location stockée si elle existe
                program_location = stored_location if stored_location else location

                # Trouver le programme par lieu
                program = db_service.get_program_by_location(program_location)
                if not program:
                    raise ValueError("Programme introuvable pour le lieu spécifié.")

                # Procéder à l'inscription
                result = db_service.register_student(
                    program['id'],
                    first_name,
                    last_name,
                    email,
                    phone,
                    age_int,
                    wa_id
                )

                # Si l'inscription est réussie, result contiendra les détails de l'inscription
                detected_language = self.conversation_manager.detected_language
                if detected_language == "fr":
                    return (f"✅ Félicitations ! Votre inscription a été confirmée.\n\n"
                           f"📝 Détails de l'inscription :\n"
                           f"- Nom : {first_name} {last_name}\n"
                           f"- Programme : {program.get('program_name', 'N/A')} à {location}\n"
                           f"- Email : {email}\n"
                           f"- Téléphone : {phone}\n"
                           f"- Places restantes : {result.get('spots_remaining', 0)}\n\n"
                           f"📧 Vous recevrez bientôt un email avec plus d'informations.")
                elif detected_language == "ar":
                    return (f"✅ تهانينا! تم تأكيد تسجيلك.\n\n"
                           f"📝 تفاصيل التسجيل:\n"
                           f"- الاسم: {first_name} {last_name}\n"
                           f"- البرنامج: {program.get('program_name', 'N/A')} في {location}\n"
                           f"- البريد الإلكتروني: {email}\n"
                           f"- الهاتف: {phone}\n"
                           f"- الأماكن المتبقية: {result.get('spots_remaining', 0)}\n\n"
                           f"📧 ستتلقى قريباً بريداً إلكترونياً يحتوي على مزيد من المعلومات.")
                else:
                    return (f"✅ Congratulations! Your registration has been confirmed.\n\n"
                           f"📝 Registration details:\n"
                           f"- Name: {first_name} {last_name}\n"
                           f"- Program: {program.get('program_name', 'N/A')} in {location}\n"
                           f"- Email: {email}\n"
                           f"- Phone: {phone}\n"
                           f"- Spots remaining: {result.get('spots_remaining', 0)}\n\n"
                           f"📧 You will receive an email with more information soon.")

            except ValueError as ve:
                detected_language = self.conversation_manager.detected_language
                error_message = str(ve)
                
                if "Programme introuvable pour le lieu spécifié" in error_message:
                    if detected_language == "fr":
                        return "L'inscription a échoué : Programme introuvable pour le lieu spécifié."
                    elif detected_language == "ar":
                        return "فشل التسجيل: لم يتم العثور على برنامج للموقع المحدد."
                    else:
                        return "Registration failed: Program/Session not found for the specified location."
                
                elif "No spots available" in error_message:
                    if detected_language == "fr":
                        return "L'inscription a échoué : Plus de places disponibles pour ce programme."
                    elif detected_language == "ar":
                        return "فشل التسجيل: لا توجد أماكن متاحة لهذا البرنامج."
                    else:
                        return "Registration failed: No spots available for this program."
                
                elif "Email already registered" in error_message:
                    if detected_language == "fr":
                        return "L'inscription a échoué : Cet e-mail est déjà enregistré."
                    elif detected_language == "ar":
                        return "فشل التسجيل: البريد الإلكتروني مسجل بالفعل."
                    else:
                        return "Registration failed: Email already registered."
                
                elif "Age must be a valid number" in error_message:
                    if detected_language == "fr":
                        return "L'inscription a échoué : L'âge doit être un nombre valide."
                    elif detected_language == "ar":
                        return "فشل التسجيل: يجب أن يكون العمر رقماً صالحاً."
                    else:
                        return "Registration failed: Age must be a valid number."
                
                else:
                    if detected_language == "fr":
                        return f"L'inscription a échoué : {error_message}"
                    elif detected_language == "ar":
                        return f"فشل التسجيل: {error_message}"
                    else:
                        return f"Registration failed: {error_message}"
                    
            except Exception as e:
                logging.error(f"An unexpected error occurred during registration: {e}")
                detected_language = self.conversation_manager.detected_language
                if detected_language == "fr":
                    return f"Une erreur inattendue est survenue lors de l'inscription : {str(e)}"
                elif detected_language == "ar":
                    return f"حدث خطأ غير متوقع أثناء التسجيل: {str(e)}"
                else:
                    return f"An unexpected error occurred during registration: {str(e)}"

        def get_program_details_func(program_name_and_location: str):
            # Accepter soit le tiret soit les deux-points comme séparateur
            parts = [p.strip() for p in program_name_and_location.replace(':', '-').split('-', 1)]
            
            # Si on n'a qu'une partie (pas de séparateur), essayer de trouver le programme par location
            if len(parts) == 1:
                location_search = parts[0]
                program = db_service.get_program_by_location(location_search)
            else:
                program_name_search = parts[0]
                location_search = parts[1]
                program = db_service.get_program_by_name_and_location(program_name_search, location_search)

            if not program:
                return json.dumps({"status": "not_found", "search_term": program_name_and_location})
            
            start_date = program.get('start_date')
            if isinstance(start_date, str):
                try:
                    start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                except ValueError:
                    start_date = None

            end_date_str = "N/A"
            if start_date and program.get('duration_months'):
                end_date = start_date + timedelta(days=program['duration_months'] * 30) 
                end_date_str = end_date.strftime('%Y-%m-%d')

            return json.dumps({
                'status': 'success',
                'program_name': program.get('program_name'),
                'location': program.get('location'),
                'start_date': start_date.strftime('%Y-%m-%d') if start_date else 'N/A',
                'end_date': end_date_str,
                'duration_months': program.get('duration_months'),
                'price': float(program.get('price', 0)),
                'available_spots': program.get('available_spots', 0),
                'description': program.get('description'),
                'requirements': program.get('requirements')
            }, indent=2)

        def search_programs_func(search_term: str): 
            programs = db_service.search_programs(search_term)
            if not programs:
                return json.dumps({"status": "no_programs_found", "search_term": search_term})
            
            results = []
            for program in programs:
                start_date = program.get('start_date')
                if isinstance(start_date, str):
                    try:
                        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    except ValueError:
                        start_date = None

                end_date_str = "N/A"
                if start_date and program.get('duration_months'):
                    end_date = start_date + timedelta(days=program['duration_months'] * 30)
                    end_date_str = end_date.strftime('%Y-%m-%d')

                results.append({
                    'program_name': program.get('program_name'),
                    'location': program.get('location'),
                    'start_date': start_date.strftime('%Y-%m-%d') if start_date else 'N/A',
                    'end_date': end_date_str,
                    'price': float(program.get('price', 0)),
                    'available_spots': program.get('available_spots', 0)
                })
            return json.dumps({"status": "success", "programs": results}, indent=2)

        def verify_user_info_func(wa_id: str) -> str:
            """Vérifie et retourne les informations de l'utilisateur pour confirmation.
            
            Args:
                wa_id: L'ID WhatsApp de l'utilisateur
            """
            verification = self.conversation_manager.verify_user_information(wa_id)
            
            if not verification["is_complete"]:
                missing = ", ".join(verification["missing_fields"])
                if self.conversation_manager.detected_language == "fr":
                    return f"Il manque les informations suivantes : {missing}"
                elif self.conversation_manager.detected_language == "ar":
                    return f"المعلومات الناقصة: {missing}"
                else:
                    return f"Missing information: {missing}"
            
            info = verification["user_info"]
            if self.conversation_manager.detected_language == "fr":
                return (
                    f"Veuillez vérifier vos informations :\n"
                    f"- Nom complet : {info['full_name']}\n"
                    f"- Email : {info['email']}\n"
                    f"- Téléphone : {info['phone']}\n"
                    f"- Âge : {info['age']}\n\n"
                    f"Ces informations sont-elles correctes ? Répondez par 'oui' pour confirmer ou 'non' pour les modifier."
                )
            elif self.conversation_manager.detected_language == "ar":
                return (
                    f"يرجى التحقق من معلوماتك:\n"
                    f"- الاسم الكامل: {info['full_name']}\n"
                    f"- البريد الإلكتروني: {info['email']}\n"
                    f"- الهاتف: {info['phone']}\n"
                    f"- العمر: {info['age']}\n\n"
                    f"هل هذه المعلومات صحيحة؟ أجب بـ 'نعم' للتأكيد أو 'لا' للتعديل."
                )
            else:
                return (
                    f"Please verify your information:\n"
                    f"- Full name: {info['full_name']}\n"
                    f"- Email: {info['email']}\n"
                    f"- Phone: {info['phone']}\n"
                    f"- Age: {info['age']}\n\n"
                    f"Is this information correct? Reply with 'yes' to confirm or 'no' to modify."
                )

        def check_user_registration_func(wa_id: str) -> str:
            """Vérifie si un utilisateur est déjà inscrit et bloque l'étape collect_personal_info si nécessaire."""
            try:
                registration = db_service.get_user_registration_by_wa_id(wa_id)
                
                if not registration:
                    # L'utilisateur n'est pas inscrit, continuer normalement
                    detected_language = self.conversation_manager.detected_language
                    if detected_language == "fr":
                        return "NOUVELLE_INSCRIPTION: L'utilisateur n'est pas encore inscrit. Continuer la collecte d'informations."
                    elif detected_language == "ar":
                        return "تسجيل_جديد: المستخدم غير مسجل بعد. متابعة جمع المعلومات."
                    else:
                        return "NEW_REGISTRATION: User is not yet registered. Continue collecting information."
                
                # L'utilisateur est déjà inscrit, bloquer l'étape collect_personal_info
                detected_language = self.conversation_manager.detected_language
                program_info = registration.get("program_info", {})
                
                # Changer l'étape vers already_registered pour bloquer collect_personal_info
                self.conversation_manager.set_current_step(wa_id, "already_registered")
                
                if detected_language == "fr":
                    return (
                        f"🚫 **COLLECTE D'INFORMATIONS BLOQUÉE** 🚫\n\n"
                        f"Vous êtes déjà inscrit à notre programme !\n\n"
                        f"📋 **Vos informations d'inscription :**\n"
                        f"• **Nom :** {registration.get('first_name', 'N/A')} {registration.get('last_name', 'N/A')}\n"
                        f"• **Email :** {registration.get('email', 'N/A')}\n"
                        f"• **Téléphone :** {registration.get('phone', 'N/A')}\n"
                        f"• **Âge :** {registration.get('age', 'N/A')} ans\n"
                        f"• **Programme :** {program_info.get('program_name', 'N/A')}\n"
                        f"• **Lieu :** {program_info.get('location', 'N/A')}\n"
                        f"• **Date d'inscription :** {registration.get('registration_date', 'N/A')}\n"
                        f"• **Statut :** {registration.get('status', 'N/A')}\n\n"
                        f"✅ **Votre inscription est déjà confirmée !**\n\n"
                        f"🎓 Comment puis-je vous aider aujourd'hui ?\n"
                        f"💬 Vous pouvez me demander des informations sur :\n"
                        f"• Les détails du programme\n"
                        f"• Les dates de début\n"
                        f"• L'emplacement des cours\n"
                        f"• Toute autre question"
                    )
                elif detected_language == "ar":
                    return (
                        f"🚫 **تم حظر جمع المعلومات** 🚫\n\n"
                        f"أنت مسجل بالفعل في برنامجنا!\n\n"
                        f"📋 **معلومات التسجيل الخاصة بك:**\n"
                        f"• **الاسم:** {registration.get('first_name', 'N/A')} {registration.get('last_name', 'N/A')}\n"
                        f"• **البريد الإلكتروني:** {registration.get('email', 'N/A')}\n"
                        f"• **الهاتف:** {registration.get('phone', 'N/A')}\n"
                        f"• **العمر:** {registration.get('age', 'N/A')} سنة\n"
                        f"• **البرنامج:** {program_info.get('program_name', 'N/A')}\n"
                        f"• **المكان:** {program_info.get('location', 'N/A')}\n"
                        f"• **تاريخ التسجيل:** {registration.get('registration_date', 'N/A')}\n"
                        f"• **الحالة:** {registration.get('status', 'N/A')}\n\n"
                        f"✅ **تم تأكيد تسجيلك بالفعل!**\n\n"
                        f"🎓 كيف يمكنني مساعدتك اليوم؟\n"
                        f"💬 يمكنك أن تسألني عن:\n"
                        f"• تفاصيل البرنامج\n"
                        f"• تواريخ البدء\n"
                        f"• موقع الدروس\n"
                        f"• أي أسئلة أخرى"
                    )
                else:
                    return (
                        f"🚫 **INFORMATION COLLECTION BLOCKED** 🚫\n\n"
                        f"You are already registered in our program!\n\n"
                        f"📋 **Your registration information:**\n"
                        f"• **Name:** {registration.get('first_name', 'N/A')} {registration.get('last_name', 'N/A')}\n"
                        f"• **Email:** {registration.get('email', 'N/A')}\n"
                        f"• **Phone:** {registration.get('phone', 'N/A')}\n"
                        f"• **Age:** {registration.get('age', 'N/A')} years\n"
                        f"• **Program:** {program_info.get('program_name', 'N/A')}\n"
                        f"• **Location:** {program_info.get('location', 'N/A')}\n"
                        f"• **Registration date:** {registration.get('registration_date', 'N/A')}\n"
                        f"• **Status:** {registration.get('status', 'N/A')}\n\n"
                        f"✅ **Your registration is already confirmed!**\n\n"
                        f"🎓 How can I help you today?\n"
                        f"💬 You can ask me about:\n"
                        f"• Program details\n"
                        f"• Start dates\n"
                        f"• Class location\n"
                        f"• Any other questions"
                    )
                    
            except Exception as e:
                logging.error(f"Error checking user registration for wa_id {wa_id}: {str(e)}")
                detected_language = self.conversation_manager.detected_language
                if detected_language == "fr":
                    return f"ERREUR: Impossible de vérifier l'inscription : {str(e)}"
                elif detected_language == "ar":
                    return f"خطأ: تعذر التحقق من التسجيل: {str(e)}"
                else:
                    return f"ERROR: Unable to check registration: {str(e)}"

        # Register all the defined functions as tools
        self.register_tool("verify_registration_info", verify_registration_info_func,
            {"en": "Verify registration information before proceeding with student registration. (args: location: str, first_name: str, last_name: str, email: str, phone: str, age: str, wa_id: str)",
             "fr": "Vérifier les informations d'inscription avant de procéder à l'inscription de l'étudiant. (arguments: location: str, first_name: str, last_name: str, email: str, phone: str, age: str, wa_id: str)",
             "ar": "التحقق من معلومات التسجيل قبل المتابعة في تسجيل الطالب. (الحجج: location: str, first_name: str, last_name: str, email: str, phone: str, age: str, wa_id: str)"})

        self.register_tool("get_bootcamp_info", get_bootcamp_info_func,
            {"en": "Get detailed information about our bootcamp programs (curriculum, duration, requirements, price, locations).",
             "fr": "Obtenir des informations détaillées sur nos programmes de bootcamp (programme, durée, exigences, prix, lieux).",
             "ar": "الحصول على معلومات مفصلة حول برامج المعسكر التدريبي لدينا (المنهج الدراسي، المدة، المتطلبات، السعر، المواقع)."})
        
        self.register_tool("get_available_sessions", get_available_sessions_func,
            {"en": "Get a formatted list of all available bootcamp programs with start dates, locations, and available spots.",
             "fr": "Obtenir une liste formatée de tous les programmes de bootcamp disponibles avec les dates de début, les lieux et les places disponibles.",
             "ar": "الحصول على قائمة منسقة بجميع برامج المعسكر التدريبي المتاحة مع تواريخ البدء والمواقع والأماكن المتاحة."})
        
        self.register_tool("get_program_details", get_program_details_func,
            {"en": "Get detailed information for a specific program by its name and location (e.g., 'Full Stack Web Development - Casablanca'). Returns JSON. (args: program_name_and_location: str)",
             "fr": "Obtenir des informations détaillées pour un programme spécifique par son nom et son lieu (ex: 'Développement Web Full Stack - Casablanca'). Retourne du JSON. (arguments: nom_programme_et_lieu: str)",
             "ar": "الحصول على معلومات مفصلة لبرنامج معين حسب اسمه وموقعه (مثال: 'تطوير الويب الكامل - الدار البيضاء'). تعيد JSON. (الحجج: اسم_البرنامج_والموقع: str)"})
        
        self.register_tool("register_student", register_student_func,
            {"en": "Register a new student for a bootcamp program. Expects full name, email, phone, age and WhatsApp ID. (args: location: str, first_name: str, last_name: str, email: str, phone: str, age: str, wa_id: str)",
             "fr": "Inscrire un nouvel étudiant à un programme de bootcamp. Attend le nom complet, l'email, le téléphone, l'âge et l'ID WhatsApp. (arguments: location: str, first_name: str, last_name: str, email: str, phone: str, age: str, wa_id: str)",
             "ar": "تسجيل طالب جديد في برنامج المعسكر التدريبي. يتطلب الاسم الكامل، البريد الإلكتروني، الهاتف، العمر ومعرف واتساب. (الحجج: location: str, first_name: str, last_name: str, email: str, phone: str, age: str, wa_id: str)"})
        
        self.register_tool("search_programs", search_programs_func, 
            {"en": "Search for bootcamp programs by a given search term (e.g., program name, city). Returns JSON. (args: search_term: str)",
             "fr": "Rechercher des programmes de bootcamp par un terme de recherche donné (par exemple, nom de programme, ville). Retourne du JSON. (arguments: search_term: str)",
             "ar": "البحث عن برامج المعسكر التدريبي حسب مصطلح بحث معين (مثل اسم الموقع، المدينة). تعيد JSON. (الحجج: search_term: str)"})

        self.register_tool("verify_user_info", verify_user_info_func,
            {"en": "Verify user information before registration. (args: wa_id: str)",
             "fr": "Vérifier les informations de l'utilisateur avant l'inscription. (arguments: wa_id: str)",
             "ar": "التحقق من معلومات المستخدم قبل التسجيل. (الحجج: wa_id: str)"})

        self.register_tool("check_user_registration", check_user_registration_func,
            {"en": "Check if a user is already registered when they reach 'collect_personal_info' step. Blocks information collection if already registered. (args: wa_id: str)",
             "fr": "Vérifier si un utilisateur est déjà inscrit quand il atteint l'étape 'collect_personal_info'. Bloque la collecte d'informations s'il est déjà inscrit. (arguments: wa_id: str)",
             "ar": "التحقق مما إذا كان المستخدم مسجلاً بالفعل عند وصوله لمرحلة 'collect_personal_info'. يمنع جمع المعلومات إذا كان مسجلاً. (الحجج: wa_id: str)"})

    def _parse_tool_call(self, tool_call: str) -> Tuple[str, List[Any], Dict[str, Any]]:
        """Parse un appel d'outil à partir d'une chaîne de caractères.
        
        Args:
            tool_call: La chaîne contenant l'appel d'outil
            
        Returns:
            Tuple contenant le nom de l'outil, les arguments positionnels et les arguments nommés
        """
        try:
            # Extraction du nom de l'outil et des arguments
            tool_match = re.match(r'{(\w+):(.*)}', tool_call.strip())
            if not tool_match:
                raise ValueError(f"Format d'appel d'outil invalide : {tool_call}")
                
            tool_name = tool_match.group(1)
            args_str = tool_match.group(2)
            
            # Traitement spécial pour set_user_step
            if tool_name == "set_user_step":
                # Extraction des arguments nommés uniquement
                kwargs = {}
                for arg in args_str.split(','):
                    key, value = arg.strip().split('=')
                    kwargs[key.strip()] = value.strip()
                return tool_name, [], kwargs
            
            # Traitement normal pour les autres outils
            args = []
            kwargs = {}
            
            # Parse les arguments
            for arg in args_str.split(','):
                if '=' in arg:
                    key, value = arg.strip().split('=')
                    kwargs[key.strip()] = value.strip()
                else:
                    args.append(arg.strip())
                    
            return tool_name, args, kwargs
            
        except Exception as e:
            logging.error(f"Erreur lors du parsing de l'appel d'outil : {str(e)}")
            raise ValueError(f"Erreur de parsing : {str(e)}")

    def execute_tool(self, tool_call: str) -> str:
        """Exécute un outil à partir d'une chaîne d'appel.
        
        Args:
            tool_call: La chaîne contenant l'appel d'outil
            
        Returns:
            str: Le résultat de l'exécution de l'outil
        """
        try:
            # Parse l'appel d'outil
            tool_name, args, kwargs = self._parse_tool_call(tool_call)
            
            # Vérifie si l'outil existe
            if tool_name not in self.tools:
                raise ValueError(f"Outil inconnu : {tool_name}")
                
            # Récupère l'outil
            tool = self.tools[tool_name]
            
            # Exécute l'outil avec les arguments appropriés
            if args and kwargs:
                result = tool.func(*args, **kwargs)
            elif args:
                result = tool.func(*args)
            elif kwargs:
                result = tool.func(**kwargs)
            else:
                result = tool.func()
                
            return result
            
        except Exception as e:
            logging.error(f"Erreur lors de l'exécution de l'outil : {str(e)}")
            raise RuntimeError(f"Erreur d'exécution : {str(e)}")

    def register_tool(self, name: str, func: Callable, description: Dict[str, str]):
        self.tools[name] = Tool(name, func, description)

    def get_tool(self, name: str) -> Optional[Tool]:
        return self.tools.get(name)

    def get_tool_descriptions(self, lang: str = "en") -> str:
        tools_list = []
        for name, tool in self.tools.items():
            tools_list.append(f"- `{name}`: {tool.get_description(lang)}")
        return "\n".join(tools_list)