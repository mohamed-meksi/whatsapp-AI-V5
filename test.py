import os
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
from typing import Dict, List, Optional
from datetime import datetime, timedelta

load_dotenv()

# MongoDB Configuration
MONGODB_URL = os.getenv('MONGODB_URL')
DATABASE_NAME = os.getenv('DATABASE_NAME')

class DatabaseService:
    def __init__(self):
        if not MONGODB_URL:
            raise ValueError("MONGODB_URL environment variable is not set. Please check your .env file.")
        if not DATABASE_NAME:
            raise ValueError("DATABASE_NAME environment variable is not set. Please check your .env file.")

        self.client = MongoClient(MONGODB_URL)
        self.db = self.client[DATABASE_NAME]
        self.programs_collection = self.db.programs 
        self.registrations_collection = self.db.registrations

        self._create_indexes()

    def _create_indexes(self):
        self.programs_collection.create_index([("program_name", "text"), ("location", "text")])
        self.registrations_collection.create_index("email", unique=True)
        self.registrations_collection.create_index("program_id")

    def _convert_objectid(self, doc: Dict) -> Dict:
        if doc and '_id' in doc:
            doc['id'] = str(doc['_id'])
            del doc['_id']
        return doc

    def get_all_programs(self) -> List[Dict]:
        try:
            programs = list(self.programs_collection.find({})) 
            return [self._convert_objectid(program) for program in programs]
        except Exception as e:
            print(f"Error getting all programs: {e}")
            return []

    # MODIFICATION: This function can be more precise if program_name is also provided
    def get_program_by_name_and_location(self, program_name: str, location: str) -> Optional[Dict]:
        """
        Récupère les détails du programme par nom de programme ET par lieu.
        """
        try:
            program = self.programs_collection.find_one({
                "program_name": {"$regex": program_name, "$options": "i"},
                "location": {"$regex": location, "$options": "i"}
            })
            return self._convert_objectid(program) if program else None
        except Exception as e:
            print(f"Error getting program by name and location: {e}")
            return None

    # Keep get_program_by_location if it's used elsewhere for broader searches
    def get_program_by_location(self, location_name: str) -> Optional[Dict]:
        """Récupère les détails du programme par le nom du lieu."""
        try:
            # This will still return only one if multiple programs are in the same city
            program = self.programs_collection.find_one({
                "location": {"$regex": location_name, "$options": "i"}
            })
            return self._convert_objectid(program) if program else None
        except Exception as e:
            print(f"Error getting program by location: {e}")
            return None

    def get_program_by_id(self, program_id: str) -> Optional[Dict]:
        try:
            program = self.programs_collection.find_one({"_id": ObjectId(program_id)})
            return self._convert_objectid(program) if program else None
        except Exception as e:
            print(f"Error getting program by ID: {e}")
            return None

    def register_student(self, program_id: str, first_name: str, last_name: str,
                         email: str, phone: str, age: int) -> Dict:
        try:
            program = self.programs_collection.find_one({"_id": ObjectId(program_id)})
            if not program:
                raise ValueError("Program/Session not found")

            if program.get('available_spots', 0) <= 0:
                raise ValueError("No spots available for this program")

            existing_registration = self.registrations_collection.find_one({"email": email})
            if existing_registration:
                raise ValueError("Email already registered")

            registration_data = {
                "program_id": ObjectId(program_id),
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "age": age,
                "registration_date": datetime.utcnow(),
                "status": "pending"
            }

            result = self.registrations_collection.insert_one(registration_data)

            updated_spots = program['available_spots'] - 1
            self.programs_collection.update_one(
                {"_id": ObjectId(program_id)},
                {"$set": {"available_spots": updated_spots}}
            )

            registration = self.registrations_collection.find_one({"_id": result.inserted_id})
            registration = self._convert_objectid(registration)
            registration['program_id'] = program_id
            registration['spots_remaining'] = updated_spots
            registration['location_name'] = program.get('location', 'N/A')

            return registration

        except ValueError as ve:
            raise ve
        except Exception as e:
            print(f"Error registering student: {e}")
            raise ValueError(f"Registration failed: {str(e)}")

    def search_programs(self, search_term: str) -> List[Dict]:
        """Recherche des programmes par nom de programme ou lieu."""
        try:
            programs = list(self.programs_collection.find({
                "$or": [
                    {"program_name": {"$regex": search_term, "$options": "i"}},
                    {"location": {"$regex": search_term, "$options": "i"}}
                ]
            }))

            result = []
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
                    
                result.append({
                    'id': str(program['_id']),
                    'program_name': program.get('program_name'),
                    'location': program.get('location'),
                    'start_date': start_date.strftime('%Y-%m-%d') if start_date else 'N/A',
                    'end_date': end_date_str,
                    'duration_months': program.get('duration_months'),
                    'price': float(program.get('price', 0)),
                    'available_spots': program.get('available_spots', 0),
                    'description': program.get('description')
                })

            return result
        except Exception as e:
            print(f"Error searching programs: {e}")
            return []
    
    def format_program_info_for_chat(self) -> str:
        try:
            programs = self.get_all_programs()
            
            if not programs:
                return "❌ Aucune information de programme disponible pour le moment. Veuillez réessayer plus tard."
            
            message = "🚀 **PROGRAMMES DISPONIBLES :**\n\n"
            
            for i, program in enumerate(programs, 1):
                start_date = program.get('start_date')
                if isinstance(start_date, str):
                    try:
                        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    except ValueError:
                        start_date = None

                message += f"**{i}. {program.get('program_name', 'N/A')}**\n"
                message += f"📍 Lieu : {program.get('location', 'N/A')}\n"
                message += f"📅 Début : {start_date.strftime('%Y-%m-%d') if start_date else 'N/A'}\n"
                message += f"⏳ Durée : {program.get('duration_months', 'N/A')} mois\n"
                message += f"💰 Prix : {program.get('price', 0):,.0f} MAD\n"
                message += f"🎫 Places disponibles : {program.get('available_spots', 0)}\n"
                message += f"ℹ️ Description : {program.get('description', 'N/A')}\n"
                
                requirements = program.get('requirements')
                if requirements:
                    message += "📝 Prérequis : " + ", ".join(requirements) + "\n"
                
                message += "\n"
            
            message += "Pour vous inscrire ou avoir plus d'informations, tapez 'inscription' !"
            
            return message
            
        except Exception as e:
            print(f"Error formatting program info for chat: {e}")
            return "❌ Erreur lors de l'affichage des informations sur les programmes. Veuillez réessayer."


    def close_connection(self):
        if self.client:
            self.client.close()

db_service = DatabaseService()

def seed_sample_data():
    try:
        sample_programs = [
            {
                "program_name": "Développement Mobile",
                "location": "Rabat",
                "start_date": "2025-10-15T09:00:00Z", 
                "duration_months": 8,
                "price": 48000.0,
                "available_spots": 18,
                "requirements": ["Expérience en programmation de base", "Connaissance de l'anglais technique"],
                "description": "Maîtrisez le développement d'applications natives iOS et Android, ainsi que les frameworks multiplateformes.",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "program_name": "Data Science & Intelligence Artificielle",
                "location": "Casablanca",
                "start_date": "2025-11-01T09:00:00Z", 
                "duration_months": 10,
                "price": 52000.0,
                "available_spots": 15,
                "requirements": ["Bases en mathématiques et statistiques", "Bonne logique de résolution de problèmes"],
                "description": "Maîtrisez l'analyse de données, le machine learning et l'IA avec Python et les outils modernes.",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "program_name": "Développement Web Full Stack",
                "location": "Casablanca",
                "start_date": "2025-12-01T09:00:00Z",
                "duration_months": 8,
                "price": 35000.0,
                "available_spots": 10,
                "requirements": ["Notions de HTML/CSS/JS", "Logique de base en programmation"],
                "description": "Devenez un développeur Full Stack complet, capable de créer des applications web robustes.",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "program_name": "Développement Web Full Stack",
                "location": "Rabat",
                "start_date": "2026-01-15T09:00:00Z",
                "duration_months": 8,
                "price": 35000.0,
                "available_spots": 12,
                "requirements": ["Notions de HTML/CSS/JS", "Logique de base en programmation"],
                "description": "Devenez un développeur Full Stack complet, capable de créer des applications web robustes.",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "program_name": "Développement Web Full Stack",
                "location": "Fès",
                "start_date": "2026-02-10T09:00:00Z",
                "duration_months": 8,
                "price": 35000.0,
                "available_spots": 8,
                "requirements": ["Notions de HTML/CSS/JS", "Logique de base en programmation"],
                "description": "Devenez un développeur Full Stack complet, capable de créer des applications web robustes.",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        ]

        for program_data in sample_programs:
            existing = db_service.programs_collection.find_one({
                "program_name": program_data["program_name"],
                "location": program_data["location"]
            })
            if not existing:
                db_service.programs_collection.insert_one(program_data)
                print(f"Inserted program: {program_data['program_name']} at {program_data['location']}")
            else:
                print(f"Program already exists: {program_data['program_name']} at {program_data['location']}")

    except Exception as e:
        print(f"Error seeding data: {e}")

if __name__ == "__main__":
    seed_sample_data()
    
    print("=== TEST DE LA FONCTION DE FORMATAGE ===")
    bootcamp_info_formatted = db_service.format_program_info_for_chat()
    print(bootcamp_info_formatted)

    print("\n=== TEST DE RECHERCHE DE PROGRAMMES (Casablanca) ===")
    search_results = db_service.search_programs("Casablanca")
    for result in search_results:
        print(f"Trouvé : {result['program_name']} à {result['location']} - {result['start_date']}")

    db_service.close_connection()
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    import os
import shelve
from dotenv import load_dotenv
import time
import logging
import json
from typing import Callable, Dict, Any, List, Optional
from datetime import datetime, timedelta
import sys
from pathlib import Path
import re

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Chemin correct pour l'importation de services.database_service
sys.path.append(str(Path(__file__).parent.parent))

try:
    from services.database_service import db_service
except ImportError as e:
    logging.error(f"Could not import db_service. Ensure database_service.py is in 'services' directory relative to its parent 'app' directory. Error: {e}")
    sys.exit("Database service not found. Exiting.")

import google.generativeai as genai

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

class ToolManager:
    """Gère la collection d'outils disponibles et leur enregistrement."""
    def __init__(self, conversation_manager):
        self.conversation_manager = conversation_manager
        self.tools: Dict[str, Tool] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        """Enregistre les outils de base que l'IA peut utiliser."""

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

        def register_student_func(location: str, first_name: str, last_name: str, email: str, phone: str, age: str):
            try:
                age_int = int(age)

                program = db_service.get_program_by_location(location) # This might still be an issue if multiple programs are in one location
                if not program:
                    raise ValueError("Program/Session not found for the specified location.")

                result = db_service.register_student(
                    program['id'],
                    first_name,
                    last_name,
                    email,
                    phone,
                    age_int
                )

                detected_language = conversation_manager.detected_language
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
                detected_language = conversation_manager.detected_language
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
                detected_language = conversation_manager.detected_language
                if detected_language == "fr":
                    return f"Une erreur inattendue est survenue lors de l'inscription : {str(e)}"
                elif detected_language == "ar":
                    return f"حدث خطأ غير متوقع أثناء التسجيل: {str(e)}"
                else:
                    return f"An unexpected error occurred during registration: {str(e)}"

        # MODIFICATION: Refined get_program_details_func to handle program name and location
        def get_program_details_func(program_name_and_location: str):
            # Attempt to parse "Program Name - Location" format
            parts = [p.strip() for p in program_name_and_location.split('-', 1)]
            program_name_search = parts[0]
            location_search = parts[1] if len(parts) > 1 else None

            program = None
            if program_name_search and location_search:
                program = db_service.get_program_by_name_and_location(program_name_search, location_search)
            elif program_name_search: # Fallback if only program name is provided
                # This might still return the wrong one if multiple programs have similar names but different locations
                programs_found = db_service.search_programs(program_name_search)
                if programs_found:
                    program = programs_found[0] # Just take the first one, or refine this logic if needed

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
        
        # MODIFICATION: Renamed to get_program_details, description updated for the new parameter type
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

class ConversationManager:
    """Gère les sessions de chat, l'historique et le traitement des outils."""
    def __init__(self):
        self.chats = {}
        self.user_states = {}
        self.ordered_steps = [
            "motivation",
            "program_selection",
            "collect_personal_info",
            "confirm_enrollment",
            "enrollment_complete"
        ]
        self.tool_manager = ToolManager(self)
        self.chat_histories = {}
        self.detected_language: str = "en"

    def get_user_state(self, user_id: str):
        """Récupère ou initialise l'état de l'utilisateur."""
        if user_id not in self.user_states:
            self.user_states[user_id] = {
                "current_step": self.ordered_steps[0],
                "personal_info": {},
                "program": None,
                "level": None,
            }
        return self.user_states[user_id]

    def get_current_step(self, user_id: str) -> str:
        """Retourne l'étape actuelle pour un utilisateur."""
        return self.get_user_state(user_id)["current_step"]

    def set_current_step(self, user_id: str, step_name: str) -> str:
        """Définit l'étape actuelle pour un utilisateur."""
        if step_name in self.ordered_steps:
            self.get_user_state(user_id)["current_step"] = step_name
            logging.info(f"User {user_id} is now at step: {step_name}")
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
                return f"Successfully advanced to step: {next_step}."
            else:
                logging.info(f"User {user_id} is already at the last step: {current_step_name}")
                return f"Already at final step: {current_step_name}."
        except ValueError:
            logging.error(f"Current step '{current_step_name}' not found in ordered_steps for user {user_id}. Resetting to first step.")
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
        logging.info(f"Info utilisateur {user_id} mise à jour: {field} = {value}")
        return f"User info '{field}' updated to '{value}'."

    def get_or_create_chat(self, wa_id: str):
        """Récupère une session de chat existante ou en crée une nouvelle pour un utilisateur donné."""
        self.get_user_state(wa_id)

        if wa_id not in self.chats:
            self.chat_histories[wa_id] = []

            initial_system_context_template = (
                "You are a helpful and professional educational assistant for a Full Stack Web Development Bootcamp. "
                "Your primary goal is to guide potential students through the bootcamp information and registration process. "
                "You are based in Casablanca, Morocco. Respond in French unless the user explicitly requests another language, or it's clear they are speaking Arabic or English. " 
                "**IMPORTANT: For language detection, use the language tag ONLY internally for your processing. "
                "NEVER include language tags like [LANG:fr], [LANG:en], or [LANG:ar] in your responses to users.** "
                "**PRIORITY 1: Detect the user's language from their message and respond in the same language. (French, Arabic, or English)** "
                "**PRIORITY 2: If a user asks for information that an AVAILABLE TOOL can provide, you ABSOLUTELY MUST call that tool using the `{{tool_name:arg1,arg2,...}}` syntax. This tool call MUST be the ONLY thing in your response. DO NOT add any conversational text.** "
                "**PRIORITY 3: If a tool does not require arguments, use `{{tool_name}}`.** "
                "Do not make up information. If you lack information for a tool, ask for it clearly. "
                "Be friendly, encouraging, and provide thorough answers in the user's language.\n\n"
                "--- Available Tools ---\n"
                "{tool_descriptions}\n"
                "-----------------------\n\n"
            )

            tool_descriptions_for_prompt = self.tool_manager.get_tool_descriptions("fr") 

            system_prompt = initial_system_context_template.format(
                tool_descriptions=tool_descriptions_for_prompt
            )

            self.chat_histories[wa_id].append({
                "role": "user",
                "parts": [system_prompt]
            })

            self.chats[wa_id] = model.start_chat(history=self.chat_histories[wa_id])
            logging.info(f"New chat started for {wa_id} with initial system prompt for language detection.")

        return self.chats[wa_id]

    def process_tool_calls_from_text(self, text: str, user_id: str) -> tuple[str, Optional[str]]:
        """Extrait et exécute les appels d'outils d'une chaîne de texte donnée."""
        tool_call_pattern = r"\{(\{?)([a-zA-Z_]+)(?::([^}]+))?\}(\1)"
        matches = list(re.finditer(tool_call_pattern, text))
        tool_execution_results = []
        clean_text_parts = []
        last_idx = 0

        for match in matches:
            tool_call_str = match.group(0)
            tool_name = match.group(2)
            args_str = match.group(3) if match.group(3) else ""

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
                    if tool_name in ["set_user_step", "update_user_info"]:
                        raw_result = tool.execute(user_id, *args)
                    elif tool_name in ["get_user_step", "advance_to_next_step"]:
                        raw_result = tool.execute(user_id)
                    elif tool_name == "register_student":
                        if len(args) == 6:
                            raw_result = tool.execute(*args) 
                        else:
                            raw_result = f"Error: register_student requires 6 arguments (location, first_name, last_name, email, phone, age), but received {len(args)} from tool call '{tool_call_str}' parsed as: {args}."
                    # Modification: Handle 'get_program_details' with specific parsing for program name and location
                    elif tool_name == "get_program_details":
                        # The AI sends a single argument like "Full Stack Web Development - Casablanca"
                        if len(args) == 1:
                            program_name_and_location = args[0]
                            raw_result = tool.execute(program_name_and_location)
                        else:
                            raw_result = f"Error: get_program_details requires 1 argument (program_name_and_location), but received {len(args)} from tool call '{tool_call_str}'."
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

# Instance globale du gestionnaire de conversation
conversation_manager = ConversationManager()

def check_if_thread_exists(wa_id: str):
    with shelve.open("threads_db") as threads_shelf:
        return threads_shelf.get(wa_id, None)

def store_thread(wa_id: str, thread_id: str):
    with shelve.open("threads_db", writeback=True) as threads_shelf:
        threads_shelf[wa_id] = thread_id

def detect_language_from_message(message: str) -> str:
    """Détecte la langue du message utilisateur."""
    french_keywords = ['bonjour', 'salut', 'merci', 'oui', 'non', 'comment', 'pourquoi', 'quand', 'où', 'information', 'bootcamp', 'formation', 'inscription', 'casablanca', 'rabat', 'développement', 'mobile', 'data science', 'cybersécurité', 'full stack'] # Added 'full stack'
    arabic_keywords = ['مرحبا', 'شكرا', 'نعم', 'لا', 'كيف', 'لماذا', 'متى', 'أين', 'معلومات', 'تدريب', 'تسجيل', 'الدار البيضاء', 'الرباط']
    english_keywords = ['hello', 'hi', 'thank', 'yes', 'no', 'how', 'why', 'when', 'where', 'information', 'bootcamp', 'training', 'registration', 'casablanca', 'rabat', 'mobile development', 'data science', 'cybersecurity', 'full stack'] # Added 'full stack'
    
    message_lower = message.lower()
    
    french_count = sum(1 for keyword in french_keywords if keyword in message_lower)
    arabic_count = sum(1 for keyword in arabic_keywords if keyword in message_lower)
    english_count = sum(1 for keyword in english_keywords if keyword in message_lower)
    
    arabic_chars = len([char for char in message if '\u0600' <= char <= '\u06FF'])
    if arabic_chars > 0:
        arabic_count += arabic_chars / 10  
    
    if french_count > english_count and french_count > arabic_count:
        return "fr"
    elif arabic_count > english_count and arabic_count > french_count:
        return "ar"
    else:
        return "en"

def generate_response(message_body: str, wa_id: str, name: str) -> str:
    """Génère une réponse à partir du message de l'utilisateur."""
    try:
        detected_language = detect_language_from_message(message_body)
        conversation_manager.detected_language = detected_language
        logging.info(f"Detected language: {detected_language}")

        chat = conversation_manager.get_or_create_chat(wa_id)
        user_state = conversation_manager.get_user_state(wa_id)
        current_step = user_state["current_step"]

        conversation_manager.chat_histories[wa_id].append({
            "role": "user",
            "parts": [f"[User: {name}] {message_body}"]
        })

        context_info = (
            f"[INTERNAL CONTEXT - DO NOT MENTION TO USER]\n"
            f"Current step: {current_step}\n"
            f"User state: {user_state}\n"
            f"Detected language: {detected_language}\n"
            f"[END INTERNAL CONTEXT]\n\n"
            f"User message: {message_body}"
        )

        response = chat.send_message(
            context_info,
            generation_config=generation_config
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
                generation_config=generation_config
            )
            
            final_response = follow_up_response.text
            
            conversation_manager.chat_histories[wa_id].append({
                "role": "model",
                "parts": [final_response]
            })
            
            return final_response
        else:
            conversation_manager.chat_histories[wa_id].append({
                "role": "model", 
                "parts": [clean_response]
            })
            
            return clean_response

    except Exception as e:
        logging.error(f"Error generating response for {wa_id}: {e}")
        
        if conversation_manager.detected_language == "fr":
            error_response = "Désolé, j'ai rencontré un problème technique. Pouvez-vous reformuler votre question ?"
        elif conversation_manager.detected_language == "ar":
            error_response = "عذراً، واجهت مشكلة تقنية. هل يمكنك إعادة صياغة سؤالك؟"
        else:
            error_response = "Sorry, I encountered a technical issue. Could you please rephrase your question?"
            
        return error_response