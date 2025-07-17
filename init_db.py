import os
import json
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration pour MongoDB local
MONGO_URI = os.getenv("MONGODB")
MONGO_DB_NAME = os.getenv("DATABASE", "geeks_institute_db")

# Define the path to your sessions.json file relative to this script
SESSIONS_DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'sessions.json')

print(f"🔧 Configuration MongoDB:")
print(f"   URI: {MONGO_URI}")
print(f"   Database: {MONGO_DB_NAME}")
print("-" * 50)

def init_db():
    """
    Fonction principale d'initialisation de la base de données
    """
    client = None
    try:
        # Connexion à MongoDB
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[MONGO_DB_NAME]
        
        # Création des collections si elles n'existent pas
        if "programs" not in db.list_collection_names():
            db.create_collection("programs")
            print("✅ Collection 'programs' créée")
        
        if "registrations" not in db.list_collection_names():
            db.create_collection("registrations")
            print("✅ Collection 'registrations' créée")
        
        if "conversations" not in db.list_collection_names():
            db.create_collection("conversations")
            print("✅ Collection 'conversations' créée")
            
        if "liste_numeros" not in db.list_collection_names():
            db.create_collection("liste_numeros")
            print("✅ Collection 'liste_numeros' créée")
            
        if "user_sessions" not in db.list_collection_names():
            db.create_collection("user_sessions")
            print("✅ Collection 'user_sessions' créée")
        
        # Création des index
        db.programs.create_index([("program_name", "text"), ("location", "text")])
        db.registrations.create_index("email", unique=True)
        db.registrations.create_index("wa_id", unique=True)
        db.registrations.create_index("program_id")
        db.liste_numeros.create_index("numero", unique=True)
        db.user_sessions.create_index("user_id", unique=True)
        print("✅ Index créés avec succès")
        
        # Initialiser les données de test
        db_service = DatabaseService()
        db_service.init_test_data()
        print("✅ Données de test initialisées")
        
        print("\n✨ Base de données initialisée avec succès!")
        
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation de la base de données: {e}")
    finally:
        if client:
            client.close()

def add_phone_number(numero, nom, description="", type_utilisateur="etudiant", notes=""):
    """
    Fonction utilitaire pour ajouter un nouveau numéro autorisé à la base locale
    
    Args:
        numero (str): Numéro de téléphone au format international (+212...)
        nom (str): Nom de la personne
        description (str): Description optionnelle
        type_utilisateur (str): Type (etudiant, admin, partenaire, alumni, staff)
        notes (str): Notes additionnelles
    """
    client = None
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[MONGO_DB_NAME]
        
        # Vérifier si le numéro existe déjà
        existing = db.liste_numeros.find_one({"numero": numero})
        if existing:
            print(f"⚠️  Le numéro {numero} existe déjà dans la base de données.")
            print(f"   Utilisateur existant: {existing.get('nom', 'N/A')}")
            return False
        
        # Ajouter le nouveau numéro
        nouveau_numero = {
            "numero": numero,
            "nom": nom,
            "description": description,
            "date_ajout": datetime.now(),
            "actif": True,
            "type_utilisateur": type_utilisateur,
            "notes": notes
        }
        
        result = db.liste_numeros.insert_one(nouveau_numero)
        print(f"✅ Numéro {numero} ajouté avec succès")
        print(f"   Nom: {nom}")
        print(f"   Type: {type_utilisateur}")
        print(f"   ID: {result.inserted_id}")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'ajout du numéro {numero}: {e}")
        return False
    finally:
        if client:
            client.close()

def list_authorized_numbers():
    """
    Liste tous les numéros autorisés dans la base locale
    """
    client = None
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[MONGO_DB_NAME]
        
        numbers = list(db.liste_numeros.find({}).sort("date_ajout", -1))
        
        if not numbers:
            print("📱 Aucun numéro autorisé trouvé dans la base de données.")
            return
        
        print(f"\n📱 Liste des numéros autorisés ({len(numbers)} total):")
        print("=" * 80)
        
        for numero in numbers:
            status = "✅ Actif" if numero.get('actif', False) else "❌ Inactif"
            print(f"📞 {numero['numero']} - {numero.get('nom', 'N/A')}")
            print(f"   Type: {numero.get('type_utilisateur', 'N/A')} | Status: {status}")
            print(f"   Description: {numero.get('description', 'N/A')}")
            print(f"   Ajouté: {numero.get('date_ajout', 'N/A')}")
            if numero.get('notes'):
                print(f"   Notes: {numero['notes']}")
            print("-" * 60)
            
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des numéros: {e}")
    finally:
        if client:
            client.close()

def test_connection():
    """
    Test la connexion à la base de données locale
    """
    client = None
    try:
        print("🔍 Test de connexion à MongoDB local...")
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        
        # Test ping
        client.admin.command('ping')
        print("✅ Ping successful")
        
        # Test database access
        db = client[MONGO_DB_NAME]
        collections = db.list_collection_names()
        print(f"✅ Database accessible: {MONGO_DB_NAME}")
        print(f"   Collections: {collections}")
        
        # Test collections count
        for collection_name in ['students', 'sessions', 'liste_numeros']:
            if collection_name in collections:
                count = db[collection_name].count_documents({})
                print(f"   {collection_name}: {count} documents")
        
        print("🎉 Connection test successful!")
        return True
        
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        print("   Make sure MongoDB is running locally on port 27017")
        return False
    finally:
        if client:
            client.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "add_number":
            # Usage: python init_db.py add_number "+212600000007" "Nom Prénom" "Description"
            if len(sys.argv) >= 4:
                numero = sys.argv[2]
                nom = sys.argv[3]
                description = sys.argv[4] if len(sys.argv) > 4 else ""
                type_user = sys.argv[5] if len(sys.argv) > 5 else "etudiant"
                add_phone_number(numero, nom, description, type_user)
            else:
                print("Usage: python init_db.py add_number <numero> <nom> [description] [type_utilisateur]")
                
        elif command == "list_numbers":
            list_authorized_numbers()
            
        elif command == "test":
            test_connection()
            
        else:
            print("Commands available:")
            print("  init_db.py                    - Initialize database")
            print("  init_db.py add_number         - Add authorized number")
            print("  init_db.py list_numbers       - List all authorized numbers")
            print("  init_db.py test              - Test database connection")
    else:
        init_db()