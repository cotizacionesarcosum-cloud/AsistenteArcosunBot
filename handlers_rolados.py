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
        
        self.rolados_form_state = {}
        
        # Datos de vendedor ROLADOS
        self.vendor_phone = "+52 222 114 8841"
        
        # Opciones de láminas
        self.tipos_lamina = [
            {"id": "zintro_alum", "title": "Zintro Alum"},
            {"id": "pintro", "title": "Pintro"},
        ]
        
        # Calibres disponibles
        self.calibres = [
            {"id": "cal_18", "title": "Calibre 18", "desc": "2.4mm"},
            {"id": "cal_20", "title": "Calibre 20", "desc": "1.6mm"},
            {"id": "cal_22", "title": "Calibre 22", "desc": "1.2mm"},
            {"id": "cal_24", "title": "Calibre 24", "desc": "0.8mm"},
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

Te ayudaré a procesar tu solicitud de laminados.

📝 *Paso 1 de 5:* ¿Qué servicio necesitas?

Responde con:
1️⃣ rolado - Venta de láminas
2️⃣ suministros - Otros suministros

(Escribe: rolado o suministros)"""
        
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
                await self._step_4_lamina(phone_number, message_text)
            elif current_step == 5:
                await self._step_5_calibre(phone_number, message_text)
            elif current_step == 6:
                await self._step_6_confirmation(phone_number, message_text)
        except Exception as e:
            logger.error(f"Error en formulario ROLADOS: {str(e)}")
            await self._send_vendor_contact(phone_number)

    async def _step_1_servicio(self, phone_number: str, user_response: str):
        """Paso 1: ¿Qué servicio necesita?"""
        
        user_response = user_response.lower().strip()
        
        if user_response not in ["rolado", "suministros", "1", "2"]:
            state = self.rolados_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ ROLADOS {phone_number} - 3 intentos fallidos en paso 1")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor responde con "rolado" o "suministros"

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.rolados_form_state[phone_number]
        servicio = "rolado" if user_response in ["rolado", "1"] else "suministros"
        state["data"]["servicio"] = servicio
        state["step"] = 2
        state["retry_count"] = 0
        
        logger.info(f"✅ Servicio: {servicio}")
        
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
            
            message = f"""❌ Por favor especifica tu ubicación correctamente

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.rolados_form_state[phone_number]
        state["data"]["ubicacion"] = user_response.strip()
        state["step"] = 3
        state["retry_count"] = 0
        
        # Paso 3: Cantidad
        message = """📝 *Paso 3 de 5:* ¿Cuántos kilos o toneladas necesitas?

Ejemplo: 500 kg, 2 toneladas, 1.5 ton"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")

    async def _step_3_cantidad(self, phone_number: str, user_response: str):
        """Paso 3: Cantidad"""
        
        if not self._is_valid_cantidad(user_response):
            state = self.rolados_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ ROLADOS {phone_number} - 3 intentos fallidos en paso 3")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor especifica una cantidad válida (ej: 500 kg)

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.rolados_form_state[phone_number]
        state["data"]["cantidad"] = user_response.strip()
        state["step"] = 3.5  # Paso intermedio
        state["retry_count"] = 0
        
        # Verificar si es ROLADO o SUMINISTROS
        servicio = state["data"].get("servicio", "")
        
        if servicio == "rolado":
            # Paso 4: Tipo de lámina
            message = """📝 *Paso 4 de 5:* ¿Qué tipo de lámina?

Responde con:
1️⃣ zintro alum
2️⃣ pintro

(Escribe: zintro alum o pintro)"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
        else:
            # Si es suministros, saltamos a confirmación
            state["step"] = 6
            await self._step_6_confirmation(phone_number, None)

    async def _step_4_lamina(self, phone_number: str, user_response: str):
        """Paso 4: Tipo de lámina"""
        
        user_response = user_response.lower().strip()
        
        # Aceptar múltiples formatos
        if "zintro" in user_response and "alum" in user_response:
            lamina_id = "zintro_alum"
        elif "zintro" in user_response:
            lamina_id = "zintro_alum"
        elif "pintro" in user_response:
            lamina_id = "pintro"
        elif user_response == "1":
            lamina_id = "zintro_alum"
        elif user_response == "2":
            lamina_id = "pintro"
        else:
            state = self.rolados_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ ROLADOS {phone_number} - 3 intentos fallidos en paso 4")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❌ Selecciona una lámina válida: zintro alum o pintro

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.rolados_form_state[phone_number]
        state["data"]["lamina"] = lamina_id
        state["step"] = 5
        state["retry_count"] = 0
        
        lamina_display = "Zintro Alum" if lamina_id == "zintro_alum" else "Pintro"
        logger.info(f"✅ Lámina: {lamina_display}")
        
        # Paso 5: Calibre
        message = """📝 *Paso 5 de 5:* ¿Qué calibre necesitas?

Disponemos del 18 al 24:
1️⃣ cal 18 (2.4mm)
2️⃣ cal 20 (1.6mm)
3️⃣ cal 22 (1.2mm)
4️⃣ cal 24 (0.8mm)

(Escribe: cal 18, cal 20, cal 22 o cal 24)"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")

    async def _step_5_calibre(self, phone_number: str, user_response: str):
        """Paso 5: Calibre"""
        
        user_response = user_response.lower().strip()
        
        # Detectar calibre
        calibre_map = {
            "cal 18": "cal_18", "cal_18": "cal_18", "18": "cal_18", "1": "cal_18",
            "cal 20": "cal_20", "cal_20": "cal_20", "20": "cal_20", "2": "cal_20",
            "cal 22": "cal_22", "cal_22": "cal_22", "22": "cal_22", "3": "cal_22",
            "cal 24": "cal_24", "cal_24": "cal_24", "24": "cal_24", "4": "cal_24",
        }
        
        calibre_id = calibre_map.get(user_response)
        
        if not calibre_id:
            state = self.rolados_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ ROLADOS {phone_number} - 3 intentos fallidos en paso 5")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❌ Selecciona un calibre válido: cal 18, cal 20, cal 22 o cal 24

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.rolados_form_state[phone_number]
        state["data"]["calibre"] = calibre_id
        state["step"] = 6
        state["retry_count"] = 0
        
        logger.info(f"✅ Calibre: {calibre_id}")
        
        # Paso 6: Confirmación
        await self._step_6_confirmation(phone_number, None)

    async def _step_6_confirmation(self, phone_number: str, user_response: Optional[str]):
        """Paso 6: Confirmación"""
        
        state = self.rolados_form_state[phone_number]
        data = state["data"]
        
        if user_response is None:
            # Mostrar resumen
            calibre_text = data.get('calibre', 'N/A')
            if calibre_text:
                calibre_display = calibre_text.replace('cal_', 'Cal ')
            else:
                calibre_display = "N/A"
            
            lamina_text = data.get('lamina', 'N/A')
            if lamina_text == 'zintro_alum':
                lamina_display = "Zintro Alum"
            elif lamina_text == 'pintro':
                lamina_display = "Pintro"
            else:
                lamina_display = "N/A"
            
            resumen = f"""✅ *RESUMEN DE TU SOLICITUD*

📦 *Servicio:* {data.get('servicio', 'N/A').upper()}
📍 *Ubicación:* {data.get('ubicacion', 'N/A')}
⚖️ *Cantidad:* {data.get('cantidad', 'N/A')}"""
            
            if data.get('servicio') == 'rolado':
                resumen += f"""
📋 *Lámina:* {lamina_display}
📏 *Calibre:* {calibre_display}"""
            
            resumen += """

¿Es correcto?

Responde: sí o no"""
            
            self.client.send_text_message(phone_number, resumen)
            self.db.save_message(phone_number, resumen, "sent")
            return
        
        user_response = user_response.lower().strip()
        
        if user_response in ["sí", "si", "s", "yes", "1"]:
            logger.info(f"✅ Formulario ROLADOS completado para {phone_number}")
            
            # Guardar lead
            self.db.save_lead_analysis(phone_number, {
                "lead_score": 8,
                "is_qualified_lead": True,
                "lead_type": "rolados_form",
                "summary_for_seller": f"Solicitud ROLADOS: {data.get('cantidad')}",
                "project_info": data
            })
            
            # Mensaje de confirmación
            confirmation = f"""✅ *¡Solicitud Enviada Correctamente!*

Tu solicitud de ARCOSUM ROLADOS ha sido registrada exitosamente y enviada al **Vendedor de ARCOSUM**.

📦 *Detalles registrados:*
• Servicio: {data.get('servicio').upper()}
• Ubicación: {data.get('ubicacion')}
• Cantidad: {data.get('cantidad')}"""
            
            if data.get('servicio') == 'rolado':
                confirmation += f"""
• Lámina: {data.get('lamina')}
• Calibre: {data.get('calibre')}"""
            
            confirmation += f"""

📞 *El Vendedor de ARCOSUM se pondrá en contacto contigo en las próximas 2 horas.*

Si es urgente: {self.vendor_phone}

*¡Gracias por confiar en ARCOSUM!* 🏭"""
            
            self.client.send_text_message(phone_number, confirmation)
            self.db.save_message(phone_number, confirmation, "sent")
            
            # Notificar vendedor
            await self._notify_vendor(phone_number, data)
            
            # Limpiar
            del self.rolados_form_state[phone_number]
        
        elif user_response in ["no", "n", "0"]:
            message = """🔄 Entendido. Cancelando solicitud.

Si cambias de idea, escribe cualquier mensaje para empezar de nuevo."""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            
            # Limpiar
            del self.rolados_form_state[phone_number]
        
        else:
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ ROLADOS {phone_number} - Cancelado")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor responde sí o no

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")

    async def _notify_vendor(self, phone_number: str, form_data: Dict):
        """Notifica al vendedor"""
        
        notification = f"""🚨 *NUEVA SOLICITUD ROLADOS*

📱 *Cliente:* {phone_number}

📦 *Servicio:* {form_data.get('servicio', 'N/A').upper()}
📍 *Ubicación:* {form_data.get('ubicacion', 'N/A')}
⚖️ *Cantidad:* {form_data.get('cantidad', 'N/A')}"""
        
        if form_data.get('servicio') == 'rolado':
            notification += f"""
📋 *Lámina:* {form_data.get('lamina', 'N/A')}
📏 *Calibre:* {form_data.get('calibre', 'N/A')}"""
        
        notification += "\n\n⏰ *Contactar en los próximos 30 minutos*"
        
        try:
            self.client.send_text_message(self.vendor_phone, notification)
            logger.info(f"📧 Notificación enviada al vendedor")
        except Exception as e:
            logger.error(f"Error notificando: {str(e)}")

    async def _send_vendor_contact(self, phone_number: str):
        """Envía contacto del vendedor"""
        
        message = f"""⚠️ Parece que hay un inconveniente con el formulario.

Te conectaremos directamente con el **Vendedor de ARCOSUM**:

☎️ WhatsApp: {self.vendor_phone}

Te atenderá en menos de 30 minutos. ¡Gracias por tu paciencia!"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")
        
        if phone_number in self.rolados_form_state:
            del self.rolados_form_state[phone_number]
        
        logger.info(f"📞 Contacto vendedor enviado")

    def _is_valid_cantidad(self, cantidad: str) -> bool:
        """Valida cantidad en kilos, toneladas"""
        cantidad_lower = cantidad.lower()
        pattern = r"(\d+[\.,]?\d*)\s*(kg|kilogramo|tonelada|ton|t)"
        return bool(re.search(pattern, cantidad_lower))