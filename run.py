
import logging
import sys
from datetime import datetime

# Configuration avancée du logging pour un débogage lisible
class ColoredFormatter(logging.Formatter):
    """Formateur coloré pour une meilleure lisibilité"""
    
    def format(self, record):
        # Format compact pour le terminal
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        
        # Messages avec couleurs et emojis déjà intégrés
        if "🔴" in record.getMessage() or "❌" in record.getMessage():
            return f"[{timestamp}] {record.getMessage()}"
        elif "🟡" in record.getMessage() or "⚠️" in record.getMessage():
            return f"[{timestamp}] {record.getMessage()}"
        elif "✅" in record.getMessage() or "🔵" in record.getMessage():
            return f"[{timestamp}] {record.getMessage()}"
        else:
            return f"[{timestamp}] {record.getMessage()}"

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',  # Format simple pour le terminal
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'debug_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8')
    ]
)

# Appliquer le formateur coloré pour le terminal uniquement
console_handler = logging.getLogger().handlers[0]
console_handler.setFormatter(ColoredFormatter())

# Configuration des niveaux
logging.getLogger().setLevel(logging.INFO)
logging.getLogger('app').setLevel(logging.INFO)
logging.getLogger('werkzeug').setLevel(logging.WARNING)  # Réduire les logs Flask

print("\n" + "━" * 70)
print("🚀 WHATSAPP AI V5 - SERVEUR DE DÉBOGAGE")
print("━" * 70)
print("📊 Mode: Débogage complet activé")
print("📁 Logs sauvegardés dans: debug_log_*.log")
print("🔍 Interface lisible et compacte")
print("━" * 70)

from app import create_app

# Créer l'application au niveau global pour Gunicorn
app = create_app()

if __name__ == "__main__":
    port = 8000
    
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🌐 Serveur démarré sur le port {port}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔗 Accès local: http://127.0.0.1:{port}")
    print("━" * 70)
    print("📱 En attente des messages WhatsApp...")
    print("━" * 70)
    
    app.run(host="0.0.0.0", port=port, debug=False)