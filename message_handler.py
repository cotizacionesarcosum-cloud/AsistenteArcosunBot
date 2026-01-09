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

        # NUEVO: Gestión de formularios de ROLADOS
        self.rolados_form_state = {}  # {phone_number: {"step": int, "data": {...}, "retry_count": int}}
        
        # Datos de vendedor ROLADOS
        self.rolados_vendor = {
            "name": "Juan Carlos",
            "phone": "+52 222 987 6543",
            "email": "ventas-rolados@arcosum.com"
        }
        
        # Opciones disponibles para ROLADOS
        self.rolados_options = {
            "tipos_material": [
                {"id": "galvanizada", "title": "Lámina Galvanizada", "description": "Protección contra oxidación"},
                {"id": "pintro", "title": "Lámina Pintro", "description": "Acabado pintado"},
                {"id": "negra", "title": "Lámina Negra", "description": "Acero sin recubrimiento"},
                {"id": "perfiles", "title": "Perfiles", "description": "Ángulos, canales, vigas"},
                {"id": "calibres", "title": "Calibres Especiales", "description": "Calibres diversos"},
            ],
            "calibres": [
                {"id": "cal_16", "title": "Calibre 16", "description": "3.2mm"},
                {"id": "cal_18", "title": "Calibre 18", "description": "2.4mm"},
                {"id": "cal_20", "title": "Calibre 20", "description": "1.6mm"},
                {"id": "cal_22", "title": "Calibre 22", "description": "1.2mm"},
                {"id": "cal_24", "title": "Calibre 24", "description": "0.8mm"},
                {"id": "otro", "title": "Otro Calibre", "description": "Especifica en mensaje"},
            ],
            "dimensiones": [
                {"id": "1200x2400", "title": "1200 x 2400 mm"},
                {"id": "1250x2500", "title": "1250 x 2500 mm"},
                {"id": "rollo", "title": "Rollo (especificar ancho)"},
                {"id": "otro", "title": "Otras Dimensiones", "description": "Especifica en mensaje"},
            ]
        }
    
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

            # NUEVO: Verificar si está en medio de un formulario de ROLADOS
            if user_division == "rolados" and from_number in self.rolados_form_state:
                await self._handle_rolados_form_response(from_number, message_text, message_id)
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

    # ============= NUEVO: GESTIÓN DE FORMULARIO ROLADOS =============

    async def _handle_rolados_form_response(self, phone_number: str, message_text: str, message_id: str):
        """Maneja respuestas del formulario interactivo de ROLADOS"""
        
        state = self.rolados_form_state[phone_number]
        current_step = state["step"]
        retry_count = state.get("retry_count", 0)

        logger.info(f"📋 ROLADOS Form - Step: {current_step}, Retry: {retry_count}, Message: {message_text}")

        try:
            if current_step == 1:  # Nombre
                await self._rolados_step_1_name(phone_number, message_text)
            
            elif current_step == 2:  # Tipo de material
                await self._rolados_step_2_material(phone_number, message_text)
            
            elif current_step == 3:  # Calibre
                await self._rolados_step_3_calibre(phone_number, message_text)
            
            elif current_step == 4:  # Dimensiones
                await self._rolados_step_4_dimensiones(phone_number, message_text)
            
            elif current_step == 5:  # Cantidad en kilos
                await self._rolados_step_5_cantidad(phone_number, message_text)
            
            elif current_step == 6:  # Confirmación
                await self._rolados_step_6_confirmation(phone_number, message_text)

        except Exception as e:
            logger.error(f"Error en formulario ROLADOS para {phone_number}: {str(e)}")
            await self._send_vendor_contact(phone_number)

    async def _init_rolados_form(self, phone_number: str):
        """Inicia el formulario de ROLADOS"""
        self.rolados_form_state[phone_number] = {
            "step": 1,
            "data": {},
            "retry_count": 0
        }
        
        logger.info(f"🆕 Formulario ROLADOS iniciado para {phone_number}")
        
        # Paso 1: Nombre
        await self._rolados_step_1_name(phone_number, None)

    async def _rolados_step_1_name(self, phone_number: str, user_response: Optional[str]):
        """Paso 1: Solicitar nombre"""
        
        if user_response is None:
            # Primera vez, mostrar instrucción
            message = """🏭 *FORMULARIO ROLADOS* 📋

Te ayudaré a preparar tu cotización de forma rápida.

📝 *Paso 1 de 6:* ¿Cuál es tu nombre?

(Por favor escribe tu nombre completo)"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return

        # Validar que sea un nombre válido (no números ni caracteres raros)
        if not self._is_valid_name(user_response):
            state = self.rolados_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ ROLADOS {phone_number} - 3 intentos fallidos en paso 1")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor ingresa un nombre válido (sin números ni caracteres especiales)

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        # Guardar nombre y pasar al siguiente paso
        state = self.rolados_form_state[phone_number]
        state["data"]["nombre"] = user_response.strip()
        state["step"] = 2
        state["retry_count"] = 0
        
        logger.info(f"✅ Nombre guardado: {user_response}")
        
        # Paso 2: Tipo de material
        await self._rolados_step_2_material(phone_number, None)

    async def _rolados_step_2_material(self, phone_number: str, user_response: Optional[str]):
        """Paso 2: Seleccionar tipo de material"""
        
        if user_response is None:
            # Primera vez, mostrar menú
            message = """✅ Gracias, {nombre}!

📝 *Paso 2 de 6:* Selecciona el tipo de material que necesitas:"""
            
            nombre = self.rolados_form_state[phone_number]["data"].get("nombre", "")
            message = message.format(nombre=nombre)
            
            sections = [
                {
                    "title": "Materiales Disponibles",
                    "rows": self.rolados_options["tipos_material"]
                }
            ]
            
            self.client.send_interactive_list(
                phone_number, 
                message,
                "Ver Materiales",
                sections
            )
            self.db.save_message(phone_number, message, "sent")
            return

        # Validar que sea una opción válida
        valid_ids = [opt["id"] for opt in self.rolados_options["tipos_material"]]
        
        if user_response.lower() not in valid_ids:
            state = self.rolados_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ ROLADOS {phone_number} - 3 intentos fallidos en paso 2")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor selecciona una opción válida del menú

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            
            # Re-enviar menú
            await self._rolados_step_2_material(phone_number, None)
            return
        
        # Guardar material y pasar al siguiente paso
        state = self.rolados_form_state[phone_number]
        state["data"]["material"] = user_response
        state["step"] = 3
        state["retry_count"] = 0
        
        logger.info(f"✅ Material guardado: {user_response}")
        
        # Paso 3: Calibre
        await self._rolados_step_3_calibre(phone_number, None)

    async def _rolados_step_3_calibre(self, phone_number: str, user_response: Optional[str]):
        """Paso 3: Seleccionar calibre"""
        
        if user_response is None:
            # Primera vez, mostrar menú
            message = """📝 *Paso 3 de 6:* Selecciona el calibre:"""
            
            sections = [
                {
                    "title": "Calibres Disponibles",
                    "rows": self.rolados_options["calibres"]
                }
            ]
            
            self.client.send_interactive_list(
                phone_number, 
                message,
                "Ver Calibres",
                sections
            )
            self.db.save_message(phone_number, message, "sent")
            return

        # Validar opción
        valid_ids = [opt["id"] for opt in self.rolados_options["calibres"]]
        
        if user_response.lower() not in valid_ids:
            state = self.rolados_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ ROLADOS {phone_number} - 3 intentos fallidos en paso 3")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor selecciona una opción válida

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            
            await self._rolados_step_3_calibre(phone_number, None)
            return
        
        # Guardar calibre
        state = self.rolados_form_state[phone_number]
        state["data"]["calibre"] = user_response
        state["step"] = 4
        state["retry_count"] = 0
        
        logger.info(f"✅ Calibre guardado: {user_response}")
        
        # Paso 4: Dimensiones
        await self._rolados_step_4_dimensiones(phone_number, None)

    async def _rolados_step_4_dimensiones(self, phone_number: str, user_response: Optional[str]):
        """Paso 4: Seleccionar dimensiones"""
        
        if user_response is None:
            # Primera vez, mostrar menú
            message = """📝 *Paso 4 de 6:* Selecciona las dimensiones:"""
            
            sections = [
                {
                    "title": "Dimensiones Disponibles",
                    "rows": self.rolados_options["dimensiones"]
                }
            ]
            
            self.client.send_interactive_list(
                phone_number, 
                message,
                "Ver Dimensiones",
                sections
            )
            self.db.save_message(phone_number, message, "sent")
            return

        # Validar opción
        valid_ids = [opt["id"] for opt in self.rolados_options["dimensiones"]]
        
        if user_response.lower() not in valid_ids:
            state = self.rolados_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ ROLADOS {phone_number} - 3 intentos fallidos en paso 4")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor selecciona una opción válida

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            
            await self._rolados_step_4_dimensiones(phone_number, None)
            return
        
        # Guardar dimensiones
        state = self.rolados_form_state[phone_number]
        state["data"]["dimensiones"] = user_response
        state["step"] = 5
        state["retry_count"] = 0
        
        logger.info(f"✅ Dimensiones guardadas: {user_response}")
        
        # Paso 5: Cantidad en kilos
        await self._rolados_step_5_cantidad(phone_number, None)

    async def _rolados_step_5_cantidad(self, phone_number: str, user_response: Optional[str]):
        """Paso 5: Seleccionar cantidad en kilos"""
        
        if user_response is None:
            # Primera vez, mostrar menú de cantidades
            message = """📝 *Paso 5 de 6:* ¿Cuántos kilos necesitas?"""
            
            # Generar opciones de cantidad dinámica
            cantidad_options = [
                {"id": "100_250", "title": "100 - 250 kg"},
                {"id": "250_500", "title": "250 - 500 kg"},
                {"id": "500_1000", "title": "500 - 1000 kg"},
                {"id": "1000_2000", "title": "1000 - 2000 kg"},
                {"id": "2000_plus", "title": "2000+ kg"},
                {"id": "especifica", "title": "Cantidad Específica", "description": "Escribe la cantidad exacta"},
            ]
            
            sections = [
                {
                    "title": "Selecciona Rango o Cantidad",
                    "rows": cantidad_options
                }
            ]
            
            self.client.send_interactive_list(
                phone_number, 
                message,
                "Ver Opciones",
                sections
            )
            self.db.save_message(phone_number, message, "sent")
            return

        # Validar que sea un número válido o una opción del menú
        valid_ranges = ["100_250", "250_500", "500_1000", "1000_2000", "2000_plus", "especifica"]
        
        # Si no es una opción de menú, validar que sea un número
        if user_response.lower() not in valid_ranges:
            if not user_response.replace(".", "").replace(",", "").isdigit():
                state = self.rolados_form_state[phone_number]
                state["retry_count"] += 1
                
                if state["retry_count"] >= 3:
                    logger.warning(f"⚠️ ROLADOS {phone_number} - 3 intentos fallidos en paso 5")
                    await self._send_vendor_contact(phone_number)
                    return
                
                message = f"""❌ Por favor ingresa una cantidad válida en kilos (solo números)

Ejemplo: 500 o 1500.5

*Intento {state["retry_count"]} de 3*"""
                
                self.client.send_text_message(phone_number, message)
                self.db.save_message(phone_number, message, "sent")
                return
        
        # Guardar cantidad
        state = self.rolados_form_state[phone_number]
        state["data"]["cantidad_kilos"] = user_response
        state["step"] = 6
        state["retry_count"] = 0
        
        logger.info(f"✅ Cantidad guardada: {user_response}")
        
        # Paso 6: Confirmación
        await self._rolados_step_6_confirmation(phone_number, None)

    async def _rolados_step_6_confirmation(self, phone_number: str, user_response: Optional[str]):
        """Paso 6: Confirmación y resumen"""
        
        state = self.rolados_form_state[phone_number]
        data = state["data"]
        
        if user_response is None:
            # Mostrar resumen y pedir confirmación
            resumen = f"""✅ *RESUMEN DE TU SOLICITUD*

👤 *Nombre:* {data.get('nombre', 'N/A')}
🏭 *Material:* {data.get('material', 'N/A')}
📏 *Calibre:* {data.get('calibre', 'N/A')}
📐 *Dimensiones:* {data.get('dimensiones', 'N/A')}
⚖️ *Cantidad:* {data.get('cantidad_kilos', 'N/A')} kg

¿Es correcto? Responde con:
✅ Sí, confirmar
❌ No, corregir"""
            
            self.client.send_text_message(phone_number, resumen)
            self.db.save_message(phone_number, resumen, "sent")
            return

        # Validar respuesta
        if user_response.lower() in ["sí", "si", "si,", "sí,", "✅", "ok", "confirmar", "confirmo"]:
            logger.info(f"✅ Formulario ROLADOS completado para {phone_number}")
            
            # Guardar lead en la base de datos
            self.db.save_lead_analysis(phone_number, {
                "lead_score": 9,
                "is_qualified_lead": True,
                "lead_type": "rolados_form",
                "summary_for_seller": f"Solicitud ROLADOS: {data.get('cantidad_kilos')} kg de {data.get('material')}",
                "project_info": data
            })
            
            # Mensaje de análisis (la IA analizando)
            nombre = data.get("nombre", "cliente")
            analysis_message = f"""Voy a analizar la información recopilada para verificar si estamos listos para una cotización.

Perfecto, {nombre}. Permíteme utilizar una herramienta para analizar tu solicitud."""
            
            self.client.send_text_message(phone_number, analysis_message)
            self.db.save_message(phone_number, analysis_message, "sent")
            
            # Simular pequeño delay de análisis
            await asyncio.sleep(2)
            
            # Analizar si podemos generar cotización o contactar vendedor
            can_quote = await self._analyze_rolados_quote_feasibility(data)
            
            if can_quote:
                # Si se puede hacer cotización
                await self._send_rolados_quote_ready(phone_number, data)
            else:
                # Si no se puede, conectar con vendedor
                await self._send_rolados_vendor_needed(phone_number, data)
            
            # Notificar al vendedor
            await self._notify_rolados_vendor(phone_number, data)
            
            # Limpiar estado del formulario
            del self.rolados_form_state[phone_number]
            
        elif user_response.lower() in ["no", "no,", "❌", "corregir", "corrijo"]:
            # Reiniciar el formulario
            message = """🔄 Entendido. Vamos a empezar de nuevo.

*¿Cuál es tu nombre?*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            
            # Reiniciar al paso 1
            self.rolados_form_state[phone_number] = {
                "step": 1,
                "data": {},
                "retry_count": 0
            }
        
        else:
            # Respuesta no válida
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ ROLADOS {phone_number} - 3 intentos fallidos en paso 6")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor responde con:
✅ Sí (para confirmar)
❌ No (para corregir)

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")

    async def _analyze_rolados_quote_feasibility(self, form_data: Dict) -> bool:
        """
        Analiza si se puede generar una cotización automática o si se necesita vendedor
        
        Retorna True si podemos cotizar, False si necesita contactar vendedor
        """
        material = form_data.get("material", "").lower()
        cantidad = form_data.get("cantidad_kilos", "")
        
        # Intentar convertir cantidad a número
        try:
            cantidad_num = float(str(cantidad).replace(",", "."))
        except:
            # Si no podemos convertir, necesita vendedor
            return False
        
        # Lógica simple: si es material estándar y cantidad normal, podemos cotizar
        materiales_standard = ["galvanizada", "pintro", "negra"]
        
        # Si es material estándar, cantidad entre 100-5000 kg → podemos cotizar
        if material in materiales_standard and 100 <= cantidad_num <= 5000:
            return True
        
        # En otros casos, contactar vendedor
        return False

    async def _send_rolados_quote_ready(self, phone_number: str, form_data: Dict):
        """Envía mensaje cuando sí podemos hacer cotización"""
        
        nombre = form_data.get("nombre", "")
        
        quote_message = f"""✅ ¡*Excelente, {nombre}!*

He analizado tu solicitud y **sí podemos procesarla directamente** para una cotización. 🎉

📊 *Detalles de tu solicitud:*
• Material: {form_data.get('material', 'N/A')}
• Calibre: {form_data.get('calibre', 'N/A')}
• Dimensiones: {form_data.get('dimensiones', 'N/A')}
• Cantidad: {form_data.get('cantidad_kilos', 'N/A')} kg

Tu cotización será procesada y te la enviaremos en las próximas 2 horas.

Si tienes alguna duda adicional, puedes contactar directamente a nuestro equipo:

📱 *{self.rolados_vendor['name']}*
☎️ WhatsApp: {self.rolados_vendor['phone']}
📧 Email: {self.rolados_vendor['email']}

*¡Gracias por confiar en ARCOSUM ROLADOS!* 🏭"""
        
        self.client.send_text_message(phone_number, quote_message)
        self.db.save_message(phone_number, quote_message, "sent")
        
        logger.info(f"✅ Cotización lista para procesar - {phone_number}")

    async def _send_rolados_vendor_needed(self, phone_number: str, form_data: Dict):
        """Envía mensaje cuando se necesita contactar al vendedor para detalles especiales"""
        
        nombre = form_data.get("nombre", "")
        
        vendor_message = f"""✅ ¡*Hola, {nombre}!*

He analizado tu solicitud y veo que tienes requerimientos especiales que necesitan atención personalizada. 📋

Para brindarte la **mejor cotización y opciones personalizadas**, te conectaré directamente con nuestro especialista en ROLADOS:

📱 *{self.rolados_vendor['name']}*
☎️ WhatsApp: {self.rolados_vendor['phone']}
📧 Email: {self.rolados_vendor['email']}

👉 **Él se comunicará contigo en los próximos 30 minutos** para:
✅ Confirmar especificaciones técnicas
✅ Ofrecer opciones personalizadas
✅ Discutir plazos y entregas
✅ Resolver cualquier pregunta

Tu solicitud:
• Material: {form_data.get('material', 'N/A')}
• Calibre: {form_data.get('calibre', 'N/A')}
• Dimensiones: {form_data.get('dimensiones', 'N/A')}
• Cantidad: {form_data.get('cantidad_kilos', 'N/A')} kg

*¡Gracias por tu paciencia y por confiar en ARCOSUM ROLADOS!* 🏭"""
        
        self.client.send_text_message(phone_number, vendor_message)
        self.db.save_message(phone_number, vendor_message, "sent")
        
        logger.info(f"📞 Vendedor contactará a {phone_number}")

    async def _notify_rolados_vendor(self, phone_number: str, form_data: Dict):
        """Notifica al vendedor de ROLADOS sobre la nueva solicitud"""
        
        notification = f"""🚨 *NUEVA SOLICITUD ROLADOS* 🚨

👤 *Cliente:* {form_data.get('nombre', 'N/A')}
📱 *Teléfono:* {phone_number}

📋 *Detalles de la solicitud:*
• Material: {form_data.get('material', 'N/A')}
• Calibre: {form_data.get('calibre', 'N/A')}
• Dimensiones: {form_data.get('dimensiones', 'N/A')}
• Cantidad: {form_data.get('cantidad_kilos', 'N/A')} kg

⏰ *ACCIÓN REQUERIDA:* Contactar al cliente en los próximos 30 minutos"""
        
        # Enviar directamente al teléfono del vendedor
        try:
            self.client.send_text_message(
                self.rolados_vendor['phone'],
                notification
            )
            logger.info(f"📧 Notificación ENVIADA al vendedor: {self.rolados_vendor['phone']}")
        except Exception as e:
            logger.error(f"Error enviando notificación al vendedor: {str(e)}")

    async def _send_vendor_contact(self, phone_number: str):
        """Envía contacto del vendedor cuando falla 3 veces"""
        
        message = f"""⚠️ Parece que hay un inconveniente con el formulario.

No te preocupes, te conectaré directamente con nuestro asesor especializado:

📱 *{self.rolados_vendor['name']}*
☎️ WhatsApp: {self.rolados_vendor['phone']}
📧 Email: {self.rolados_vendor['email']}

Puedes escribirle directamente y te atenderá en menos de 30 minutos. ¡Gracias por tu paciencia!"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")
        
        # Limpiar estado del formulario
        if phone_number in self.rolados_form_state:
            del self.rolados_form_state[phone_number]
        
        logger.info(f"📞 Contacto del vendedor enviado a {phone_number}")

    def _is_valid_name(self, name: str) -> bool:
        """Valida que el nombre sea válido (solo letras y espacios)"""
        # Permitir letras, espacios y acentos
        import re
        pattern = r"^[a-záéíóúñA-ZÁÉÍÓÚÑ\s]+$"
        return bool(re.match(pattern, name.strip())) and len(name.strip()) >= 2

    # ============= FIN GESTIÓN FORMULARIO ROLADOS =============
    
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

            # Preparar datos del lead
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

            # Enviar notificación
            await self.notifier.notify_qualified_lead(lead_data, notification_message)

            logger.info(f"Seller notified about qualified lead: {phone_number}")
            
            # NUEVO: Notificar también al cliente
            await self._notify_client_lead_received(phone_number, ai_analysis)

        except Exception as e:
            logger.error(f"Error notifying seller: {str(e)}")
    
    async def _notify_client_lead_received(self, phone_number: str, ai_analysis: Dict):
        """
        Notifica al cliente que su solicitud fue recibida y procesada
        
        Args:
            phone_number: Número del cliente
            ai_analysis: Análisis del lead con información de la solicitud
        """
        try:
            # Obtener datos relevantes del análisis
            lead_type = ai_analysis.get("lead_type", "")
            
            # Mensaje para el cliente
            client_message = f"""✅ *¡Hemos recibido tu solicitud!*

Gracias por contactarnos. Tu solicitud ha sido procesada correctamente. 🎉

📋 *Detalles de tu solicitud:*
• Tipo: {lead_type if lead_type else 'Consulta General'}
• Fecha: {datetime.now().strftime("%d/%m/%Y %H:%M")}

Un miembro de nuestro equipo analizará tu solicitud y se pondrá en contacto contigo en las próximas 2 horas.

Si tienes preguntas mientras tanto, no dudes en escribir. 😊

*Gracias por confiar en ARCOSUM* 🏭"""
            
            # Enviar mensaje al cliente
            self.client.send_text_message(phone_number, client_message)
            self.db.save_message(phone_number, client_message, "sent")
            
            logger.info(f"✅ Notificación de recibida enviada al cliente: {phone_number}")
            
        except Exception as e:
            logger.error(f"Error notifying client: {str(e)}")

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

Para agilizar tu solicitud de cotización, te guiaré a través de un formulario rápido.

¿Comenzamos? 📋"""
            
            self.client.send_text_message(to, response)
            self.db.save_message(to, response, "sent")
            
            # NUEVO: Iniciar formulario de ROLADOS
            asyncio.create_task(self._init_rolados_form(to))
            
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