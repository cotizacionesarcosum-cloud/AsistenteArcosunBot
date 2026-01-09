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

        self.conversation_logger = ConversationLogger()
        self.memory_manager = MemoryManager(database)

        self.form_states = {} 

        self.menu_keywords = ["menu", "menú", "inicio", "hola", "ayuda", "help"]
        self.commands = {
            "cotizacion": self.handle_quote_request,
            "cotización": self.handle_quote_request,
            "precios": self.handle_pricing,
            "servicios": self.handle_services,
            "contacto": self.handle_contact,
            "horario": self.handle_schedule,
        }

        self.user_media_cache = {}
        self.pending_notifications = {}
        self.last_message_timestamp = {}
        self.highest_lead_data = {}
        self.notification_delay = 120
    
    async def process_message(self, from_number: str, message_text: str, message_id: str,
                            media_url: Optional[str] = None, media_type: Optional[str] = None, 
                            message_raw: Optional[Dict] = None):
        """Procesa un mensaje entrante."""
        try:
            self.client.mark_as_read(message_id)
            self.memory_manager.cleanup_inactive_sessions()

            # DEBUG: Ver estado actual del usuario
            current_state = self.form_states.get(from_number)
            logger.info(f"👤 Usuario: {from_number} | Estado Actual: {current_state}")

            # ---------------------------------------------------------------
            # 1. BOTONES Y LISTAS (Prioridad Máxima)
            # ---------------------------------------------------------------
            if message_raw and message_raw.get("type") == "interactive":
                interaction = message_raw["interactive"]
                
                if interaction["type"] == "list_reply":
                    sel_id = interaction["list_reply"]["id"]
                    title = interaction["list_reply"]["title"]
                    if sel_id.startswith("rol_"):
                        logger.info(f"🔘 Selección de Lista: {title}")
                        self.handle_rolados_selection(from_number, sel_id, title)
                        return

                elif interaction["type"] == "button_reply":
                    btn_id = interaction["button_reply"]["id"]
                    if btn_id.startswith("fin_"):
                        logger.info(f"🔘 Selección de Botón: {btn_id}")
                        self.handle_finish_selection(from_number, btn_id)
                        return

            # ---------------------------------------------------------------
            # 2. TEXTO DENTRO DEL FORMULARIO
            # ---------------------------------------------------------------
            # Si el usuario tiene un estado activo y escribe texto (no botones)
            if current_state and not media_url:
                step = current_state.get("step")
                # Solo interceptamos si estamos esperando Cantidad o Ubicación
                if step in ["waiting_quantity", "waiting_location"]:
                    logger.info(f"📝 Procesando input de formulario: {message_text} (Paso: {step})")
                    self.process_rolados_input(from_number, message_text)
                    return 

            # ---------------------------------------------------------------
            # 3. COMANDOS DE TEXTO (Menú Rolados)
            # ---------------------------------------------------------------
            text_lower = message_text.lower().strip()
            triggers_rolados = ["2", "opcion 2", "opción 2", "rolados", "laminas", "láminas"]
            
            if text_lower in triggers_rolados or (len(text_lower) < 15 and "2" in text_lower and "rolados" in text_lower):
                logger.info("🚀 Iniciando flujo de Rolados por comando de texto")
                self.start_rolados_flow(from_number)
                return

            # ---------------------------------------------------------------
            # 4. IA (Si no cayó en nada anterior)
            # ---------------------------------------------------------------
            # (Aquí va tu lógica normal de IA y Base de Datos...)
            
            if media_url:
                await self._save_media_file(from_number, media_url, media_type)

            message_with_media = message_text
            if media_url:
                message_with_media += f" [ARCHIVO: {media_type}]"
            self.db.save_message(from_number, message_with_media, "received")

            is_new_user = not self.db.user_exists(from_number)
            if is_new_user:
                self.db.create_user(from_number)
                await self.send_welcome_message(from_number)
                return

            user_division = self.db.get_user_division(from_number)
            if user_division is None:
                await self.ask_division(from_number, message_text)
                return

            self.memory_manager.reactivate_user(from_number)
            context_limit = self.memory_manager.get_fresh_context_limit(from_number)
            conversation_history = self.db.get_conversation_history(from_number, limit=context_limit)

            ai_response = await self.ai.chat(
                message=message_text,
                conversation_history=conversation_history,
                phone_number=from_number,
                user_division=user_division
            )
            
            response_text = ai_response.get("response", "")
            if response_text:
                self.client.send_text_message(from_number, response_text)
                self.db.save_message(from_number, response_text, "sent")
            
            self.db.save_lead_analysis(from_number, ai_response)
            media_files = self.user_media_cache.get(from_number, [])
            self.conversation_logger.log_conversation(
                phone_number=from_number,
                messages=conversation_history + [{"message_text": message_text, "direction": "received"}],
                lead_analysis=ai_response,
                media_files=media_files
            )

            self.last_message_timestamp[from_number] = datetime.now()

            should_notify = await self.ai.should_notify_seller(ai_response)
            current_score = ai_response.get('lead_score', 0)

            if should_notify:
                if from_number not in self.highest_lead_data or current_score > self.highest_lead_data[from_number]['score']:
                    self.highest_lead_data[from_number] = {
                        'ai_analysis': ai_response,
                        'score': current_score,
                        'conversation_history': conversation_history,
                        'media_files': media_files,
                        'message_id': message_id
                    }

                if from_number in self.pending_notifications:
                    self.pending_notifications[from_number].cancel()

                task = asyncio.create_task(self._schedule_notification(from_number))
                self.pending_notifications[from_number] = task

        except Exception as e:
            logger.error(f"❌ Error CRÍTICO en process_message: {str(e)}")

    # =========================================================================
    # 🧱 FLUJO AUTOMÁTICO DE ROLADOS
    # =========================================================================

    def start_rolados_flow(self, phone_number: str):
        """Paso 1: Muestra lista de materiales"""
        if phone_number in self.form_states:
            del self.form_states[phone_number]
            
        self.db.set_user_division(phone_number, "rolados")

        sections = [
            {
                "title": "Perfiles Disponibles",
                "rows": [
                    {"id": "rol_span1", "title": "Span 1", "description": "Perfil estructural"},
                    {"id": "rol_span2", "title": "Span 2", "description": "Perfil estructural"},
                    {"id": "rol_r101", "title": "Lámina R-101", "description": "Muros y cubiertas"}
                ]
            },
            {
                "title": "Otros",
                "rows": [{"id": "rol_otro", "title": "Otro Material", "description": "Consultar asesor"}]
            }
        ]
        
        text = "🔧 *ARCOSUM ROLADOS*\n\nPara cotizar, selecciona el perfil que necesitas:"
        self.client.send_interactive_list(phone_number, text, "Ver Perfiles", sections)
        self.db.save_message(phone_number, text, "sent")

    def handle_rolados_selection(self, phone_number: str, selection_id: str, title: str):
        """Paso 2: Botones de Acabado (Sin Galvanizado)"""
        if selection_id == "rol_otro":
            self.client.send_text_message(phone_number, "Entendido. Un asesor te contactará.")
            return

        self.form_states[phone_number] = {
            "step": "selecting_finish",
            "retries": 0,
            "data": {"producto": title}
        }
        logger.info(f"✅ Guardado estado inicial para {phone_number}: selecting_finish")

        buttons = [
            {"id": "fin_zintro", "title": "Zintro Alum"},
            {"id": "fin_pintro", "title": "Pintro"},
        ]
        self.client.send_interactive_buttons(phone_number, f"✅ *{title}* seleccionado.\n¿Qué acabado necesitas?", buttons)

    def handle_finish_selection(self, phone_number: str, button_id: str):
        """Paso 3: Guarda Acabado y pide Cantidad"""
        # Recuperar estado o crear uno nuevo si falló la persistencia
        state = self.form_states.get(phone_number, {"data": {}, "retries": 0})
        
        acabado = "Pintro" if "pintro" in button_id else "Zintro Alum"
        state["data"]["acabado"] = acabado
        
        # ACTUALIZAR ESTADO
        state["step"] = "waiting_quantity" 
        state["retries"] = 0
        self.form_states[phone_number] = state
        
        logger.info(f"✅ Estado actualizado a: waiting_quantity. Datos: {state['data']}")

        msg = (
            f"👍 Acabado: *{acabado}*.\n\n"
            "🔢 *¿Qué cantidad necesitas?*\n"
            "Responde con **kilos, toneladas** o **medidas**.\n\n"
            "_Ejemplo: '2 toneladas' o '10 láminas de 6 metros'_"
        )
        self.client.send_text_message(phone_number, msg)

    def process_rolados_input(self, phone_number: str, text: str):
        """Maneja el texto (Cantidad y Ubicación)"""
        state = self.form_states.get(phone_number)
        
        if not state:
            logger.error(f"❌ Error: Se intentó procesar input pero no hay estado para {phone_number}")
            return

        step = state["step"]
        logger.info(f"🔄 Procesando input Rolados. Paso actual: {step}. Texto: {text}")

        # Validación básica
        if len(text) < 2:
            state["retries"] += 1
            self.client.send_text_message(phone_number, "⚠️ Por favor sé más específico.")
            return

        # PASO 4: Recibir Cantidad -> Pedir Ubicación
        if step == "waiting_quantity":
            state["data"]["cantidad"] = text
            state["step"] = "waiting_location"
            state["retries"] = 0
            self.form_states[phone_number] = state
            
            logger.info("✅ Cantidad recibida. Pidiendo ubicación.")
            self.client.send_text_message(phone_number, "📍 ¿En qué **Estado y Municipio** será la entrega?")
            return

        # PASO 5: Recibir Ubicación -> Finalizar
        elif step == "waiting_location":
            state["data"]["ubicacion"] = text
            data = state["data"]
            
            logger.info(f"✅ Flujo completo. Datos finales: {data}")
            
            summary = (
                "✅ *¡Datos Recibidos Exitosamente!*\n\n"
                "📝 Resumen de solicitud:\n"
                f"• Producto: {data.get('producto')}\n"
                f"• Acabado: {data.get('acabado')}\n"
                f"• Cantidad: {data.get('cantidad')}\n"
                f"• Ubicación: {text}\n\n"
                "👨‍💻 Un agente te contactará en breve con tu cotización.\n\n"
                "👋 *¡Gracias por elegir ARCOSUM!*"
            )
            self.client.send_text_message(phone_number, summary)
            
            self.db.save_message(phone_number, f"LEAD ROLADOS COMPLETO: {data}", "system")
            
            # Notificar vendedor inmediatamente
            asyncio.create_task(self.notify_rolados_lead(phone_number, data))
            
            # Limpiar estado
            del self.form_states[phone_number]
            return

    async def notify_rolados_lead(self, phone_number: str, data: dict):
        """Notifica al vendedor de rolados (función helper)"""
        try:
            msg = (
                "🔔 *NUEVO LEAD ROLADOS (Formulario)*\n\n"
                f"👤 Cliente: {phone_number}\n"
                f"🏗️ Producto: {data.get('producto')}\n"
                f"🎨 Acabado: {data.get('acabado')}\n"
                f"🔢 Cantidad: {data.get('cantidad')}\n"
                f"📍 Ubicación: {data.get('ubicacion')}"
            )
            lead_data = {
                "phone_number": phone_number,
                "lead_score": 10,
                "lead_type": "cotizacion_rolados",
                "division": "rolados",
                "summary_for_seller": msg
            }
            await self.notifier.notify_qualified_lead(lead_data, msg)
        except Exception as e:
            logger.error(f"Error notificando lead rolados: {e}")

    def handle_rolados_failure(self, phone_number: str):
        seller_phone = "522221148841"
        msg = (
            "⚠️ *No pude entender tu respuesta.*\n\n"
            f"Contacta directo a nuestro especialista:\n👤 *Omar Hernández*: https://wa.me/{seller_phone}"
        )
        self.client.send_text_message(phone_number, msg)
        if phone_number in self.form_states:
            del self.form_states[phone_number]

    # =========================================================================
    # OTROS MÉTODOS (Sin cambios significativos, solo requeridos por la clase)
    # =========================================================================
    
    async def _save_media_file(self, phone_number: str, media_url: str, media_type: str):
        if phone_number not in self.user_media_cache:
            self.user_media_cache[phone_number] = []
        self.user_media_cache[phone_number].append({
            "url": media_url, "type": media_type, "timestamp": datetime.now().isoformat()
        })

    async def _schedule_notification(self, phone_number: str):
        try:
            await asyncio.sleep(self.notification_delay)
            if phone_number in self.last_message_timestamp:
                time_since_last = (datetime.now() - self.last_message_timestamp[phone_number]).total_seconds()
                if time_since_last >= self.notification_delay - 5:
                    if phone_number in self.highest_lead_data:
                        lead_data = self.highest_lead_data[phone_number]
                        await self._notify_seller_about_lead(
                            phone_number=phone_number,
                            ai_analysis=lead_data['ai_analysis'],
                            conversation_history=lead_data['conversation_history'],
                            media_files=lead_data['media_files'],
                            last_message_id=lead_data['message_id']
                        )
                        del self.highest_lead_data[phone_number]
                        del self.pending_notifications[phone_number]
                        del self.last_message_timestamp[phone_number]
        except Exception as e:
            logger.error(f"Error en notificación: {str(e)}")

    async def _notify_seller_about_lead(self, phone_number: str, ai_analysis: Dict,
                                      conversation_history: List[Dict],
                                      media_files: Optional[List[Dict]] = None,
                                      last_message_id: Optional[str] = None):
        try:
            division_db = self.db.get_user_division(phone_number)
            notification_message = await self.ai.generate_seller_notification(
                phone_number=phone_number,
                conversation_summary=ai_analysis,
                conversation_history=conversation_history,
                chat_id=phone_number,
                last_message_id=last_message_id
            )
            lead_data = {
                "phone_number": phone_number,
                "lead_score": ai_analysis.get("lead_score", 0),
                "lead_type": ai_analysis.get("lead_type", ""),
                "division": division_db,
                "summary_for_seller": ai_analysis.get("summary_for_seller", ""),
                "media_files": media_files or []
            }
            await self.notifier.notify_qualified_lead(lead_data, notification_message)
        except Exception as e:
            logger.error(f"Error notifying seller: {str(e)}")

    async def send_welcome_message(self, to: str):
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
        message_lower = message_text.lower().strip()
        techos_keywords = ["techo", "arcotecho", "arco", "estructura", "metalica", "nave"]
        rolados_keywords = ["rolado", "lamin", "lamina", "perfil", "acero", "calibre"]

        if message_text.strip() == "1" or any(k in message_lower for k in techos_keywords):
            self.db.set_user_division(to, "techos")
            self.client.send_text_message(to, "Perfecto! 🏗️ Te atenderé para *ARCOSUM TECHOS*.\n¿En qué puedo ayudarte hoy?")
        elif message_text.strip() == "2" or any(k in message_lower for k in rolados_keywords):
            self.start_rolados_flow(to)
        else:
            self.client.send_text_message(to, "Por favor elige una opción:\n\n🏗️ *1* - TECHOS\n🔧 *2* - ROLADOS")

    async def handle_quote_request(self, to: str, original_message: str):
        self.client.send_text_message(to, "Para cotizar necesito: Tipo de proyecto, dimensiones, ubicación y tiempo estimado.")

    async def handle_pricing(self, to: str, original_message: str):
        buttons = [{"id": "btn_yes_quote", "title": "✅ Sí, cotizar"}, {"id": "btn_back", "title": "⬅️ Menú"}]
        self.client.send_interactive_buttons(to, "Nuestros precios varían. ¿Te gustaría solicitar una cotización personalizada?", buttons)

    async def handle_services(self, to: str, original_message: str):
        self.client.send_text_message(to, "*NUESTROS SERVICIOS*\nArcotechos, Estructuras y Laminados.")

    async def handle_contact(self, to: str, original_message: str):
        buttons = [{"id": "btn_call_me", "title": "📞 Llamarme"}, {"id": "btn_menu", "title": "⬅️ Menú"}]
        self.client.send_interactive_buttons(to, "*CONTACTO*\nTel: +52 222 123 4567\nWeb: www.arcosum.com", buttons)

    async def handle_schedule(self, to: str, original_message: str):
        self.client.send_text_message(to, "*HORARIO*\nLunes a Viernes: 8:00 AM - 6:00 PM\nSábados: 8:00 AM - 1:00 PM")