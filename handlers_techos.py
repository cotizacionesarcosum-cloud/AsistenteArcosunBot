import logging
from typing import Optional
from datetime import datetime
import asyncio
import re

logger = logging.getLogger(__name__)

class TechosHandler:
    """Maneja formulario y lógica de ARCOSUM TECHOS"""

    def __init__(self, client, database, ai_assistant, notifier):
        self.client = client
        self.db = database
        self.ai = ai_assistant
        self.notifier = notifier
        
        self.techos_form_state = {}
        
        # Datos de vendedor TECHOS
        self.vendor_phone = "+52 222 423 4611"

    async def handle_techos_message(self, phone_number: str, message_text: str, message_id: str):
        """Maneja mensajes para TECHOS"""
        
        if phone_number in self.techos_form_state:
            await self._handle_techos_form_response(phone_number, message_text)
        else:
            await self._init_techos_form(phone_number)

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
        """Paso 2: Descripción del proyecto"""
        
        if len(user_response.strip()) < 10:
            state = self.techos_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ TECHOS {phone_number} - 3 intentos fallidos en paso 2")
                await self._send_techos_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor describe tu proyecto con más detalle (mínimo 10 caracteres)

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.techos_form_state[phone_number]
        state["data"]["descripcion"] = user_response.strip()
        state["step"] = 3
        state["retry_count"] = 0
        
        logger.info(f"✅ Descripción guardada")
        
        message = """📝 *Paso 3 de 4:* ¿En qué estado y municipio se ubicará la obra?

Ejemplo: Puebla, Puebla"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")

    async def _techos_step_3_location(self, phone_number: str, user_response: str):
        """Paso 3: Ubicación"""
        
        if len(user_response.strip()) < 5:
            state = self.techos_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ TECHOS {phone_number} - 3 intentos fallidos en paso 3")
                await self._send_techos_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor especifica la ubicación correctamente

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.techos_form_state[phone_number]
        state["data"]["ubicacion"] = user_response.strip()
        state["step"] = 4
        state["retry_count"] = 0
        
        await self._techos_step_4_confirmation(phone_number, None)

    async def _techos_step_4_confirmation(self, phone_number: str, user_response: Optional[str]):
        """Paso 4: Confirmación"""
        
        state = self.techos_form_state[phone_number]
        data = state["data"]
        
        if user_response is None:
            resumen = f"""✅ *RESUMEN DE TU SOLICITUD*

👤 *Nombre:* {data.get('nombre', 'N/A')}
📋 *Proyecto:* {data.get('descripcion', 'N/A')}
📍 *Ubicación:* {data.get('ubicacion', 'N/A')}

¿Es correcto? Responde:
✅ Sí, enviar
❌ No, cancelar"""
            
            self.client.send_text_message(phone_number, resumen)
            self.db.save_message(phone_number, resumen, "sent")
            return
        
        if user_response.lower() in ["sí", "si", "✅", "ok", "enviar"]:
            logger.info(f"✅ Formulario TECHOS completado para {phone_number}")
            
            self.db.save_lead_analysis(phone_number, {
                "lead_score": 8,
                "is_qualified_lead": True,
                "lead_type": "techos_form",
                "summary_for_seller": f"Solicitud TECHOS: {data.get('descripcion')}",
                "project_info": data
            })
            
            goodbye = f"""✅ *¡Solicitud Enviada Correctamente!*

Tu solicitud de ARCOSUM TECHOS ha sido registrada exitosamente y enviada al **Vendedor de ARCOSUM**.

🏗️ *Detalles registrados:*
• Nombre: {data.get('nombre')}
• Proyecto: {data.get('descripcion')}
• Ubicación: {data.get('ubicacion')}

📞 *El Vendedor de ARCOSUM se pondrá en contacto contigo en las próximas 2 horas.*

Si es urgente: {self.vendor_phone}

*¡Gracias por confiar en ARCOSUM!* 🏭"""
            
            self.client.send_text_message(phone_number, goodbye)
            self.db.save_message(phone_number, goodbye, "sent")
            
            await self._notify_techos_vendor(phone_number, data)
            
            del self.techos_form_state[phone_number]
        else:
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ TECHOS {phone_number} - Cancelado")
                await self._send_techos_vendor_contact(phone_number)
                return
            
            message = f"""❌ Responde con:
✅ Sí (enviar)
❌ No (cancelar)

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")

    async def _notify_techos_vendor(self, phone_number: str, form_data: dict):
        """Notifica al vendedor de TECHOS"""
        
        notification = f"""🚨 *NUEVA SOLICITUD TECHOS*

📱 *Cliente:* {phone_number}
👤 *Nombre:* {form_data.get('nombre', 'N/A')}

📋 *Proyecto:* {form_data.get('descripcion', 'N/A')}
📍 *Ubicación:* {form_data.get('ubicacion', 'N/A')}

⏰ *Contactar en los próximos 30 minutos*"""
        
        try:
            self.client.send_text_message(self.vendor_phone, notification)
            logger.info(f"📧 Notificación enviada al vendedor TECHOS")
        except Exception as e:
            logger.error(f"Error notificando: {str(e)}")

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
        
        logger.info(f"📞 Contacto vendedor enviado")

    def _is_valid_full_name(self, name: str) -> bool:
        """Valida nombre y apellido"""
        parts = name.strip().split()
        if len(parts) < 2:
            return False
        pattern = r"^[a-záéíóúñA-ZÁÉÍÓÚÑ\s]+$"
        return bool(re.match(pattern, name.strip()))