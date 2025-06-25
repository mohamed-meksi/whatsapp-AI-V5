import sys
from pathlib import Path
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Chemin correct pour l'importation de services.database_service
sys.path.append(str(Path(__file__).parent.parent))

from utils.ai_utils import (
    Tool,
    ToolManager,
    ConversationManager,
    conversation_manager,
    detect_language_from_message,
    generate_response,
    check_if_thread_exists,
    store_thread
)

# Export all the necessary components
__all__ = [
    'Tool',
    'ToolManager',
    'ConversationManager',
    'conversation_manager',
    'detect_language_from_message',
    'generate_response',
    'check_if_thread_exists',
    'store_thread'
]