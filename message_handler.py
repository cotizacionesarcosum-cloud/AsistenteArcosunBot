import logging
from typing import Dict, Optional, List
from datetime import datetime
import asyncio
from whatsapp_client import WhatsAppClient
from database import Database
from ai_assistant import AIAssistant
from notification_service import NotificationService
from conversation_logger import ConversationLogger
from memory_manager import MemoryManager

logger = logging.getLogger(__name__)

class MessageHandler:
    """Maneja la lógica de respuestas automáticas del bot con IA"""

    def __init__(self, whatsapp_client: WhatsAppClient, database: Database,
                 ai_assistant: AIAssistant, notification_service: NotificationService):
        self.client = whatsapp_client
        self.db = database
        self.ai = ai_assistant
        self.notifier = notification_service

        # Nuevos componentes
        self.conversation_logger = ConversationLogger()
        self.memory_manager = MemoryManager(database)

        # Palabras clave para menú principal
        self.menu_keywords = ["menu", "menú", "inicio", "hola", "ayuda", "help"]

        # Comandos específicos
        self.commands = {
            "cotizacion": self.handle_quote_request,
            "cotización": self.handle_quote_request,
            "precios": self.handle_pricing,
            "servicios": self.handle_services,
            "contacto": self.handle_contact,
            "horario": self.handle_schedule,
        }

        # Cache temporal de archivos multimedia por usuario
        self.user_media_cache = {}

        # Sistema de debouncing para notificaciones
        self.pending_notifications = {}  # {phone_number: asyncio.Task}
        self.last_message_timestamp = {}  # {phone_number: datetime}
        self.highest_lead_data = {}  # {phone_number: {ai_analysis, score, conversation_history, media_files, message_id}}
        self.notification_delay = 120  # 2 minutos en segundos
    
    async def process_message(self, from_number: str, message_text: str, message_id: str,
                            media_url: Optional[str] = None, media_type: Optional[str] = None):
        """
        Procesa un mensaje entrante usando IA y genera respuesta inteligente

        Args:
            from_number: Número de teléfono del remitente
            message_text: Contenido del mensaje
            message_id: ID del mensaje (para marcarlo como leído)
            media_url: URL del archivo multimedia (imagen, PDF, etc.)
            media_type: Tipo de medio (image, document, etc.)
        """
        try:
            # Marcar mensaje como leído
            self.client.mark_as_read(message_id)

            # Limpiar sesiones inactivas (optimización)
            self.memory_manager.cleanup_inactive_sessions()

            # Guardar archivo multimedia si existe
            if media_url:
                await self._save_media_file(from_number, media_url, media_type)

            # Guardar mensaje en base de datos
            message_with_media = message_text
            if media_url:
                message_with_media += f" [ARCHIVO: {media_type}]"

            self.db.save_message(from_number, message_with_media, "received")

            # Verificar si es primera vez del usuario
            is_new_user = not self.db.user_exists(from_number)

            if is_new_user:
                self.db.create_user(from_number)
                await self.send_welcome_message(from_number)
                return

            # Verificar si el usuario ya tiene división asignada
            user_division = self.db.get_user_division(from_number)

            if user_division is None:
                # Usuario no tiene división, preguntar
                await self.ask_division(from_number, message_text)
                return

            # Reactivar usuario si estaba inactivo
            self.memory_manager.reactivate_user(from_number)

            # Obtener límite de contexto dinámico (optimización de velocidad)
            context_limit = self.memory_manager.get_fresh_context_limit(from_number)

            # Obtener historial de conversación con límite optimizado
            conversation_history = self.db.get_conversation_history(from_number, limit=context_limit)

            # Procesar mensaje con IA (incluir división del usuario)
            ai_response = await self.ai.chat(
                message=message_text,
                conversation_history=conversation_history,
                phone_number=from_number,
                user_division=user_division  # Informar a la IA qué división está atendiendo
            )
            
            # Enviar respuesta al cliente
            response_text = ai_response.get("response", "")
            if response_text:
                self.client.send_text_message(from_number, response_text)
                self.db.save_message(from_number, response_text, "sent")
            
            # Guardar análisis en base de datos
            self.db.save_lead_analysis(from_number, ai_response)

            # Guardar conversación completa para análisis
            media_files = self.user_media_cache.get(from_number, [])
            self.conversation_logger.log_conversation(
                phone_number=from_number,
                messages=conversation_history + [{
                    "message_text": message_text,
                    "direction": "received",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }],
                lead_analysis=ai_response,
                media_files=media_files
            )

            # Actualizar timestamp del último mensaje
            self.last_message_timestamp[from_number] = datetime.now()

            # Verificar si se debe notificar al vendedor
            should_notify = await self.ai.should_notify_seller(ai_response)
            current_score = ai_response.get('lead_score', 0)

            logger.info(f"🔍 Evaluación de notificación - Lead Score: {current_score}/10, "
                       f"Calificado: {ai_response.get('is_qualified_lead', False)}, "
                       f"Tipo: {ai_response.get('lead_type', 'N/A')}, "
                       f"¿Notificar?: {should_notify}")

            if should_notify:
                # Guardar o actualizar el lead con el score más alto
                if from_number not in self.highest_lead_data or current_score > self.highest_lead_data[from_number]['score']:
                    self.highest_lead_data[from_number] = {
                        'ai_analysis': ai_response,
                        'score': current_score,
                        'conversation_history': conversation_history,
                        'media_files': media_files,
                        'message_id': message_id
                    }
                    logger.info(f"📊 Actualizado lead data - Nuevo score más alto: {current_score}/10")

                # Cancelar notificación pendiente si existe
                if from_number in self.pending_notifications:
                    self.pending_notifications[from_number].cancel()
                    logger.info(f"⏸️ Notificación anterior cancelada - Esperando más mensajes")

                # Programar nueva notificación con debounce de 2 minutos
                task = asyncio.create_task(self._schedule_notification(from_number))
                self.pending_notifications[from_number] = task
                logger.info(f"⏰ Notificación programada - Se enviará si no hay mensajes en {self.notification_delay}s")
            else:
                logger.info(f"⏭️ Lead no calificado, no se notifica (score < 6 o no calificado)")

            logger.info(f"Message processed successfully for {from_number}")
            
        except Exception as e:
            logger.error(f"Error processing message from {from_number}: {str(e)}")
            # Intentar enviar mensaje de error al usuario
            try:
                self.client.send_text_message(
                    from_number,
                    "Disculpa, tuve un problema técnico. ¿Podrías repetir tu mensaje?"
                )
            except:
                pass
    
    async def _save_media_file(self, phone_number: str, media_url: str, media_type: str):
        """Guarda información de archivo multimedia en caché"""
        if phone_number not in self.user_media_cache:
            self.user_media_cache[phone_number] = []

        self.user_media_cache[phone_number].append({
            "url": media_url,
            "type": media_type,
            "timestamp": datetime.now().isoformat()
        })

        # Mantener solo los últimos 5 archivos por usuario
        if len(self.user_media_cache[phone_number]) > 5:
            self.user_media_cache[phone_number] = self.user_media_cache[phone_number][-5:]

        logger.info(f"📎 Archivo multimedia guardado: {media_type} de {phone_number}")

    async def _schedule_notification(self, phone_number: str):
        """
        Espera 2 minutos y envía notificación si no hay nuevos mensajes

        Args:
            phone_number: Número del cliente
        """
        try:
            logger.info(f"⏳ Iniciando temporizador de {self.notification_delay}s para {phone_number}")

            # Esperar 2 minutos
            await asyncio.sleep(self.notification_delay)

            # Verificar que no haya llegado un mensaje nuevo durante la espera
            if phone_number in self.last_message_timestamp:
                time_since_last_message = (datetime.now() - self.last_message_timestamp[phone_number]).total_seconds()

                # Si han pasado al menos 2 minutos desde el último mensaje, enviar notificación
                if time_since_last_message >= self.notification_delay - 5:  # Margen de 5 segundos
                    if phone_number in self.highest_lead_data:
                        lead_data = self.highest_lead_data[phone_number]

                        logger.info(f"✅ Enviando notificación FINAL - Lead Score: {lead_data['score']}/10 para {phone_number}")

                        # Enviar notificación con el lead de mayor score
                        await self._notify_seller_about_lead(
                            phone_number=phone_number,
                            ai_analysis=lead_data['ai_analysis'],
                            conversation_history=lead_data['conversation_history'],
                            media_files=lead_data['media_files'],
                            last_message_id=lead_data['message_id']
                        )

                        # Limpiar datos después de enviar
                        del self.highest_lead_data[phone_number]
                        del self.pending_notifications[phone_number]
                        del self.last_message_timestamp[phone_number]

                        logger.info(f"🧹 Datos de notificación limpiados para {phone_number}")
                    else:
                        logger.warning(f"⚠️ No hay datos de lead guardados para {phone_number}")
                else:
                    logger.info(f"🔄 Nuevos mensajes recibidos - Notificación cancelada para {phone_number}")
            else:
                logger.info(f"⚠️ No hay timestamp registrado para {phone_number}")

        except asyncio.CancelledError:
            logger.info(f"❌ Notificación cancelada por nuevo mensaje de {phone_number}")
        except Exception as e:
            logger.error(f"Error en programación de notificación para {phone_number}: {str(e)}")

    async def _notify_seller_about_lead(self, phone_number: str, ai_analysis: Dict,
                                        conversation_history: List[Dict],
                                        media_files: Optional[List[Dict]] = None,
                                        last_message_id: Optional[str] = None):
        """
        Notifica al vendedor sobre un lead calificado

        Args:
            phone_number: Número del cliente
            ai_analysis: Análisis de IA del lead
            conversation_history: Historial de conversación
            media_files: Lista de archivos multimedia enviados por el cliente
            last_message_id: ID del último mensaje de WhatsApp (wamid.xxx)
        """
        try:
            # Obtener división de la base de datos (fuente confiable)
            division_db = self.db.get_user_division(phone_number)

            if not division_db:
                logger.warning(f"⚠️ Usuario {phone_number} no tiene división asignada. No se enviará notificación.")
                return

            logger.info(f"🎯 División desde DB: {division_db}")

            # Generar mensaje para vendedor
            notification_message = await self.ai.generate_seller_notification(
                phone_number=phone_number,
                conversation_summary=ai_analysis,
                conversation_history=conversation_history,
                chat_id=phone_number,
                last_message_id=last_message_id
            )

            # Agregar información de archivos multimedia
            if media_files:
                notification_message += f"\n\n📎 *ARCHIVOS ADJUNTOS:* {len(media_files)}"
                for idx, media in enumerate(media_files, 1):
                    notification_message += f"\n{idx}. {media['type']} - {media['url']}"

            # Preparar datos del lead - USAR DIVISIÓN DE LA BASE DE DATOS
            lead_data = {
                "phone_number": phone_number,
                "lead_score": ai_analysis.get("lead_score", 0),
                "lead_type": ai_analysis.get("lead_type", ""),
                "division": division_db,  # ✅ Usar división de la DB, NO de la IA
                "project_info": ai_analysis.get("project_info", {}),
                "summary_for_seller": ai_analysis.get("summary_for_seller", ""),
                "next_action": ai_analysis.get("next_action", ""),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "media_files": media_files or []
            }

            # Enviar notificación
            await self.notifier.notify_qualified_lead(lead_data, notification_message)

            logger.info(f"Seller notified about qualified lead: {phone_number}")

        except Exception as e:
            logger.error(f"Error notifying seller: {str(e)}")
    
    async def send_welcome_message(self, to: str):
        """Envía mensaje de bienvenida a nuevos usuarios"""
        welcome_text = """¡Hola! 👋 Soy el asistente virtual de ARCOSUM.

Tenemos dos divisiones:

🏗️ **1 - TECHOS**
Arcotechos y estructuras metálicas

🔧 **2 - ROLADOS**
Laminados y suministros industriales

*¿Qué necesitas?* Responde con *1* para Techos o *2* para Rolados."""

        self.client.send_text_message(to, welcome_text)
        self.db.save_message(to, welcome_text, "sent")

    async def ask_division(self, to: str, message_text: str):
        """
        Procesa la selección de división del usuario de forma inteligente

        Args:
            to: Número del usuario
            message_text: Mensaje del usuario
        """
        message_lower = message_text.lower().strip()

        # Palabras clave para TECHOS
        techos_keywords = [
            "techo", "arcotecho", "arco", "estructura", "metalica", "metálica",
            "nave", "bodega", "techado", "cubierta", "span", "galvanizada pintro"
        ]

        # Palabras clave para ROLADOS
        rolados_keywords = [
            "rolado", "lamin", "lamina", "lámina", "perfil", "acero",
            "calibre", "galvanizada", "material", "suministro", "rollo",
            "cal", "hoja", "placa"
        ]

        # Detectar división por palabras clave
        tiene_techos = any(keyword in message_lower for keyword in techos_keywords)
        tiene_rolados = any(keyword in message_lower for keyword in rolados_keywords)

        # Si menciona techos O eligió "1"
        if message_text.strip() == "1" or tiene_techos:
            self.db.set_user_division(to, "techos")
            response = """Perfecto! 🏗️ Te atenderé para *ARCOSUM TECHOS* (Arcotechos y estructuras metálicas).

¿En qué puedo ayudarte hoy?"""
            self.client.send_text_message(to, response)
            self.db.save_message(to, response, "sent")
            logger.info(f"✅ División TECHOS asignada a {to}")

        # Si menciona rolados O eligió "2"
        elif message_text.strip() == "2" or tiene_rolados:
            self.db.set_user_division(to, "rolados")
            response = """Perfecto! 🔧 Te atenderé para *ARCOSUM ROLADOS* (Laminados y suministros industriales).

¿En qué puedo ayudarte hoy?"""
            self.client.send_text_message(to, response)
            self.db.save_message(to, response, "sent")
            logger.info(f"✅ División ROLADOS asignada a {to}")

        else:
            # No se detectó ninguna palabra clave, volver a preguntar
            response = """Por favor elige una opción:

🏗️ *1* - TECHOS (Arcotechos y estructuras)
🔧 *2* - ROLADOS (Laminados y suministros)

Responde con *1* o *2*"""
            self.client.send_text_message(to, response)
            self.db.save_message(to, response, "sent")
            logger.info(f"⚠️ No se detectó división en mensaje de {to}: '{message_text}'")
    
    async def send_main_menu(self, to: str):
        """Envía el menú principal"""
        menu_text = """*MENÚ PRINCIPAL* 🏗️

Selecciona una opción:"""
        
        sections = [
            {
                "title": "Servicios",
                "rows": [
                    {
                        "id": "opt_arcotechos",
                        "title": "Arcotechos",
                        "description": "Techos industriales curvos"
                    },
                    {
                        "id": "opt_estructuras",
                        "title": "Estructuras Metálicas",
                        "description": "Diseño y construcción"
                    },
                    {
                        "id": "opt_laminados",
                        "title": "Laminados",
                        "description": "Láminas y aceros"
                    }
                ]
            },
            {
                "title": "Información",
                "rows": [
                    {
                        "id": "opt_quote",
                        "title": "Solicitar Cotización",
                        "description": "Obtén tu presupuesto"
                    },
                    {
                        "id": "opt_contact",
                        "title": "Contacto",
                        "description": "Hablar con un asesor"
                    }
                ]
            }
        ]
        
        self.client.send_interactive_list(to, menu_text, "Ver Opciones", sections)
        self.db.save_message(to, menu_text, "sent")
    
    async def handle_quote_request(self, to: str, original_message: str):
        """Maneja solicitudes de cotización"""
        response = """*SOLICITUD DE COTIZACIÓN* 📋

Para brindarte una cotización precisa, necesito la siguiente información:

1️⃣ Tipo de proyecto (Arcotecho/Estructura/Laminado)
2️⃣ Dimensiones aproximadas
3️⃣ Ubicación de la obra
4️⃣ Tiempo estimado de ejecución

Por favor comparte estos datos y con gusto te prepararemos una cotización personalizada.

También puedes enviarnos fotos o planos si los tienes."""
        
        self.client.send_text_message(to, response)
        self.db.save_message(to, response, "sent")
        self.db.update_user_state(to, "awaiting_quote_info")
    
    async def handle_pricing(self, to: str, original_message: str):
        """Maneja consultas de precios"""
        response = """*INFORMACIÓN DE PRECIOS* 💰

Nuestros precios varían según:
• Tipo de material
• Dimensiones del proyecto
• Complejidad de instalación
• Ubicación geográfica

Para darte un precio exacto, necesitamos evaluar tu proyecto específico.

¿Te gustaría solicitar una cotización personalizada?"""
        
        buttons = [
            {"id": "btn_yes_quote", "title": "✅ Sí, cotizar"},
            {"id": "btn_projects", "title": "📸 Ver proyectos"},
            {"id": "btn_back", "title": "⬅️ Menú"}
        ]
        
        self.client.send_interactive_buttons(to, response, buttons)
        self.db.save_message(to, response, "sent")
    
    async def handle_services(self, to: str, original_message: str):
        """Maneja consultas sobre servicios"""
        response = """*NUESTROS SERVICIOS* 🏗️

🔹 *Arcotechos Ecológicos*
Sistemas de techado curvo autosoportado, ideal para naves industriales, bodegas y espacios amplios.

🔹 *Estructuras Metálicas*
Diseño, fabricación e instalación de estructuras para construcción industrial y comercial.

🔹 *Laminados*
Suministro de láminas y perfiles de acero para diversos proyectos.

✅ Más de 20 años de experiencia
✅ Garantía en todos nuestros trabajos
✅ Asesoría técnica especializada

¿Sobre qué servicio quieres más información?"""
        
        self.client.send_text_message(to, response)
        self.db.save_message(to, response, "sent")
    
    async def handle_contact(self, to: str, original_message: str):
        """Maneja solicitudes de contacto"""
        response = """*INFORMACIÓN DE CONTACTO* 📞

📱 WhatsApp: +52 222 123 4567
📧 Email: contacto@arcosum.com
🌐 Web: www.arcosum.com

🏢 *Oficina Puebla*
Dirección: [Tu dirección]
Horario: Lunes a Viernes 9:00 - 18:00
Sábados: 9:00 - 14:00

¿Prefieres que un asesor se comunique contigo?"""
        
        buttons = [
            {"id": "btn_call_me", "title": "📞 Llamarme"},
            {"id": "btn_visit", "title": "🏢 Agendar visita"},
            {"id": "btn_menu", "title": "⬅️ Menú"}
        ]
        
        self.client.send_interactive_buttons(to, response, buttons)
        self.db.save_message(to, response, "sent")
    
    async def handle_schedule(self, to: str, original_message: str):
        """Maneja consultas de horarios"""
        response = """*HORARIO DE ATENCIÓN* 🕐

📅 Lunes a Viernes: 8:00 AM - 6:00 PM
📅 Sábados: 8:00 AM - 1:00 PM
📅 Domingos: Cerrado

⚡ *Este chat está disponible 24/7* para recibir tus mensajes. Te responderemos lo antes posible.

Para urgencias, marca al: +52 222 123 4567"""
        
        self.client.send_text_message(to, response)
        self.db.save_message(to, response, "sent")
    
    async def send_default_response(self, to: str, message_text: str):
        """Respuesta por defecto cuando no se reconoce el mensaje"""
        response = """Gracias por tu mensaje. 

Si necesitas ayuda, escribe *"menu"* para ver todas las opciones disponibles.

O cuéntame en qué puedo ayudarte específicamente."""
        
        self.client.send_text_message(to, response)
        self.db.save_message(to, response, "sent")