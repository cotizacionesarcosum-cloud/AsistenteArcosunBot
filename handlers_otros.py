import logging

logger = logging.getLogger(__name__)

class OtrosHandler:
    """Maneja consultas de OTROS / Consultas Generales"""

    def __init__(self, client, database, ai_assistant, notifier):
        self.client = client
        self.db = database
        self.ai = ai_assistant
        self.notifier = notifier
        
        self.otros_form_state = {}
        
        # Mismo vendedor para OTROS
        self.vendor = {
            "name": "Juan Carlos",
            "phone": "+52 222 114 8841",
            "email": "ventas-rolados@arcosum.com"
        }

    async def handle_otros_message(self, phone_number: str, message_text: str, message_id: str):
        """Maneja mensajes para OTROS"""
        
        if phone_number in self.otros_form_state:
            await self._handle_otros_form_response(phone_number, message_text)
        else:
            await self._init_otros_form(phone_number)

    async def _init_otros_form(self, phone_number: str):
        """Inicia formulario de OTROS"""
        
        self.otros_form_state[phone_number] = {
            "step": 1,
            "data": {},
            "retry_count": 0
        }
        
        logger.info(f"🆕 Formulario OTROS iniciado para {phone_number}")
        
        message = """❓ *CONSULTA GENERAL* 📋

Cuéntame tu consulta y nos pondremos en contacto.

📝 *Paso 1 de 2:* ¿Cuál es tu nombre completo?

(Formato: Nombre Apellido)"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")

    async def _handle_otros_form_response(self, phone_number: str, message_text: str):
        """Maneja respuestas del formulario OTROS"""
        
        state = self.otros_form_state[phone_number]
        current_step = state["step"]
        
        logger.info(f"📋 OTROS Form - Step: {current_step}, Message: {message_text}")
        
        try:
            if current_step == 1:
                await self._step_1_nombre(phone_number, message_text)
            elif current_step == 2:
                await self._step_2_asunto(phone_number, message_text)
        except Exception as e:
            logger.error(f"Error en formulario OTROS: {str(e)}")
            await self._send_vendor_contact(phone_number)

    async def _step_1_nombre(self, phone_number: str, user_response: str):
        """Paso 1: Nombre y Apellido"""
        
        if not self._is_valid_full_name(user_response):
            state = self.otros_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ OTROS {phone_number} - 3 intentos fallidos")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor ingresa nombre y apellido

Formato: Juan Pérez

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.otros_form_state[phone_number]
        state["data"]["nombre"] = user_response.strip()
        state["step"] = 2
        state["retry_count"] = 0
        
        nombre_corto = user_response.split()[0]
        
        message = f"""✅ Gracias, {nombre_corto}!

📝 *Paso 2 de 2:* ¿Cuál es tu asunto o consulta?

Cuéntanos qué necesitas"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")

    async def _step_2_asunto(self, phone_number: str, user_response: str):
        """Paso 2: Asunto/Consulta"""
        
        if len(user_response.strip()) < 10:
            state = self.otros_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ OTROS {phone_number} - 3 intentos fallidos en asunto")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor describe tu consulta con más detalle (mínimo 10 caracteres)

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.otros_form_state[phone_number]
        state["data"]["asunto"] = user_response.strip()
        
        data = state["data"]
        
        # Mostrar confirmación
        resumen = f"""✅ *RESUMEN*

👤 *Nombre:* {data.get('nombre', 'N/A')}
📋 *Asunto:* {data.get('asunto', 'N/A')[:50]}...

¿Enviar consulta?
✅ Sí
❌ No"""
        
        self.client.send_text_message(phone_number, resumen)
        self.db.save_message(phone_number, resumen, "sent")
        
        # Esperar confirmación final
        state["step"] = 3

    async def handle_otros_confirmation(self, phone_number: str, user_response: str):
        """Maneja confirmación final"""
        
        if phone_number not in self.otros_form_state:
            return
        
        state = self.otros_form_state[phone_number]
        
        if user_response.lower() in ["sí", "si", "✅", "ok"]:
            logger.info(f"✅ Formulario OTROS completado para {phone_number}")
            
            data = state["data"]
            
            # Guardar lead
            self.db.save_lead_analysis(phone_number, {
                "lead_score": 7,
                "is_qualified_lead": True,
                "lead_type": "otros_form",
                "summary_for_seller": f"Consulta General: {data.get('asunto')}",
                "project_info": data
            })
            
            # Confirmación
            confirmation = f"""✅ *¡Consulta Registrada!*

Tu mensaje ha sido registrado exitosamente.

Un asesor se pondrá en contacto contigo en las próximas 2 horas.

📱 Si es urgente: {self.vendor['phone']}

*Gracias por confiar en ARCOSUM* 🏭"""
            
            self.client.send_text_message(phone_number, confirmation)
            self.db.save_message(phone_number, confirmation, "sent")
            
            # Notificar vendedor
            await self._notify_vendor(phone_number, data)
            
            # Limpiar
            del self.otros_form_state[phone_number]
        else:
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❌ Responde con sí o no"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")

    async def _notify_vendor(self, phone_number: str, form_data: dict):
        """Notifica al vendedor"""
        
        notification = f"""🚨 *NUEVA CONSULTA GENERAL*

👤 *Cliente:* {form_data.get('nombre', 'N/A')}
📱 *Teléfono:* {phone_number}

📋 *Asunto:* {form_data.get('asunto', 'N/A')}

⏰ *Contactar en los próximos 30 minutos*"""
        
        try:
            self.client.send_text_message(self.vendor['phone'], notification)
            logger.info(f"📧 Notificación enviada al vendedor")
        except Exception as e:
            logger.error(f"Error notificando: {str(e)}")

    async def _send_vendor_contact(self, phone_number: str):
        """Envía contacto del vendedor"""
        
        message = f"""⚠️ Parece que hay un inconveniente.

Te conectaremos directamente con nuestro especialista:

📱 *{self.vendor['name']}*
☎️ WhatsApp: {self.vendor['phone']}
📧 Email: {self.vendor['email']}

Te atenderá en menos de 30 minutos. ¡Gracias!"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")
        
        if phone_number in self.otros_form_state:
            del self.otros_form_state[phone_number]
        
        logger.info(f"📞 Contacto vendedor enviado")

    def _is_valid_full_name(self, name: str) -> bool:
        """Valida nombre y apellido"""
        import re
        parts = name.strip().split()
        if len(parts) < 2:
            return False
        pattern = r"^[a-záéíóúñA-ZÁÉÍÓÚÑ\s]+$"
        return bool(re.match(pattern, name.strip()))