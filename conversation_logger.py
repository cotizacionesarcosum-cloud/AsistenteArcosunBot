import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class ConversationLogger:
    """Guarda todas las conversaciones para entrenamiento y análisis"""

    def __init__(self, conversations_file: str = "conversations_history.json"):
        self.conversations_file = conversations_file
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Asegura que el archivo de conversaciones existe"""
        if not Path(self.conversations_file).exists():
            self._save_conversations([])
            logger.info(f"Created new conversations file: {self.conversations_file}")

    def _load_conversations(self) -> List[Dict]:
        """Carga todas las conversaciones del archivo"""
        try:
            with open(self.conversations_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading conversations: {str(e)}")
            return []

    def _save_conversations(self, conversations: List[Dict]):
        """Guarda conversaciones al archivo"""
        try:
            with open(self.conversations_file, 'w', encoding='utf-8') as f:
                json.dump(conversations, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving conversations: {str(e)}")

    def log_conversation(self, phone_number: str, messages: List[Dict],
                        lead_analysis: Dict, media_files: Optional[List[Dict]] = None):
        """
        Guarda una conversación completa

        Args:
            phone_number: Número del cliente
            messages: Lista de mensajes intercambiados
            lead_analysis: Análisis de IA del lead
            media_files: Lista de archivos multimedia enviados
        """
        conversations = self._load_conversations()

        conversation_entry = {
            "phone_number": phone_number,
            "timestamp": datetime.now().isoformat(),
            "lead_score": lead_analysis.get("lead_score", 0),
            "lead_type": lead_analysis.get("lead_type", ""),
            "is_qualified": lead_analysis.get("is_qualified_lead", False),
            "messages": [
                {
                    "role": "cliente" if msg["direction"] == "received" else "bot",
                    "text": msg["message_text"],
                    "timestamp": msg["created_at"]
                }
                for msg in messages
            ],
            "project_info": lead_analysis.get("project_info", {}),
            "summary": lead_analysis.get("summary_for_seller", ""),
            "media_files": media_files or []
        }

        conversations.append(conversation_entry)

        # Mantener solo las últimas 500 conversaciones para no crecer indefinidamente
        if len(conversations) > 500:
            conversations = conversations[-500:]

        self._save_conversations(conversations)
        logger.info(f"Logged conversation for {phone_number} (score: {lead_analysis.get('lead_score', 0)})")

    def get_conversations_by_score(self, min_score: int = 7) -> List[Dict]:
        """Obtiene conversaciones calificadas por score"""
        conversations = self._load_conversations()
        return [c for c in conversations if c.get("lead_score", 0) >= min_score]

    def get_recent_conversations(self, limit: int = 50) -> List[Dict]:
        """Obtiene las conversaciones más recientes"""
        conversations = self._load_conversations()
        return conversations[-limit:]

    def export_for_training(self, output_file: str = "training_data.json"):
        """Exporta conversaciones en formato para entrenamiento"""
        conversations = self._load_conversations()

        training_data = {
            "updated_at": datetime.now().isoformat(),
            "total_conversations": len(conversations),
            "qualified_leads": len([c for c in conversations if c.get("is_qualified", False)]),
            "examples": []
        }

        # Filtrar solo conversaciones calificadas para entrenamiento
        for conv in conversations:
            if conv.get("is_qualified", False) and conv.get("lead_score", 0) >= 7:
                training_data["examples"].append({
                    "tipo": conv.get("lead_type", "general"),
                    "conversacion": [
                        {"cliente": msg["text"]} if msg["role"] == "cliente"
                        else {"bot": msg["text"]}
                        for msg in conv.get("messages", [])
                    ],
                    "lead_score": conv.get("lead_score", 0),
                    "motivo_calificacion": conv.get("summary", "")
                })

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(training_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Exported {len(training_data['examples'])} training examples to {output_file}")
        return output_file
