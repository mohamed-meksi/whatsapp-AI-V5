import os
import json
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration pour MongoDB local
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "geeks_institute_db")

# Define the path to your sessions.json file relative to this script
SESSIONS_DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'sessions.json')

print(f"🔧 Configuration MongoDB:")
print(f"   URI: {MONGO_URI}")
print(f"   Database: {MONGO_DB_NAME}")
print("-" * 50)

def init_db():
    """
    Initializes the local MongoDB database.
    Drops existing 'students', 'conversations', 'sessions', and 'liste_numeros' collections for a clean slate,
    then inserts sample bootcamp session data and authorized phone numbers.
    Ensures indexes on relevant collections.
    """
    client = None
    try:
        # Configuration pour MongoDB local
        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000,  # 5 secondes timeout
            connectTimeoutMS=10000,         # 10 secondes pour la connexion
            socketTimeoutMS=10000           # 10 secondes pour les sockets
        )
        
        # Test de connexion
        client.admin.command('ping')
        db = client[MONGO_DB_NAME]

        print(f"✅ Connected to local MongoDB database: {MONGO_DB_NAME}")
        print(f"📍 Server info: {client.server_info()['version']}")

        # Drop existing collections for a clean setup (useful during development)
        print("\n🗑️  Dropping existing collections...")
        collections_to_drop = ['students', 'conversations', 'sessions', 'liste_numeros']
        
        existing_collections = db.list_collection_names()
        print(f"📋 Existing collections: {existing_collections}")
        
        for collection_name in collections_to_drop:
            if collection_name in existing_collections:
                db[collection_name].drop()
                print(f"   ✅ Collection '{collection_name}' dropped.")
            else:
                print(f"   ℹ️  Collection '{collection_name}' doesn't exist, skipping.")

        # Create collections explicitly
        print("\n📁 Creating collections...")
        db.create_collection('students')
        db.create_collection('sessions')
        db.create_collection('liste_numeros')
        print("   ✅ Collections 'students', 'sessions', and 'liste_numeros' created.")

        # Ensure indexes for performance and data integrity
        print("\n🔍 Creating indexes...")
        db.students.create_index("whatsapp_id", unique=True)
        print("   ✅ Unique index on students.whatsapp_id")
        
        db.sessions.create_index([("program_name", 1), ("location", 1)])
        print("   ✅ Compound index on sessions (program_name, location)")
        
        db.liste_numeros.create_index("numero", unique=True)
        print("   ✅ Unique index on liste_numeros.numero")
        
        db.liste_numeros.create_index("actif")
        print("   ✅ Index on liste_numeros.actif")

        # Sample bootcamp sessions data
        print("\n📚 Inserting sample sessions...")
        sessions_data = [
            {
                "program_name": "Développement Web (Full-Stack)",
                "location": "Casablanca",
                "start_date": "2025-09-01T09:00:00Z",
                "duration_months": 8,
                "price": 45000,
                "available_spots": 20,
                "requirements": ["Logique de base en programmation", "Motivation"],
                "description": "Apprenez à construire des applications web complètes, du frontend au backend, avec les technologies les plus demandées.",
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            },
            {
                "program_name": "Développement Mobile",
                "location": "Rabat",
                "start_date": "2025-10-15T09:00:00Z",
                "duration_months": 8,
                "price": 48000,
                "available_spots": 18,
                "requirements": ["Connaissances en programmation orientée objet", "Créativité"],
                "description": "Maîtrisez le développement d'applications natives iOS et Android, ainsi que les frameworks hybrides populaires.",
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            },
            {
                "program_name": "Data Science & Intelligence Artificielle",
                "location": "Casablanca",
                "start_date": "2025-11-01T09:00:00Z",
                "duration_months": 10,
                "price": 52000,
                "available_spots": 15,
                "requirements": ["Mathématiques de base", "Logique de programmation"],
                "description": "Maîtrisez l'analyse de données, le machine learning et l'IA avec Python et les outils modernes.",
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
        ]

        # Sample authorized phone numbers data
        print("📱 Inserting authorized phone numbers...")
        numeros_autorises_data = [
            {
                "numero": "+212643370003",
                "nom": "Mohamed Meksi",
                "description": "Étudiant potentiel - Programme Web Development",
                "date_ajout": datetime.now(),
                "actif": True,
                "type_utilisateur": "etudiant",
                "notes": "Contact initial via site web"
            },
            {
                "numero": "+212700000002", 
                "nom": "Fatima Zahra",
                "description": "Étudiante potentielle - Programme Mobile",
                "date_ajout": datetime.now(),
                "actif": True,  # Changé à True pour les tests
                "type_utilisateur": "etudiant",
                "notes": "Recommandée par un ancien étudiant"
            },
            {
                "numero": "+212600000001",
                "nom": "Ahmed Benali",
                "description": "Administrateur système",
                "date_ajout": datetime.now(),
                "actif": True,
                "type_utilisateur": "admin",
                "notes": "Accès administrateur complet"
            },
            {
                "numero": "+212500000005",
                "nom": "Khadija Alami",
                "description": "Conseillère pédagogique",
                "date_ajout": datetime.now(),
                "actif": True,
                "type_utilisateur": "staff",
                "notes": "Support pédagogique et orientation"
            }
        ]

        # Insert sample sessions
        if sessions_data:
            result = db.sessions.insert_many(sessions_data)
            print(f"   ✅ {len(result.inserted_ids)} sessions inserted successfully")
        else:
            print("   ⚠️  No sample sessions to insert")

        # Insert authorized phone numbers
        if numeros_autorises_data:
            result = db.liste_numeros.insert_many(numeros_autorises_data)
            print(f"   ✅ {len(result.inserted_ids)} authorized numbers inserted successfully")
            
            # Display the authorized numbers for reference
            print(f"\n📱 Numéros autorisés ajoutés:")
            print("=" * 70)
            for numero in numeros_autorises_data:
                status = "✅ Actif" if numero['actif'] else "❌ Inactif"
                print(f"  {numero['numero']} - {numero['nom']}")
                print(f"     Type: {numero['type_utilisateur']} | Status: {status}")
                print(f"     Description: {numero['description']}")
                print("-" * 50)
        else:
            print("   ⚠️  No authorized phone numbers to insert")

        # Statistics
        print(f"\n📊 Database Statistics:")
        print(f"   📚 Sessions: {db.sessions.count_documents({})}")
        print(f"   👤 Students: {db.students.count_documents({})}")
        print(f"   📱 Authorized numbers: {db.liste_numeros.count_documents({})}")
        print(f"   📱 Active numbers: {db.liste_numeros.count_documents({'actif': True})}")

        print(f"\n🎉 Local MongoDB initialization complete!")
        print(f"🏠 Database: {MONGO_DB_NAME}")
        print(f"🔗 Connection: {MONGO_URI}")

    except ConnectionFailure as e:
        print(f"❌ ERROR: MongoDB connection failed.")
        print(f"   Please ensure MongoDB is running locally on port 27017")
        print(f"   You can start MongoDB with: mongod --dbpath /your/db/path")
        print(f"   Details: {e}")
    except OperationFailure as e:
        print(f"❌ ERROR: MongoDB operation failed during initialization.")
        print(f"   Details: {e}")
    except FileNotFoundError:
        print(f"⚠️  WARNING: sessions.json not found at {SESSIONS_DATA_PATH}")
        print(f"   Using hardcoded sample data instead")
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Failed to decode sessions.json")
        print(f"   Please check the JSON file format. Details: {e}")
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR occurred during MongoDB initialization: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if client:
            client.close()
            print("\n🔐 MongoDB connection closed.")

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