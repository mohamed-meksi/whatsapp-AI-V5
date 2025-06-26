import os
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import unicodedata

load_dotenv()

# MongoDB Configuration
MONGODB_URL = os.getenv('MONGODB')
DATABASE_NAME = os.getenv('DATABASE')

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
    
    def is_user_registered(self, wa_id: str) -> bool:
        # Utiliser le service de base de données, pas self.db
        user = self.db_service.registrations_collection.find_one({'wa_id': wa_id})
        
        return user is not None
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

    def get_program_by_name_and_location(self, program_name, location):
        # Recherche souple
        for prog in self.db['programs'].find():
            if (self.normalize(prog['program_name']) == self.normalize(program_name)
                and self.normalize(prog['location']) == self.normalize(location)):
                return prog
        return None

    def normalize(self, s):
        return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII').lower().replace('-', ' ').replace('_', ' ').strip()

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
                         email: str, phone: str, age: int, wa_id: str) -> Dict:
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
                "wa_id": wa_id,
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
    def save_conversation_message(self, user_id: str, role: str, message: str, metadata: Dict = None) -> bool:
        """Sauvegarde un message de conversation dans la base de données."""
        try:
            conversation_data = {
                "user_id": user_id,
                "role": role,  # "user" ou "assistant"
                "message": message,
                "timestamp": datetime.utcnow(),
                "metadata": metadata or {}
            }
            
            result = self.db.conversations.insert_one(conversation_data)
            return bool(result.inserted_id)
        except Exception as e:
            print(f"Error saving conversation message: {e}")
            return False

    def get_conversation_history(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Récupère l'historique de conversation pour un utilisateur."""
        try:
            conversations = list(
                self.db.conversations.find({"user_id": user_id})
                .sort("timestamp", -1)
                .limit(limit)
            )
            
            # Inverser pour avoir l'ordre chronologique
            conversations.reverse()
            
            return [self._convert_objectid(conv) for conv in conversations]
        except Exception as e:
            print(f"Error getting conversation history: {e}")
            return []

    def delete_conversation_history(self, user_id: str) -> bool:
        """Supprime l'historique de conversation pour un utilisateur."""
        try:
            result = self.db.conversations.delete_many({"user_id": user_id})
            return result.deleted_count > 0
        except Exception as e:
            print(f"Error deleting conversation history: {e}")
            return False

    def save_user_session(self, user_id: str, session_data: Dict) -> bool:
        """Sauvegarde les données de session utilisateur."""
        try:
            session_doc = {
                "user_id": user_id,
                "session_data": session_data,
                "last_updated": datetime.utcnow()
            }
            
            # Upsert - met à jour si existe, crée sinon
            result = self.db.user_sessions.replace_one(
                {"user_id": user_id},
                session_doc,
                upsert=True
            )
            return bool(result.acknowledged)
        except Exception as e:
            print(f"Error saving user session: {e}")
            return False

    def get_user_session(self, user_id: str) -> Optional[Dict]:
        """Récupère les données de session utilisateur."""
        try:
            session = self.db.user_sessions.find_one({"user_id": user_id})
            return self._convert_objectid(session) if session else None
        except Exception as e:
            print(f"Error getting user session: {e}")
            return None

    def _create_indexes(self):
        """Mise à jour de la méthode existante pour inclure les nouveaux index."""
        # Index existants
        self.programs_collection.create_index([("program_name", "text"), ("location", "text")])
        self.registrations_collection.create_index("email", unique=True)
        self.registrations_collection.create_index("program_id")
        
        # Nouveaux index pour les conversations
        self.db.conversations.create_index([("user_id", 1), ("timestamp", -1)])
        self.db.user_sessions.create_index("user_id", unique=True)
        self.db.user_sessions.create_index("last_updated")
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