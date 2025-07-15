import os
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

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
        self.registrations_collection.create_index("wa_id", unique=True)  
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

    #  This function can be more precise if program_name is also provided
    def get_program_by_name_and_location(self, program_name: str, location: str) -> Optional[Dict]:
        """
        Récupère les détails du programme par nom de programme ET par lieu.
        """
        try:
            # Utiliser une recherche exacte au lieu de regex pour éviter les problèmes avec les caractères spéciaux
            program = self.programs_collection.find_one({
                "program_name": program_name,
                "location": location
            })
            
            # Si la recherche exacte ne donne rien, essayer une recherche insensible à la casse
            if not program:
                program = self.programs_collection.find_one({
                    "$and": [
                        {"program_name": {"$eq": program_name}},
                        {"location": {"$eq": location}}
                    ]
                })
            
            return self._convert_objectid(program) if program else None
        except Exception as e:
            print(f"Error getting program by name and location: {e}")
            return None

    # Keep get_program_by_location if it's used elsewhere for broader searches
    def get_program_by_location(self, location_name: str) -> Optional[Dict]:
        """Récupère les détails du programme par le nom du lieu."""
        try:
            # Recherche exacte d'abord
            program = self.programs_collection.find_one({
                "location": location_name
            })
            
            # Si pas de résultat, essayer une recherche insensible à la casse
            if not program:
                program = self.programs_collection.find_one({
                    "location": {"$eq": location_name}
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

    def verify_registration_possibility(self, program_id: str, email: str, wa_id: str) -> None:
        """Vérifie si l'inscription est possible."""
        try:
            # Vérifier si le programme existe et a des places disponibles
            try:
                program_object_id = ObjectId(program_id)
            except:
                logging.error(f"ID de programme invalide: {program_id}")
                raise ValueError("ID de programme invalide.")

            program = self.programs_collection.find_one({"_id": program_object_id})
            if not program:
                logging.error(f"Programme {program_id} non trouvé")
                raise ValueError("Programme introuvable.")
            
            if program.get("available_spots", 0) <= 0:
                logging.error(f"Plus de places disponibles pour le programme {program_id}")
                raise ValueError("Plus de places disponibles pour ce programme.")
            
            # Vérifier si l'utilisateur est déjà inscrit (par wa_id)
            existing_registration = self.registrations_collection.find_one({"wa_id": wa_id})
            if existing_registration:
                logging.error(f"wa_id {wa_id} déjà inscrit")
                raise ValueError("Ce numéro WhatsApp est déjà inscrit à un programme.")
                
            logging.info(f"Vérification réussie pour wa_id {wa_id} et programme {program_id}")
            
        except ValueError as ve:
            raise ve
        except Exception as e:
            logging.error(f"Error in verify_registration_possibility: {str(e)}")
            raise ValueError(f"Erreur lors de la vérification de l'inscription : {str(e)}")

    def get_user_registration_by_wa_id(self, wa_id: str) -> Optional[Dict]:
        """Récupère l'inscription existante d'un utilisateur par son wa_id."""
        try:
            registration = self.registrations_collection.find_one({"wa_id": wa_id})
            if not registration:
                return None
            
            # Récupérer les informations du programme associé
            program = self.programs_collection.find_one({"_id": ObjectId(registration["program_id"])})
            
            # Convertir les ObjectId et ajouter les informations du programme
            registration = self._convert_objectid(registration)
            if program:
                registration["program_info"] = {
                    "program_name": program.get("program_name"),
                    "location": program.get("location"),
                    "start_date": program.get("start_date"),
                    "duration_months": program.get("duration_months"),
                    "price": program.get("price")
                }
            
            logging.info(f"Inscription trouvée pour wa_id {wa_id}")
            return registration
            
        except Exception as e:
            logging.error(f"Error getting user registration for wa_id {wa_id}: {str(e)}")
            return None

    def register_student(self, program_id: str, first_name: str, last_name: str, email: str, phone: str, age: int, wa_id: str) -> dict:
        """Inscrit un étudiant à un programme."""
        try:
            # Vérifier si l'inscription est possible
            self.verify_registration_possibility(program_id, email, wa_id)
            
            # Créer l'inscription
            registration = {
                "program_id": program_id,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "age": age,
                "wa_id": wa_id,
                "status": "pending",
                "registration_date": datetime.utcnow()
            }
            
            logging.info(f"Tentative d'inscription pour wa_id {wa_id} au programme {program_id}")
            
            # Insérer l'inscription
            result = self.registrations_collection.insert_one(registration)
            if not result.inserted_id:
                raise ValueError("Échec de l'insertion dans la base de données")
            
            logging.info(f"Inscription réussie avec ID: {result.inserted_id}")
            
            # Mettre à jour le nombre de places disponibles
            update_result = self.programs_collection.update_one(
                {"_id": ObjectId(program_id)},
                {"$inc": {"available_spots": -1}}
            )
            
            if not update_result.modified_count:
                logging.error(f"Échec de la mise à jour des places disponibles pour le programme {program_id}")
                # Annuler l'inscription si la mise à jour échoue
                self.registrations_collection.delete_one({"_id": result.inserted_id})
                raise ValueError("Échec de la mise à jour des places disponibles")
            
            # Récupérer le programme mis à jour
            updated_program = self.programs_collection.find_one({"_id": ObjectId(program_id)})
            if not updated_program:
                raise ValueError("Programme non trouvé après mise à jour")
            
            logging.info(f"Inscription complétée avec succès pour wa_id {wa_id}")
            
            return {
                "registration_id": str(result.inserted_id),
                "spots_remaining": updated_program.get("available_spots", 0)
            }
            
        except Exception as e:
            logging.error(f"Error in register_student: {str(e)}")
            raise ValueError(str(e))

    def search_programs(self, search_term: str) -> List[Dict]:
        """Recherche des programmes par nom de programme ou lieu."""
        try:
            # Recherche exacte d'abord
            programs = list(self.programs_collection.find({
                "$or": [
                    {"program_name": search_term},
                    {"location": search_term}
                ]
            }))
            
            # Si pas de résultats, essayer une recherche insensible à la casse
            if not programs:
                programs = list(self.programs_collection.find({
                    "$or": [
                        {"program_name": {"$eq": search_term}},
                        {"location": {"$eq": search_term}}
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
                if isinstance(start_date, datetime):
                    start_date_str = start_date.strftime('%Y-%m-%d')
                elif isinstance(start_date, str):
                    try:
                        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                        start_date_str = start_date.strftime('%Y-%m-%d')
                    except ValueError:
                        start_date_str = 'N/A'
                else:
                    start_date_str = 'N/A'

                message += f"**{i}. {program.get('program_name', 'N/A')}**\n"
                message += f"📍 Lieu : {program.get('location', 'N/A')}\n"
                message += f"📅 Début : {start_date_str}\n"
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

    def get_program_by_name_and_location_fuzzy(self, program_name: str, location: str) -> Optional[Dict]:
        """
        Version améliorée qui trouve le programme le plus proche même si le nom n'est pas exact.
        """
        try:
            # D'abord essayer une recherche exacte
            exact_match = self.programs_collection.find_one({
                "program_name": {"$regex": f"^{program_name}$", "$options": "i"},
                "location": {"$regex": f"^{location}$", "$options": "i"}
            })
            
            if exact_match:
                return self._convert_objectid(exact_match)
            
            # Si pas de match exact, chercher des correspondances partielles
            from difflib import SequenceMatcher
            
            all_programs = list(self.programs_collection.find({}))
            best_match = None
            best_score = 0
            
            program_lower = program_name.lower().strip()
            location_lower = location.lower().strip()
            
            for program in all_programs:
                prog_name = program.get('program_name', '').lower()
                prog_location = program.get('location', '').lower()
                
                # Score pour le nom du programme
                name_score = SequenceMatcher(None, program_lower, prog_name).ratio()
                
                # Score pour la location (plus important)
                location_score = SequenceMatcher(None, location_lower, prog_location).ratio()
                
                # Score combiné (privilégier la location)
                combined_score = (name_score * 0.4) + (location_score * 0.6)
                
                # Bonus si des mots clés correspondent
                if any(word in prog_name for word in program_lower.split() if len(word) > 3):
                    combined_score += 0.2
                
                if combined_score > best_score:
                    best_score = combined_score
                    best_match = program
            
            # Retourner le meilleur match si le score est suffisant
            if best_match and best_score > 0.5:
                return self._convert_objectid(best_match)
            
            return None
            
        except Exception as e:
            logging.error(f"Error in get_program_by_name_and_location_fuzzy: {e}")
            return None

    def find_similar_programs(self, search_term: str, threshold: float = 0.6) -> List[Dict]:
        """
        Trouve des programmes similaires basés sur la similarité de texte.
        Utilise une recherche floue pour trouver les programmes les plus proches.
        """
        try:
            from difflib import SequenceMatcher
            
            all_programs = list(self.programs_collection.find({}))
            results = []
            
            search_lower = search_term.lower().strip()
            
            for program in all_programs:
                # Calcul de similarité pour le nom du programme
                program_name = program.get('program_name', '').lower()
                location = program.get('location', '').lower()
                
                # Score de similarité pour le nom
                name_similarity = SequenceMatcher(None, search_lower, program_name).ratio()
                
                # Score de similarité pour la location
                location_similarity = SequenceMatcher(None, search_lower, location).ratio()
                
                # Score combiné (privilégier la location si elle match bien)
                combined_score = max(name_similarity, location_similarity * 1.2)
                
                # Vérifier aussi si le terme de recherche est contenu dans le nom ou la location
                if search_lower in program_name or search_lower in location:
                    combined_score = max(combined_score, 0.8)
                
                # Vérifier les mots individuels
                search_words = search_lower.split()
                for word in search_words:
                    if len(word) > 3:  # Ignorer les mots courts
                        if word in program_name or word in location:
                            combined_score = max(combined_score, 0.7)
                
                if combined_score >= threshold:
                    results.append({
                        'program': self._convert_objectid(program),
                        'score': combined_score
                    })
            
            # Trier par score décroissant
            results.sort(key=lambda x: x['score'], reverse=True)
            
            return [r['program'] for r in results]
            
        except Exception as e:
            logging.error(f"Error in find_similar_programs: {e}")
            return []

    def search_programs_intelligent(self, search_term: str) -> List[Dict]:
        """
        Recherche intelligente qui trouve les programmes même avec des fautes de frappe.
        """
        try:
            # D'abord chercher des correspondances exactes
            exact_matches = list(self.programs_collection.find({
                "$or": [
                    {"program_name": {"$regex": search_term, "$options": "i"}},
                    {"location": {"$regex": search_term, "$options": "i"}}
                ]
            }))
            
            if exact_matches:
                return [self._convert_objectid(p) for p in exact_matches]
            
            # Si pas de correspondance exacte, utiliser la recherche floue
            similar_programs = self.find_similar_programs(search_term, threshold=0.5)
            
            # Formater les résultats
            results = []
            for program in similar_programs[:5]:  # Limiter à 5 résultats
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
                    'id': program.get('id', str(program.get('_id', ''))),
                    'program_name': program.get('program_name'),
                    'location': program.get('location'),
                    'start_date': start_date.strftime('%Y-%m-%d') if start_date else 'N/A',
                    'end_date': end_date_str,
                    'duration_months': program.get('duration_months'),
                    'price': float(program.get('price', 0)),
                    'available_spots': program.get('available_spots', 0),
                    'description': program.get('description')
                })
            
            return results
            
        except Exception as e:
            logging.error(f"Error in search_programs_intelligent: {e}")
            return []


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