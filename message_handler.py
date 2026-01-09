import logging
from typing import Dict, Optional, List
from datetime import datetime
import asyncio
from handlers_techos import TechosHandler
from handlers_rolados import RoladosHandler
from handlers_otros import OtrosHandler
from handlers_suministros import SuministrosHandler

logger = logging.getLogger(__name__)

class MessageHandler:
    """Orquestador principal de mensajes"""

    def __init__(self, whatsapp_client, database, ai_assistant, notification_service):
        self.client = whatsapp_client
        self.db = database
        self.ai = ai_assistant
        self.notifier = notification_service
        
        # Inicializar handlers especializados
        self.techos_handler = TechosHandler(whatsapp_client, database, ai_assistant, notification_service)
        self.rolados_handler = RoladosHandler(whatsapp_client, database, ai_assistant, notification_service)
        self.suministros_handler = SuministrosHandler(whatsapp_client, database, ai_assistant, notification_service)
        self.otros_handler = OtrosHandler(whatsapp_client, database, ai_assistant, notification_service)
        
        # Rastrear división del usuario
        self.user_division = {}  # {phone_number: "techos" | "rolados" | "suministros" | "otros"}

    async def process_message(self, from_number: str, message_text: str, message_id: str,
                            media_url: Optional[str] = None, media_type: Optional[str] = None):
        """
        Procesa mensaje entrante
        
        Args:
            from_number: Número de teléfono
            message_text: Contenido del mensaje
            message_id: ID del mensaje (para marcar como leído)
            media_url: URL de multimedia (opcional)
            media_type: Tipo de multimedia (opcional)
        """
        try:
            # Marcar como leído
            self.client.mark_as_read(message_id)
            
            # Guardar mensaje
            self.db.save_message(from_number, message_text, "received")
            
            # Verificar si es usuario nuevo
            is_new_user = not self.db.user_exists(from_number)
            
            if is_new_user:
                self.db.create_user(from_number)
                await self.send_welcome_menu(from_number)
                return
            
            # Verificar si el usuario tiene división asignada
            if from_number not in self.user_division:
                division = self.db.get_user_division(from_number)
                if division:
                    self.user_division[from_number] = division
                else:
                    # Mostrar menú de nuevo
                    await self.send_welcome_menu(from_number)
                    return
            
            user_division = self.user_division[from_number]
            
            # Enrutar a handler correspondiente
            if user_division == "techos":
                await self.techos_handler.handle_techos_message(from_number, message_text, message_id)
            
            elif user_division == "rolados":
                await self.rolados_handler.handle_rolados_message(from_number, message_text, message_id)
            
            elif user_division == "suministros":
                await self.suministros_handler.handle_suministros_message(from_number, message_text, message_id)
            
            elif user_division == "otros":
                await self.otros_handler.handle_otros_message(from_number, message_text, message_id)
            
            logger.info(f"✅ Mensaje procesado para {from_number} - División: {user_division}")
            
        except Exception as e:
            logger.error(f"Error procesando mensaje de {from_number}: {str(e)}")
            try:
                self.client.send_text_message(
                    from_number,
                    "⚠️ Disculpa, tuve un problema técnico. ¿Podrías intentar de nuevo?"
                )
            except:
                pass

    async def send_welcome_menu(self, to: str):
        """Envía menú de bienvenida mejorado"""
        
        message = """¡Hola! 👋 Soy el asistente virtual de ARCOSUM.

¿A qué división deseas acudir?

🏗️ *1 - ARCOSUM TECHOS*
Arcotechos y estructuras metálicas

🔧 *2 - ARCOSUM ROLADOS*
Laminados y suministros industriales

🏢 *3 - ARCOSUM SUMINISTROS*
Láminas, extractores, vigas y más

❓ *4 - OTROS*
Consultas generales y más

¿Qué necesitas? Responde con: 1, 2, 3 o 4"""
        
        self.client.send_text_message(to, message)
        self.db.save_message(to, message, "sent")
        
        logger.info(f"📋 Menú de bienvenida enviado a {to}")

    async def handle_division_selection(self, from_number: str, selection: str):
        """
        Procesa la selección de división
        
        Args:
            from_number: Número del cliente
            selection: Número de división (1, 2, 3, 4)
        """
        
        selection = selection.strip()
        
        if selection == "1":
            self.user_division[from_number] = "techos"
            self.db.set_user_division(from_number, "techos")
            
            message = """✅ Perfecto! Te atenderé para **ARCOSUM TECHOS**

Arcotechos y estructuras metálicas.

Déjame preparar el formulario...

⏳ Un momento por favor..."""
            
            self.client.send_text_message(from_number, message)
            self.db.save_message(from_number, message, "sent")
            
            # Iniciar formulario de TECHOS
            await asyncio.sleep(1)
            await self.techos_handler._init_techos_form(from_number)
            
            logger.info(f"🏗️ División TECHOS asignada a {from_number}")
        
        elif selection == "2":
            self.user_division[from_number] = "rolados"
            self.db.set_user_division(from_number, "rolados")
            
            message = """✅ Perfecto! Te atenderé para **ARCOSUM ROLADOS**

Laminados y suministros industriales.

Déjame preparar el formulario...

⏳ Un momento por favor..."""
            
            self.client.send_text_message(from_number, message)
            self.db.save_message(from_number, message, "sent")
            
            # Iniciar formulario de ROLADOS
            await asyncio.sleep(1)
            await self.rolados_handler._init_rolados_form(from_number)
            
            logger.info(f"🔧 División ROLADOS asignada a {from_number}")
        
        elif selection == "3":
            self.user_division[from_number] = "suministros"
            self.db.set_user_division(from_number, "suministros")
            
            message = """✅ Perfecto! Te atenderé para **ARCOSUM SUMINISTROS**

Láminas, extractores, vigas y más.

Déjame preparar el formulario...

⏳ Un momento por favor..."""
            
            self.client.send_text_message(from_number, message)
            self.db.save_message(from_number, message, "sent")
            
            # Iniciar formulario de SUMINISTROS
            await asyncio.sleep(1)
            await self.suministros_handler._init_suministros_form(from_number)
            
            logger.info(f"🏢 División SUMINISTROS asignada a {from_number}")
        
        elif selection == "4":
            self.user_division[from_number] = "otros"
            self.db.set_user_division(from_number, "otros")
            
            message = """✅ Perfecto! Recibiremos tu consulta general.

Déjame preparar el formulario...

⏳ Un momento por favor..."""
            
            self.client.send_text_message(from_number, message)
            self.db.save_message(from_number, message, "sent")
            
            # Iniciar formulario de OTROS
            await asyncio.sleep(1)
            await self.otros_handler._init_otros_form(from_number)
            
            logger.info(f"❓ División OTROS asignada a {from_number}")
        
        else:
            # Opción inválida, mostrar menú de nuevo
            message = """❌ Opción no válida.

Por favor responde con:
1️⃣ Techos
2️⃣ Rolados
3️⃣ Suministros
4️⃣ Otros"""
            
            self.client.send_text_message(from_number, message)
            self.db.save_message(from_number, message, "sent")

    async def process_message_with_ai(self, from_number: str, message_text: str, message_id: str):
        """
        Procesa mensaje con soporte de IA (para mensaje inicial sin división asignada)
        """
        
        # Detectar si está intentando seleccionar división
        message_lower = message_text.lower().strip()
        
        # Palabras clave para TECHOS
        if message_text.strip() == "1" or any(kw in message_lower for kw in ["techo", "arcotecho", "estructura"]):
            await self.handle_division_selection(from_number, "1")
        
        # Palabras clave para ROLADOS
        elif message_text.strip() == "2" or any(kw in message_lower for kw in ["rolado", "lamina", "laminado"]):
            await self.handle_division_selection(from_number, "2")
        
        # Palabras clave para SUMINISTROS
        elif message_text.strip() == "3" or "suministro" in message_lower:
            await self.handle_division_selection(from_number, "3")
        
        # Palabras clave para OTROS
        elif message_text.strip() == "4" or any(kw in message_lower for kw in ["otro", "consulta", "general"]):
            await self.handle_division_selection(from_number, "4")
        
        else:
            # No se detectó división, mostrar menú
            await self.send_welcome_menu(from_number)