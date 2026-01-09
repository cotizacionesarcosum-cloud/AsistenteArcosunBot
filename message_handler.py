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
        
        # Inicializar handlers especializados (pasando self como message_handler)
        self.techos_handler = TechosHandler(whatsapp_client, database, ai_assistant, notification_service, self)
        self.rolados_handler = RoladosHandler(whatsapp_client, database, ai_assistant, notification_service, self)
        self.suministros_handler = SuministrosHandler(whatsapp_client, database, ai_assistant, notification_service, self)
        self.otros_handler = OtrosHandler(whatsapp_client, database, ai_assistant, notification_service, self)
        
        # Rastrear división del usuario (cache en memoria)
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
            
            # Cargar división de BD (verificar si ya fue asignada)
            division_from_db = self.db.get_user_division(from_number)
            
            # Si ya tiene división asignada, usar esa
            if division_from_db:
                self.user_division[from_number] = division_from_db
                user_division = division_from_db
                logger.info(f"✅ División cargada de BD: {user_division} para {from_number}")
            else:
                # Si NO tiene división, intentar detectarla del mensaje
                detected_division = self._detect_division_from_message(message_text)
                
                if detected_division:
                    # Manejar cierre de chat
                    if detected_division == "cerrar":
                        await self.close_chat(from_number)
                        return
                    
                    # Asignar y guardar en BD
                    await self.handle_division_selection(from_number, detected_division)
                    return
                else:
                    # No se detectó división, mostrar menú de nuevo
                    await self.send_welcome_menu(from_number)
                    return
            
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

    def _detect_division_from_message(self, message_text: str) -> Optional[str]:
        """
        Detecta la división basada en el mensaje del usuario
        
        Returns:
            "techos", "rolados", "suministros", "otros", "cerrar" o None
        """
        message_lower = message_text.lower().strip()
        
        # Detección numérica (principal)
        if message_text.strip() == "1":
            return "techos"
        elif message_text.strip() == "2":
            return "rolados"
        elif message_text.strip() == "3":
            return "suministros"
        elif message_text.strip() == "4":
            return "otros"
        elif message_text.strip() == "5":
            return "cerrar"
        
        # Detección por palabras clave (fallback)
        if any(kw in message_lower for kw in ["techo", "arcotecho", "estructura", "metalica"]):
            return "techos"
        elif any(kw in message_lower for kw in ["rolado", "lamina", "laminado", "calibre"]):
            return "rolados"
        elif "suministro" in message_lower:
            return "suministros"
        elif any(kw in message_lower for kw in ["otro", "consulta", "general"]):
            return "otros"
        elif any(kw in message_lower for kw in ["cerrar", "cerrar chat", "no necesito", "listo", "gracias"]):
            return "cerrar"
        
        return None

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

👋 *5 - CERRAR CHAT*
No necesito nada más

¿Qué necesitas? Responde con: 1, 2, 3, 4 o 5"""
        
        self.client.send_text_message(to, message)
        self.db.save_message(to, message, "sent")
        
        logger.info(f"📋 Menú de bienvenida enviado a {to}")

    async def send_main_menu(self, to: str):
        """Envía menú principal después de completar un formulario"""
        
        # Reset: Limpiar la división actual para que pueda seleccionar otra
        self.db.set_user_division(to, None)
        if to in self.user_division:
            del self.user_division[to]
        
        logger.info(f"🔄 División reseteada para {to}")
        
        # Mostrar el mismo menú de bienvenida
        await self.send_welcome_menu(to)

    async def close_chat(self, from_number: str):
        """Cierra el chat y despide al usuario"""
        
        closing_message = """👋 ¡Que tengas un excelente día!

Gracias por usar ARCOSUM.

Si necesitas algo en el futuro, estaremos aquí para ayudarte. 🏭"""
        
        self.client.send_text_message(from_number, closing_message)
        self.db.save_message(from_number, closing_message, "sent")
        
        logger.info(f"👋 Chat cerrado para {from_number}")

    async def handle_division_selection(self, from_number: str, selection: str):
        """
        Procesa la selección de división
        
        Args:
            from_number: Número del cliente
            selection: Código de división ("techos", "rolados", "suministros", "otros") o número (1, 2, 3, 4, 5)
        """
        
        selection = selection.strip()
        
        # Mapeo de números a divisiones
        division_map = {
            "1": "techos",
            "techos": "techos",
            "2": "rolados",
            "rolados": "rolados",
            "3": "suministros",
            "suministros": "suministros",
            "4": "otros",
            "otros": "otros",
            "5": "cerrar",
            "cerrar": "cerrar"
        }
        
        division = division_map.get(selection.lower())
        
        if not division:
            # Opción inválida
            message = """❌ Opción no válida.

Por favor responde con:
1️⃣ Techos
2️⃣ Rolados
3️⃣ Suministros
4️⃣ Otros
5️⃣ Cerrar chat"""
            
            self.client.send_text_message(from_number, message)
            self.db.save_message(from_number, message, "sent")
            return
        
        # Manejar cierre de chat
        if division == "cerrar":
            await self.close_chat(from_number)
            return
        
        # ✅ GUARDAR DIVISIÓN EN LA BD ← CRITICAL
        self.db.set_user_division(from_number, division)
        logger.info(f"💾 División '{division}' guardada en BD para {from_number}")
        
        # Actualizar cache en memoria
        self.user_division[from_number] = division
        
        # Enviar mensaje de confirmación
        division_messages = {
            "techos": """✅ Perfecto! Te atenderé para **ARCOSUM TECHOS**

Arcotechos y estructuras metálicas.

Déjame preparar el formulario...

⏳ Un momento por favor...""",
            
            "rolados": """✅ Perfecto! Te atenderé para **ARCOSUM ROLADOS**

Laminados y suministros industriales.

Déjame preparar el formulario...

⏳ Un momento por favor...""",
            
            "suministros": """✅ Perfecto! Te atenderé para **ARCOSUM SUMINISTROS**

Láminas, extractores, vigas y más.

Déjame preparar el formulario...

⏳ Un momento por favor...""",
            
            "otros": """✅ Perfecto! Recibiremos tu consulta general.

Déjame preparar el formulario...

⏳ Un momento por favor..."""
        }
        
        message = division_messages.get(division, "")
        self.client.send_text_message(from_number, message)
        self.db.save_message(from_number, message, "sent")
        
        # Esperar un poco y luego iniciar formulario
        await asyncio.sleep(1.5)
        
        # Iniciar formulario según división
        if division == "techos":
            await self.techos_handler._init_techos_form(from_number)
            logger.info(f"🏗️ División TECHOS asignada e iniciada para {from_number}")
        
        elif division == "rolados":
            await self.rolados_handler._init_rolados_form(from_number)
            logger.info(f"🔧 División ROLADOS asignada e iniciada para {from_number}")
        
        elif division == "suministros":
            await self.suministros_handler._init_suministros_form(from_number)
            logger.info(f"🏢 División SUMINISTROS asignada e iniciada para {from_number}")
        
        elif division == "otros":
            await self.otros_handler._init_otros_form(from_number)
            logger.info(f"❓ División OTROS asignada e iniciada para {from_number}")