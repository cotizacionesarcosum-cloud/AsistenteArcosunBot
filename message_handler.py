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

        # --- NUEVO: Control de Estados para Formularios (Rolados) ---
        # Estructura: { "telefono": { "step": "waiting_qty", "retries": 0, "data": {} } }
        self.form_states = {} 

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
        self.highest_lead_data = {}  # {phone_number: {data}}
        self.notification_delay = 120  # 2 minutos en segundos
    
    async def process_message(self, from_number: str, message_text: str, message_id: str,
                            media_url: Optional[str] = None, media_type: Optional[str] = None, 
                            message_raw: Optional[Dict] = None):
        """
        Procesa un mensaje entrante.
        Nota: message_raw es el objeto completo de WhatsApp si lo tienes disponible desde main.py
        """
        try:
            # 1. Marcar como leído
            self.client.mark_as_read(message_id)
            self.memory_manager.cleanup_inactive_sessions()

            # -----------------------------------------------------------
            # 2. INTERCEPTAR FLUJOS MANUALES (Antes de guardar o llamar IA)
            # -----------------------------------------------------------
            
            # A) Verificar si el usuario está "atrapado" en un formulario (Rolados)
            if from_number in self.form_states and not media_url:
                # Si está esperando respuesta de texto (kilos, ubicación)
                self.process_rolados_input(from_number, message_text)
                return  # <--- IMPORTANTE: Detener aquí para que NO conteste la IA

            # B) Detectar respuestas interactivas (Botones/Listas) si tenemos el raw
            # (Si no pasas message_raw desde main, asegúrate de adaptar esto)
            if message_raw and message_raw.get("type") == "interactive":
                interaction = message_raw["interactive"]
                
                # Respuesta de LISTA (Selección de producto Rolados)
                if interaction["type"] == "list_reply":
                    sel_id = interaction["list_reply"]["id"]
                    title = interaction["list_reply"]["title"]
                    if sel_id.startswith("rol_"):
                        self.handle_rolados_selection(from_number, sel_id, title)
                        return

                # Respuesta de BOTÓN (Selección de acabado Rolados)
                elif interaction["type"] == "button_reply":
                    btn_id = interaction["button_reply"]["id"]
                    if btn_id.startswith("fin_"):
                        self.handle_finish_selection(from_number, btn_id)
                        return

            # C) Interceptar "2" o "Rolados" en texto plano
            triggers_rolados = ["2", "opcion 2", "opción 2", "rolados", "laminas", "láminas"]
            text_lower = message_text.lower().strip()
            
            if text_lower in triggers_rolados or (len(text_lower) < 10 and "2" in text_lower and "rolados" in text_lower):
                self.start_rolados_flow(from_number)
                return  # <--- Detener IA

            # -----------------------------------------------------------
            # 3. PROCESAMIENTO NORMAL (IA, Base de Datos, etc.)
            # -----------------------------------------------------------

            # Guardar multimedia
            if media_url:
                await self._save_media_file(from_number, media_url, media_type)

            # Guardar mensaje en DB
            message_with_media = message_text
            if media_url:
                message_with_media += f" [ARCHIVO: {media_type}]"
            self.db.save_message(from_number, message_with_media, "received")

            # Verificar usuario nuevo
            is_new_user = not self.db.user_exists(from_number)
            if is_new_user:
                self.db.create_user(from_number)
                await self.send_welcome_message(from_number)
                return

            # Verificar división
            user_division = self.db.get_user_division(from_number)
            if user_division is None:
                await self.ask_division(from_number, message_text)
                return

            # Reactivar usuario y obtener contexto
            self.memory_manager.reactivate_user(from_number)
            context_limit = self.memory_manager.get_fresh_context_limit(from_number)
            conversation_history = self.db.get_conversation_history(from_number, limit=context_limit)

            # --- LLAMADA A LA IA ---
            ai_response = await self.ai.chat(
                message=message_text,
                conversation_history=conversation_history,
                phone_number=from_number,
                user_division=user_division
            )
            
            # Enviar respuesta
            response_text = ai_response.get("response", "")
            if response_text:
                self.client.send_text_message(from_number, response_text)
                self.db.save_message(from_number, response_text, "sent")
            
            # Guardar análisis y logs
            self.db.save_lead_analysis(from_number, ai_response)
            media_files = self.user_media_cache.get(from_number, [])
            self.conversation_logger.log_conversation(
                phone_number=from_number,
                messages=conversation_history + [{"message_text": message_text, "direction": "received"}],
                lead_analysis=ai_response,
                media_files=media_files
            )

            self.last_message_timestamp[from_number] = datetime.now()

            # Lógica de Notificación al Vendedor
            should_notify = await self.ai.should_notify_seller(ai_response)
            current_score = ai_response.get('lead_score', 0)

            logger.info(f"🔍 Lead Score: {current_score}/10, Notificar: {should_notify}")

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
            logger.error(f"Error processing message from {from_number}: {str(e)}")
            try:
                self.client.send_text_message(from_number, "Disculpa, tuve un problema técnico. ¿Podrías repetir?")
            except:
                pass

    # =========================================================================
    # 🧱 FLUJO AUTOMÁTICO DE ROLADOS (State Machine)
    # =========================================================================

    def start_rolados_flow(self, phone_number: str):
        """Paso 1: Muestra lista de materiales predeterminados"""
        # Limpiamos estado anterior
        if phone_number in self.form_states:
            del self.form_states[phone_number]
            
        # Asignamos división en DB para futuras referencias
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
        """Paso 2: Botones de Acabado"""
        if selection_id == "rol_otro":
            self.client.send_text_message(phone_number, "Entendido. Un asesor te contactará.")
            return

        # Guardamos el producto y estado
        self.form_states[phone_number] = {
            "step": "selecting_finish",
            "retries": 0,
            "data": {"producto": title}
        }

        buttons = [
            {"id": "fin_zintro", "title": "Zintro Alum"},
            {"id": "fin_pintro", "title": "Pintro"},
            {"id": "fin_galv", "title": "Galvanizado"}
        ]
        self.client.send_interactive_buttons(phone_number, f"✅ *{title}* seleccionado.\n¿Qué acabado necesitas?", buttons)

    def handle_finish_selection(self, phone_number: str, button_id: str):
        """Paso 3: Pedir Cantidad (Activa espera de texto)"""
        state = self.form_states.get(phone_number, {"data": {}, "retries": 0})
        
        acabado = "Pintro" if "pintro" in button_id else "Zintro" if "zintro" in button_id else "Galvanizado"
        state["data"]["acabado"] = acabado
        
        # ACTUALIZAMOS EL ESTADO: Esperar CANTIDAD
        state["step"] = "waiting_quantity" 
        state["retries"] = 0
        self.form_states[phone_number] = state

        msg = (
            f"👍 Acabado: *{acabado}*.\n\n"
            "🔢 *¿Qué cantidad necesitas?*\n"
            "Puedes responder en **kilos/toneladas** o **medidas**.\n\n"
            "_Ejemplo: '2 toneladas' o '10 láminas de 6 metros'_"
        )
        self.client.send_text_message(phone_number, msg)

    def process_rolados_input(self, phone_number: str, text: str):
        """Maneja el texto del usuario dentro del flujo manual"""
        state = self.form_states.get(phone_number)
        step = state["step"]
        
        # Validación básica
        if len(text) < 2 or text.lower() in ["hola", "buenos dias", "gracias"]:
            state["retries"] += 1
            if state["retries"] >= 3:
                self.handle_rolados_failure(phone_number)
                return
            self.client.send_text_message(phone_number, f"⚠️ No entendí ese dato ({state['retries']}/3). Sé más específico.")
            return

        # Lógica por pasos
        if step == "waiting_quantity":
            state["data"]["cantidad"] = text
            state["step"] = "waiting_location"
            state["retries"] = 0
            self.form_states[phone_number] = state
            self.client.send_text_message(phone_number, "📍 ¿En qué **Estado y Municipio** será la entrega?")
            return

        elif step == "waiting_location":
            state["data"]["ubicacion"] = text
            data = state["data"]
            
            # Resumen y Despedida
            summary = (
                "✅ *¡Datos Recibidos Exitosamente!*\n\n"
                "📝 Resumen de solicitud:\n"
                f"• Producto: {data.get('producto')}\n"
                f"• Acabado: {data.get('acabado')}\n"
                f"• Cantidad: {data.get('cantidad')}\n"
                f"• Ubicación: {text}\n\n"
                "👨‍💻 Un agente está calculando tu cotización y te contactará en breve.\n\n"
                "👋 *¡Gracias por elegir ARCOSUM!*"
            )
            self.client.send_text_message(phone_number, summary)
            
            # Guardar como log importante
            self.db.save_message(phone_number, f"LEAD ROLADOS COMPLETO: {data}", "system")
            
            # Liberar usuario
            del self.form_states[phone_number]
            return

    def handle_rolados_failure(self, phone_number: str):
        """Se activa tras 3 intentos fallidos"""
        seller_phone = "522221148841"
        msg = (
            "⚠️ *No pude entender tu respuesta.*\n\n"
            "Te comparto el contacto directo de nuestro especialista en Rolados:\n"
            f"👤 *Omar Hernández*: https://wa.me/{seller_phone}\n"
        )
        self.client.send_text_message(phone_number, msg)
        if phone_number in self.form_states:
            del self.form_states[phone_number]

    # =========================================================================
    # OTROS MÉTODOS EXISTENTES
    # =========================================================================

    async def _save_media_file(self, phone_number: str, media_url: str, media_type: str):
        if phone_number not in self.user_media_cache:
            self.user_media_cache[phone_number] = []
        self.user_media_cache[phone_number].append({
            "url": media_url, "type": media_type, "timestamp": datetime.now().isoformat()
        })
        if len(self.user_media_cache[phone_number]) > 5:
            self.user_media_cache[phone_number] = self.user_media_cache[phone_number][-5:]
        logger.info(f"📎 Archivo multimedia guardado: {media_type} de {phone_number}")

    async def _schedule_notification(self, phone_number: str):
        try:
            logger.info(f"⏳ Iniciando temporizador para {phone_number}")
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
            if media_files:
                notification_message += f"\n\n📎 *ARCHIVOS ADJUNTOS:* {len(media_files)}"
                for idx, media in enumerate(media_files, 1):
                    notification_message += f"\n{idx}. {media['type']} - {media['url']}"

            lead_data = {
                "phone_number": phone_number,
                "lead_score": ai_analysis.get("lead_score", 0),
                "lead_type": ai_analysis.get("lead_type", ""),
                "division": division_db,
                "project_info": ai_analysis.get("project_info", {}),
                "summary_for_seller": ai_analysis.get("summary_for_seller", ""),
                "next_action": ai_analysis.get("next_action", ""),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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

        tiene_techos = any(k in message_lower for k in techos_keywords)
        tiene_rolados = any(k in message_lower for k in rolados_keywords)

        if message_text.strip() == "1" or tiene_techos:
            self.db.set_user_division(to, "techos")
            msg = "Perfecto! 🏗️ Te atenderé para *ARCOSUM TECHOS*.\n¿En qué puedo ayudarte hoy?"
            self.client.send_text_message(to, msg)
        elif message_text.strip() == "2" or tiene_rolados:
            # Aunque interceptamos "2", esto es un fallback por si entra por aquí
            self.start_rolados_flow(to)
        else:
            msg = "Por favor elige una opción:\n\n🏗️ *1* - TECHOS\n🔧 *2* - ROLADOS"
            self.client.send_text_message(to, msg)

    # ... (Resto de métodos: handle_quote_request, handle_pricing, etc. se mantienen igual)
    async def handle_quote_request(self, to: str, original_message: str):
        response = "Para cotizar necesito: Tipo de proyecto, dimensiones, ubicación y tiempo estimado."
        self.client.send_text_message(to, response)

    async def handle_pricing(self, to: str, original_message: str):
        response = "Nuestros precios varían. ¿Te gustaría solicitar una cotización personalizada?"
        buttons = [{"id": "btn_yes_quote", "title": "✅ Sí, cotizar"}, {"id": "btn_back", "title": "⬅️ Menú"}]
        self.client.send_interactive_buttons(to, response, buttons)

    async def handle_services(self, to: str, original_message: str):
        response = "*NUESTROS SERVICIOS*\nArcotechos, Estructuras y Laminados."
        self.client.send_text_message(to, response)

    async def handle_contact(self, to: str, original_message: str):
        response = "*CONTACTO*\nTel: +52 222 123 4567\nWeb: www.arcosum.com"
        buttons = [{"id": "btn_call_me", "title": "📞 Llamarme"}, {"id": "btn_menu", "title": "⬅️ Menú"}]
        self.client.send_interactive_buttons(to, response, buttons)

    async def handle_schedule(self, to: str, original_message: str):
        response = "*HORARIO*\nLunes a Viernes: 8:00 AM - 6:00 PM\nSábados: 8:00 AM - 1:00 PM"
        self.client.send_text_message(to, response)