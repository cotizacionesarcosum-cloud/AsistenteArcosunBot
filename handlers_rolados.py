import logging
from typing import Optional, Dict
from datetime import datetime
import asyncio
import re

logger = logging.getLogger(__name__)

class RoladosHandler:
    """Maneja formulario y lógica de ARCOSUM ROLADOS"""

    def __init__(self, client, database, ai_assistant, notifier):
        self.client = client
        self.db = database
        self.ai = ai_assistant
        self.notifier = notifier
        
        self.rolados_form_state = {}  # {phone_number: {"step": int, "data": {...}, "retry_count": int}}
        
        # Datos de vendedor ROLADOS (mismo para ROLADOS, SUMINISTROS y OTROS)
        self.vendor = {
            "phone": "+52 222 114 8841",
            "email": "ventas-rolados@arcosum.com"
        }
        
        # Opciones de láminas
        self.tipos_lamina = [
            {"id": "zintro", "title": "Lámina Zintro", "description": "Zinc y aluminio"},
            {"id": "alum", "title": "Lámina Aluminio", "description": "100% Aluminio"},
            {"id": "pintro", "title": "Lámina Pintro", "description": "Acabado pintado"},
        ]
        
        # Calibres disponibles (18 a 24)
        self.calibres = [
            {"id": "cal_18", "title": "Calibre 18", "description": "2.4mm"},
            {"id": "cal_20", "title": "Calibre 20", "description": "1.6mm"},
            {"id": "cal_22", "title": "Calibre 22", "description": "1.2mm"},
            {"id": "cal_24", "title": "Calibre 24", "description": "0.8mm"},
        ]

    async def handle_rolados_message(self, phone_number: str, message_text: str, message_id: str):
        """Maneja mensajes para ROLADOS"""
        
        if phone_number in self.rolados_form_state:
            await self._handle_rolados_form_response(phone_number, message_text)
        else:
            await self._init_rolados_form(phone_number)

    async def _init_rolados_form(self, phone_number: str):
        """Inicia el formulario de ROLADOS"""
        
        self.rolados_form_state[phone_number] = {
            "step": 1,
            "data": {},
            "retry_count": 0
        }
        
        logger.info(f"🆕 Formulario ROLADOS iniciado para {phone_number}")
        
        message = """🔧 *FORMULARIO ROLADOS* 📋

Te ayudaré a procesar tu solicitud de laminados y suministros.

📝 *Paso 1 de 5:* ¿Qué servicio necesitas?

Responde:
🏗️ rolado - Venta de láminas y perfiles
🏢 suministros - Otros suministros industriales"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")

    async def _handle_rolados_form_response(self, phone_number: str, message_text: str):
        """Maneja respuestas del formulario"""
        
        state = self.rolados_form_state[phone_number]
        current_step = state["step"]
        
        logger.info(f"📋 ROLADOS Form - Step: {current_step}, Message: {message_text}")
        
        try:
            if current_step == 1:
                await self._step_1_servicio(phone_number, message_text)
            elif current_step == 2:
                await self._step_2_ubicacion(phone_number, message_text)
            elif current_step == 3:
                await self._step_3_cantidad(phone_number, message_text)
            elif current_step == 4:
                await self._step_4_lamina_calibre(phone_number, message_text)
            elif current_step == 5:
                await self._step_5_confirmation(phone_number, message_text)
        except Exception as e:
            logger.error(f"Error en formulario ROLADOS: {str(e)}")
            await self._send_vendor_contact(phone_number)

    async def _step_1_servicio(self, phone_number: str, user_response: str):
        """Paso 1: ¿Qué servicio necesita?"""
        
        user_response = user_response.lower().strip()
        
        if user_response not in ["rolado", "suministros"]:
            state = self.rolados_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ ROLADOS {phone_number} - 3 intentos fallidos en paso 1")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor responde:
🏗️ rolado
🏢 suministros

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.rolados_form_state[phone_number]
        state["data"]["servicio"] = user_response
        state["step"] = 2
        state["retry_count"] = 0
        
        logger.info(f"✅ Servicio: {user_response}")
        
        # Paso 2: Ubicación
        message = """📝 *Paso 2 de 5:* ¿En qué estado y municipio?

Ejemplo: Puebla, Puebla"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")

    async def _step_2_ubicacion(self, phone_number: str, user_response: str):
        """Paso 2: Ubicación"""
        
        if len(user_response.strip()) < 5:
            state = self.rolados_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ ROLADOS {phone_number} - 3 intentos fallidos en paso 2")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❌ Especifica estado y municipio correctamente

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.rolados_form_state[phone_number]
        state["data"]["ubicacion"] = user_response.strip()
        state["step"] = 3
        state["retry_count"] = 0
        
        # Paso 3: Cantidad en kilos o toneladas
        message = """📝 *Paso 3 de 5:* ¿Cuántos kilos o toneladas necesitas?

Ejemplo: 500 kg o 2 toneladas

(Si no sabe, proporcione ancho y largo en metros)"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")

    async def _step_3_cantidad(self, phone_number: str, user_response: str):
        """Paso 3: Cantidad"""
        
        user_response = user_response.strip()
        
        # Validar que sea cantidad válida (números, kg, toneladas, o dimensiones)
        if not self._is_valid_cantidad(user_response):
            state = self.rolados_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ ROLADOS {phone_number} - 3 intentos fallidos en paso 3")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❌ Especifica una cantidad válida (kilos, toneladas, o dimensiones)

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.rolados_form_state[phone_number]
        state["data"]["cantidad"] = user_response
        state["step"] = 4
        state["retry_count"] = 0
        
        # Paso 4: Tipo de lámina y calibre (si es ROLADO)
        servicio = state["data"].get("servicio", "")
        
        if servicio == "rolado":
            message = """📝 *Paso 4 de 5:* Tipo de lámina:

Responde:
🔹 zintro - Lámina Zintro
🔹 alum - Lámina Aluminio
🔹 pintro - Lámina Pintro"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
        else:
            # Si es suministros, saltar a confirmación
            state["step"] = 5
            await self._step_5_confirmation(phone_number, None)

    async def _step_4_lamina_calibre(self, phone_number: str, user_response: str):
        """Paso 4: Tipo de lámina y calibre"""
        
        user_response = user_response.lower().strip()
        
        # Validar tipo de lámina
        valid_tipos = [opt["id"] for opt in self.tipos_lamina]
        
        if user_response not in valid_tipos:
            state = self.rolados_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ ROLADOS {phone_number} - 3 intentos fallidos en paso 4")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❌ Selecciona un tipo válido: zintro, alum o pintro

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.rolados_form_state[phone_number]
        state["data"]["lamina"] = user_response
        
        # Preguntar calibre
        message = """¿Qué calibre necesitas? (solo disponemos del 18 al 24)

Responde:
📏 cal_18 - Calibre 18 (2.4mm)
📏 cal_20 - Calibre 20 (1.6mm)
📏 cal_22 - Calibre 22 (1.2mm)
📏 cal_24 - Calibre 24 (0.8mm)"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")
        
        state["step"] = 4.5  # Paso intermedio para calibre
        state["retry_count"] = 0

    async def _step_5_confirmation(self, phone_number: str, user_response: Optional[str]):
        """Paso 5: Confirmación"""
        
        state = self.rolados_form_state[phone_number]
        
        # Si es el primer paso, mostrar formulario para calibre
        if user_response is None and state["step"] == 4.5:
            # Esperar respuesta de calibre
            user_response_calibre = await self._get_user_response(phone_number)
            
            valid_calibres = [opt["id"] for opt in self.calibres]
            if user_response_calibre.lower() not in valid_calibres:
                state["retry_count"] += 1
                if state["retry_count"] >= 3:
                    await self._send_vendor_contact(phone_number)
                    return
                
                message = f"""❌ Calibre no válido

*Intento {state["retry_count"]} de 3*"""
                self.client.send_text_message(phone_number, message)
                self.db.save_message(phone_number, message, "sent")
                return
            
            state["data"]["calibre"] = user_response_calibre.lower()
            state["step"] = 5
            state["retry_count"] = 0
        
        data = state["data"]
        
        if user_response is None:
            # Mostrar resumen
            resumen = f"""✅ *RESUMEN DE TU SOLICITUD*

📦 *Servicio:* {data.get('servicio', 'N/A').upper()}
📍 *Ubicación:* {data.get('ubicacion', 'N/A')}
⚖️ *Cantidad:* {data.get('cantidad', 'N/A')}
📋 *Lámina:* {data.get('lamina', 'N/A')}
📏 *Calibre:* {data.get('calibre', 'N/A')}

¿Es correcto?
✅ Sí, enviar
❌ No, cancelar"""
            
            self.client.send_text_message(phone_number, resumen)
            self.db.save_message(phone_number, resumen, "sent")
            return
        
        if user_response.lower() in ["sí", "si", "✅", "ok", "enviar"]:
            logger.info(f"✅ Formulario ROLADOS completado para {phone_number}")
            
            # Guardar lead
            self.db.save_lead_analysis(phone_number, {
                "lead_score": 8,
                "is_qualified_lead": True,
                "lead_type": "rolados_form",
                "summary_for_seller": f"Solicitud {data.get('servicio').upper()}: {data.get('cantidad')}",
                "project_info": data
            })
            
            # Mensaje de confirmación
            confirmation = f"""✅ *¡Solicitud Enviada!*

Tu solicitud de ARCOSUM ROLADOS ha sido registrada exitosamente.

Un asesor se pondrá en contacto contigo en las próximas 2 horas.

📱 Si es urgente: {self.vendor['phone']}

*Gracias por confiar en ARCOSUM* 🏭"""
            
            self.client.send_text_message(phone_number, confirmation)
            self.db.save_message(phone_number, confirmation, "sent")
            
            # Notificar vendedor
            await self._notify_vendor(phone_number, data)
            
            # Limpiar
            del self.rolados_form_state[phone_number]
        else:
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ ROLADOS {phone_number} - Cancelado por usuario")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❌ Responde con:
✅ Sí (enviar)
❌ No (cancelar)

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")

    async def _notify_vendor(self, phone_number: str, form_data: Dict):
        """Notifica al vendedor"""
        
        notification = f"""🚨 *NUEVA SOLICITUD ROLADOS*

📱 *Teléfono:* {phone_number}

📦 *Servicio:* {form_data.get('servicio', 'N/A').upper()}
📍 *Ubicación:* {form_data.get('ubicacion', 'N/A')}
⚖️ *Cantidad:* {form_data.get('cantidad', 'N/A')}
📋 *Lámina:* {form_data.get('lamina', 'N/A')}
📏 *Calibre:* {form_data.get('calibre', 'N/A')}

⏰ *Contactar en los próximos 30 minutos*"""
        
        try:
            self.client.send_text_message(self.vendor['phone'], notification)
            logger.info(f"📧 Notificación enviada al vendedor")
        except Exception as e:
            logger.error(f"Error notificando: {str(e)}")

    async def _send_vendor_contact(self, phone_number: str):
        """Envía contacto del vendedor"""
        
        message = f"""⚠️ Parece que hay un inconveniente con el formulario.

Te conectaremos directamente con nuestro especialista:

📱 *{self.vendor['name']}*
☎️ WhatsApp: {self.vendor['phone']}
📧 Email: {self.vendor['email']}

Te atenderá en menos de 30 minutos. ¡Gracias por tu paciencia!"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")
        
        if phone_number in self.rolados_form_state:
            del self.rolados_form_state[phone_number]
        
        logger.info(f"📞 Contacto vendedor enviado a {phone_number}")

    async def _get_user_response(self, phone_number: str) -> str:
        """Obtiene respuesta del usuario (temporal, en futuro usar webhook)"""
        # Por ahora retorna vacío, será capturado en el handler principal
        return ""

    def _is_valid_cantidad(self, cantidad: str) -> bool:
        """Valida cantidad en kilos, toneladas o dimensiones"""
        cantidad_lower = cantidad.lower()
        # Buscar números seguidos de kg, t, toneladas, metros, x
        pattern = r"(\d+[\.,]?\d*)\s*(kg|tonelada|ton|t|m|x)"
        return bool(re.search(pattern, cantidad_lower))