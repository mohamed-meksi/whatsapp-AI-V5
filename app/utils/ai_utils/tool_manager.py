import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable
from .tool import Tool

class ToolManager:
    """Gère la collection d'outils disponibles et leur enregistrement."""
    def __init__(self, conversation_manager):
        self.conversation_manager = conversation_manager
        self.tools: Dict[str, Tool] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        """Enregistre les outils de base que l'IA peut utiliser."""
        from services.database_service import db_service

        self.register_tool("get_user_step", self.conversation_manager.get_current_step,
                            {"en": "Get the user's current conversation step.",
                             "fr": "Obtenir l'étape actuelle de la conversation de l'utilisateur.",
                             "ar": "الحصول على خطوة المحادثة الحالية للمستخدم."})
        
        self.register_tool("set_user_step", self.conversation_manager.set_current_step,
                            {"en": "Explicitly set the user's current conversation step. (args: user_id: str, step_name: str)",
                             "fr": "Définir explicitement l'étape actuelle de la conversation de l'utilisateur. (arguments: user_id: str, nom_etape: str)",
                             "ar": "تعيين خطوة المحادثة الحالية للمستخدم بشكل صريح. (الحجج: user_id: str, اسم_الخطوة: str)"})
        
        self.register_tool("advance_to_next_step", self.conversation_manager.advance_step,
                            {"en": "Advance the user to the next logical step in the conversation flow.",
                             "fr": "Faire avancer l'utilisateur à l'étape logique suivante dans le flux de conversation.",
                             "ar": "الانتقال بالمستخدم إلى الخطوة المنطقية التالية في مسار المحادثة."})

        self.register_tool("update_user_info", self.conversation_manager.update_user_info,
                            {"en": "Update a specific piece of user information (e.g., program, level, full_name, email). (args: user_id: str, field: str, value: str)",
                             "fr": "Mettre à jour une information spécifique de l'utilisateur (ex: programme, niveau, nom_complet, email). (arguments: user_id: str, champ: str, valeur: str)",
                             "ar": "تحديث معلومة محددة للمستخدم (مثال: البرنامج، المستوى، الاسم_الكامل، البريد_الإلكتروني). (الحجج: user_id: str, الحقل: str, القيمة: str)"})

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

        def get_bootcamp_info_func():
            return db_service.format_program_info_for_chat()

        def register_student_func(wa_id: str, location: str, first_name: str, last_name: str, email: str, phone: str, age: str):
            try:
                # Vérification d'inscription préalable avec le wa_id
                if self.conversation_manager.is_user_registered(wa_id):
                    detected_language = self.conversation_manager.detected_language
                    if detected_language == "fr":
                        return "Vous êtes déjà inscrit(e). Il n'est pas possible de s'inscrire une deuxième fois."
                    elif detected_language == "ar":
                        return "أنت مسجل بالفعل. لا يمكن التسجيل مرة أخرى."
                    else:
                        return "You are already registered. It is not possible to register again."

                age_int = int(age)
                program = db_service.get_program_by_location(location)
                if not program:
                    raise ValueError("Program/Session not found for the specified location.")

                result = db_service.register_student(
                    program['id'],
                    first_name,
                    last_name,
                    email,
                    phone,
                    age_int,
                    wa_id  # Ajout du wa_id à la base de données
                )

                detected_language = self.conversation_manager.detected_language
                if detected_language == "fr":
                     return (f"Inscription réussie pour {first_name} {last_name} "
                             f"au programme de {result.get('location_name', 'N/A')}. Places restantes : {result['spots_remaining']}.")
                elif detected_language == "ar":
                     return (f"تم التسجيل بنجاح لـ {first_name} {last_name} "
                             f"في برنامج {result.get('location_name', 'N/A')}. الأماكن المتبقية: {result['spots_remaining']}.")
                else: # English default
                    return (f"Registration successful for {first_name} {last_name} "
                            f"in {result.get('location_name', 'N/A')} program. Spots remaining: {result['spots_remaining']}.")

            except ValueError as ve:
                detected_language = self.conversation_manager.detected_language
                error_message = str(ve)
                
                if "Program/Session not found" in error_message:
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
                        return "فشل التسجيل: لا توجد أماكن متاحة لهذا programme."
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
            parts = [p.strip() for p in program_name_and_location.split('-', 1)]
            program_name_search = parts[0]
            location_search = parts[1] if len(parts) > 1 else None

            program = None
            if program_name_search and location_search:
                program = db_service.get_program_by_name_and_location(program_name_search, location_search)
            elif program_name_search:
                programs_found = db_service.search_programs(program_name_search)
                if programs_found:
                    program = programs_found[0]

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
            {"en": "Register a new student for a bootcamp program. Expects full name, email, phone, and age. (args: location: str, first_name: str, last_name: str, email: str, phone: str, age: str)",
             "fr": "Inscrire un nouvel étudiant à un programme de bootcamp. Attend le nom complet, l'email, le téléphone et l'âge. (arguments: location: str, first_name: str, last_name: str, email: str, phone: str, age: str)",
             "ar": "تسجيل طالب جديد في برنامج المعسكر التدريبي. يتطلب الاسم الكامل، البريد الإلكتروني، الهاتف، والعمر. (الحجج: location: str, first_name: str, last_name: str, email: str, phone: str, age: str)"})
        
        self.register_tool("search_programs", search_programs_func, 
            {"en": "Search for bootcamp programs by a given search term (e.g., program name, city). Returns JSON. (args: search_term: str)",
             "fr": "Rechercher des programmes de bootcamp par un terme de recherche donné (par exemple, nom de programme, ville). Retourne du JSON. (arguments: search_term: str)",
             "ar": "البحث عن برامج المعسكر التدريبي حسب مصطلح بحث معين (مثل اسم الموقع، المدينة). تعيد JSON. (الحجج: search_term: str)"})

    def register_tool(self, name: str, func: Callable, description: Dict[str, str]):
        self.tools[name] = Tool(name, func, description)

    def get_tool(self, name: str) -> Optional[Tool]:
        return self.tools.get(name)

    def get_tool_descriptions(self, lang: str = "en") -> str:
        tools_list = []
        for name, tool in self.tools.items():
            tools_list.append(f"- `{name}`: {tool.get_description(lang)}")
        return "\n".join(tools_list) 