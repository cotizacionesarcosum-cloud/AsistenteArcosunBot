import logging
from typing import Optional, Dict
from datetime import datetime
import asyncio
import re

logger = logging.getLogger(__name__)

class TechosHandler:
    """Maneja formulario y lógica de ARCOSUM TECHOS con IA asistida"""

    def __init__(self, client, database, ai_assistant, notifier, message_handler=None):
        self.client = client
        self.db = database
        self.ai = ai_assistant
        self.notifier = notifier
        self.message_handler = message_handler  # Referencia al orquestador principal
        
        self.techos_form_state = {}
        
        # Datos de vendedor TECHOS
        self.vendor_phone = "+52 222 423 4611"

    def _detect_division_change(self, message: str) -> str:
        """Detecta si el usuario quiere cambiar a otra división.
        
        Retorna:
        - 'rolados': si menciona ROLADOS
        - 'suministros': si menciona SUMINISTROS
        - 'otros': si menciona OTROS
        - None: si no quiere cambiar
        """
        
        message_lower = message.lower()
        
        # Detección de ROLADOS
        if any(word in message_lower for word in ["rolados", "rolado", "lamina", "laminado", "calibre"]):
            return "rolados"
        
        # Detección de SUMINISTROS
        if any(word in message_lower for word in ["suministros", "suministro", "materiales", "otros materiales", "accesorios"]):
            return "suministros"
        
        # Detección de OTROS
        if any(word in message_lower for word in ["otros", "otra cosa", "otra division", "consulta"]):
            return "otros"
        
        return None

    async def handle_techos_message(self, phone_number: str, message_text: str, message_id: str):
        """Maneja mensajes para TECHOS"""
        
        # Detectar cambio de división en CUALQUIER momento
        division_change = self._detect_division_change(message_text)
        if division_change:
            await self._redirect_division(phone_number, division_change)
            return
        
        if phone_number in self.techos_form_state:
            await self._handle_techos_form_response(phone_number, message_text)
        else:
            await self._init_techos_form(phone_number)

    async def _redirect_division(self, phone_number: str, division: str):
        """Redirige el usuario a otra división"""
        division_names = {
            "rolados": "🔧 ARCOSUM ROLADOS",
            "suministros": "📦 ARCOSUM SUMINISTROS",
            "otros": "❓ ARCOSUM OTROS"
        }
        
        message = f"""Perfecto, te conecto con {division_names.get(division)}.

Por favor escribe "hola" para comenzar de nuevo."""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")
        
        # Limpiar estado del formulario si existe
        if phone_number in self.techos_form_state:
            del self.techos_form_state[phone_number]
        
        logger.info(f"🔄 Usuario redirigido a {division}")

    async def _init_techos_form(self, phone_number: str):
        """Inicia el formulario de TECHOS"""
        
        self.techos_form_state[phone_number] = {
            "step": 1,
            "data": {},
            "retry_count": 0
        }
        
        logger.info(f"🆕 Formulario TECHOS iniciado para {phone_number}")
        
        message = """🏗️ *FORMULARIO TECHOS* 📋

Te ayudaré a procesar tu solicitud de Arcotechos y estructuras metálicas.

📝 *Paso 1 de 4:* ¿Cuál es tu nombre completo?

(Formato: Nombre Apellido)"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")

    async def _handle_techos_form_response(self, phone_number: str, message_text: str):
        """Maneja respuestas del formulario de TECHOS"""
        
        state = self.techos_form_state[phone_number]
        current_step = state["step"]
        
        logger.info(f"📋 TECHOS Form - Step: {current_step}, Message: {message_text}")
        
        try:
            if current_step == 1:
                await self._techos_step_1_name(phone_number, message_text)
            elif current_step == 2:
                await self._techos_step_2_description(phone_number, message_text)
            elif current_step == 3:
                await self._techos_step_3_location(phone_number, message_text)
            elif current_step == 4:
                await self._techos_step_4_confirmation(phone_number, message_text)
        except Exception as e:
            logger.error(f"Error en formulario TECHOS: {str(e)}")
            await self._send_techos_vendor_contact(phone_number)

    async def _techos_step_1_name(self, phone_number: str, user_response: str):
        """Paso 1: Nombre y Apellido"""
        
        if not self._is_valid_full_name(user_response):
            state = self.techos_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ TECHOS {phone_number} - 3 intentos fallidos en paso 1")
                await self._send_techos_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor ingresa nombre y apellido válidos

Formato: Juan Pérez

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.techos_form_state[phone_number]
        state["data"]["nombre"] = user_response.strip()
        state["step"] = 2
        state["retry_count"] = 0
        
        logger.info(f"✅ Nombre guardado: {user_response}")
        
        nombre_corto = user_response.split()[0]
        message = f"""✅ Gracias, {nombre_corto}!

📝 *Paso 2 de 4:* Describe tu proyecto (Arcotecho, estructura, etc.)

Ejemplo: "Necesito un arcotecho para mi nave industrial de 50x30 metros"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")

    async def _techos_step_2_description(self, phone_number: str, user_response: str):
        """Paso 2: Descripción del proyecto - IA asistida"""
        
        # Validación inicial rápida
        if len(user_response.strip()) < 10:
            state = self.techos_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ TECHOS {phone_number} - 3 intentos fallidos en paso 2")
                await self._send_techos_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor describe tu proyecto con más detalle (mínimo 10 caracteres)

Ejemplo: "Arcotecho para nave de 40x20 con ventilación"

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        # Usar IA para validar y mejorar la descripción
        ia_prompt = f"""Analiza si esta descripción de proyecto es válida y coherente:

Descripción: "{user_response}"

Responde SOLO con: "valido" si es una descripción razonable, o "invalido" si no lo es."""
        
        try:
            ia_response = await self.ai.generate_response(ia_prompt)
            is_valid = "valido" in ia_response.lower()
            
            if not is_valid:
                raise ValueError("IA marcó como inválido")
            
            logger.info(f"✅ Descripción validada por IA")
        
        except:
            # Fallback: confiar en validación por longitud si IA falla
            logger.info(f"⚠️ IA no pudo validar, usando validación por longitud")
        
        state = self.techos_form_state[phone_number]
        state["data"]["descripcion"] = user_response.strip()
        state["step"] = 3
        state["retry_count"] = 0
        
        logger.info(f"✅ Descripción guardada")
        
        message = """📝 *Paso 3 de 4:* ¿En qué estado y municipio se ubicará la obra?

Ejemplo: Puebla, Puebla o Tlaxcala, Tenancingo"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")

    async def _techos_step_3_location(self, phone_number: str, user_response: str):
        """Paso 3: Ubicación - IA asistida"""
        
        # Validación inicial rápida
        if len(user_response.strip()) < 5:
            state = self.techos_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ TECHOS {phone_number} - 3 intentos fallidos en paso 3")
                await self._send_techos_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor especifica la ubicación correctamente

Formato: Ciudad, Estado
Ejemplo: Puebla, Puebla

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        # Usar IA para validar ubicación
        ia_prompt = f"""Analiza si esta es una ubicación válida en México:

Ubicación: "{user_response}"

Responde SOLO con: "valido" si es una ubicación válida, o "invalido" si no."""
        
        try:
            ia_response = await self.ai.generate_response(ia_prompt)
            is_valid = "valido" in ia_response.lower()
            
            if not is_valid:
                raise ValueError("IA marcó como inválido")
            
            logger.info(f"✅ Ubicación validada por IA")
        
        except:
            # Fallback: confiar en validación por longitud si IA falla
            logger.info(f"⚠️ IA no pudo validar ubicación, usando validación por longitud")
        
        state = self.techos_form_state[phone_number]
        state["data"]["ubicacion"] = user_response.strip()
        state["step"] = 4
        state["retry_count"] = 0
        
        logger.info(f"✅ Ubicación guardada: {user_response.strip()}")
        
        await self._techos_step_4_confirmation(phone_number, None)

    async def _techos_step_4_confirmation(self, phone_number: str, user_response: Optional[str]):
        """Paso 4: Confirmación"""
        
        state = self.techos_form_state[phone_number]
        data = state["data"]
        
        if user_response is None:
            # Mostrar resumen
            resumen = f"""✅ *RESUMEN DE TU SOLICITUD*

👤 *Nombre:* {data.get('nombre', 'N/A')}
📋 *Proyecto:* {data.get('descripcion', 'N/A')}
📍 *Ubicación:* {data.get('ubicacion', 'N/A')}

¿Es correcto?

Responde: sí o no"""
            
            self.client.send_text_message(phone_number, resumen)
            self.db.save_message(phone_number, resumen, "sent")
            return
        
        # Usar IA para detectar confirmación
        ia_prompt = f"""¿El usuario confirma o cancela?

Respuesta: "{user_response}"

Responde SOLO con: "confirma", "cancela" o "invalido"."""
        
        try:
            ia_response = await self.ai.generate_response(ia_prompt)
            user_intent = ia_response.strip().lower()
        except:
            user_intent = "invalido"
        
        # Fallback: palabras clave simples
        if user_intent == "invalido":
            if any(w in user_response.lower() for w in ["sí", "si", "ok", "yes", "yep", "vale", "perfecto"]):
                user_intent = "confirma"
            elif any(w in user_response.lower() for w in ["no", "cancel", "nope", "negativo"]):
                user_intent = "cancela"
        
        if user_intent == "confirma":
            logger.info(f"✅ Formulario TECHOS completado para {phone_number}")
            
            # Guardar lead
            self.db.save_lead_analysis(phone_number, {
                "lead_score": 8,
                "is_qualified_lead": True,
                "lead_type": "techos_form",
                "summary_for_seller": f"Solicitud TECHOS: {data.get('descripcion')}",
                "project_info": data
            })
            
            confirmation = f"""✅ *¡Solicitud Enviada Correctamente!*

Tu solicitud de ARCOSUM TECHOS ha sido registrada exitosamente y enviada al **Vendedor de ARCOSUM**.

🏗️ *Detalles registrados:*
• Nombre: {data.get('nombre')}
• Proyecto: {data.get('descripcion')}
• Ubicación: {data.get('ubicacion')}

📞 *El Vendedor de ARCOSUM se pondrá en contacto contigo en las próximas 2 horas.*

Si es urgente: {self.vendor_phone}

*¡Gracias por confiar en ARCOSUM!* 🏭"""
            
            self.client.send_text_message(phone_number, confirmation)
            self.db.save_message(phone_number, confirmation, "sent")
            
            await self._notify_techos_vendor(phone_number, data)
            
            # Mostrar menú principal
            await self._show_main_menu(phone_number)
            
            del self.techos_form_state[phone_number]
        
        elif user_intent == "cancela":
            message = """🔄 Entendido. Cancelando solicitud.

Si cambias de idea, escribe cualquier mensaje para empezar de nuevo."""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            
            del self.techos_form_state[phone_number]
        
        else:
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ TECHOS {phone_number} - Cancelado")
                await self._send_techos_vendor_contact(phone_number)
                return
            
            message = f"""❓ No entendí. Por favor responde:
- Sí (para confirmar)
- No (para cancelar)

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")

    async def _show_main_menu(self, phone_number: str):
        """Muestra el menú principal a través del MessageHandler"""
        
        await asyncio.sleep(1)  # Pequeña pausa para que se vea el flujo
        
        # Limpiar estado del formulario TECHOS
        if phone_number in self.techos_form_state:
            del self.techos_form_state[phone_number]
        
        logger.info(f"📋 Redirigiendo a menú principal para {phone_number}")
        
        # Llamar al MessageHandler para mostrar el menú principal
        if self.message_handler:
            await self.message_handler.send_main_menu(phone_number)
            logger.info(f"✅ Menú principal enviado por MessageHandler para {phone_number}")
        else:
            # Fallback si no hay referencia al message_handler
            logger.warning(f"⚠️ No hay referencia a MessageHandler para {phone_number}")

    async def _notify_techos_vendor(self, phone_number: str, form_data: Dict):
        """Notifica al vendedor de TECHOS usando plantilla o mensaje directo"""
        
        try:
            # Parámetros para plantilla
            template_params = [
                form_data.get('nombre', 'N/A'),  # {{1}} Nombre
                phone_number,  # {{2}} Cliente
                form_data.get('descripcion', 'N/A'),  # {{3}} Descripción
                form_data.get('ubicacion', 'N/A'),  # {{4}} Ubicación
            ]
            
            self.client.send_template_message(
                to=self.vendor_phone,
                template_name="notificacion_lead_calificado",
                language_code="es_MX",
                parameters=template_params
            )
            logger.info(f"📧 Notificación enviada al vendedor TECHOS (plantilla)")
            return
        except Exception as e:
            logger.error(f"❌ Error enviando plantilla: {str(e)}")
        
        # Si falla plantilla: Mensaje de texto normal
        notification = f"""🚨 *NUEVA SOLICITUD TECHOS*

📱 *Cliente:* {phone_number}
👤 *Nombre:* {form_data.get('nombre', 'N/A')}

📋 *Proyecto:* {form_data.get('descripcion', 'N/A')}
📍 *Ubicación:* {form_data.get('ubicacion', 'N/A')}

⏰ *Contactar en los próximos 30 minutos*"""
        
        try:
            self.client.send_text_message(self.vendor_phone, notification)
            logger.info(f"📧 Notificación (texto) enviada al vendedor TECHOS")
        except Exception as e:
            logger.error(f"❌ Error notificando al vendedor: {str(e)}")
            logger.error(f"💡 Solución: Crea una plantilla aprobada en Meta/WhatsApp")

    async def _send_techos_vendor_contact(self, phone_number: str):
        """Envía contacto del vendedor cuando hay problemas"""
        
        message = f"""⚠️ Parece que hay un inconveniente con el formulario.

Te conectaremos directamente con el **Vendedor de ARCOSUM**:

☎️ WhatsApp: {self.vendor_phone}

Te atenderá en menos de 30 minutos. ¡Gracias por tu paciencia!"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")
        
        if phone_number in self.techos_form_state:
            del self.techos_form_state[phone_number]
        
        logger.info(f"📞 Contacto vendedor TECHOS enviado")

    def _is_valid_full_name(self, name: str) -> bool:
        """Valida nombre y apellido"""
        parts = name.strip().split()
        if len(parts) < 2:
            return False
        pattern = r"^[a-záéíóúñA-ZÁÉÍÓÚÑ\s]+$"
        return bool(re.match(pattern, name.strip()))