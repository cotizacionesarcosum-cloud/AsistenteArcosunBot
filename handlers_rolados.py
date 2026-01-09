import logging
from typing import Optional, Dict
from datetime import datetime
import asyncio
import re

logger = logging.getLogger(__name__)

class RoladosHandler:
    """Maneja formulario y lógica de ARCOSUM ROLADOS con IA asistida"""

    def __init__(self, client, database, ai_assistant, notifier):
        self.client = client
        self.db = database
        self.ai = ai_assistant
        self.notifier = notifier
        
        self.rolados_form_state = {}
        self.vendor_phone = "+52 222 114 8841"

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

Escribe: rolado (venta de láminas) o suministros"""
        
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
        """Paso 1: IA detecta servicio"""
        
        user_response = user_response.lower().strip()
        
        # Usar IA para detectar intención
        ia_prompt = f"""Analiza esta respuesta del usuario y determina si quiere:
- "rolado": Venta de láminas
- "suministros": Otros suministros
- "invalido": No es claro

Respuesta del usuario: "{user_response}"

Responde SOLO con: rolado, suministros o invalido"""
        
        try:
            ia_response = await self.ai.generate_response(ia_prompt)
            detected_service = ia_response.strip().lower()
            
            if detected_service not in ["rolado", "suministros"]:
                raise ValueError("Respuesta inválida de IA")
        except:
            detected_service = None
        
        # Si IA no detectó, intentar con palabras clave simples
        if not detected_service:
            if "rolado" in user_response or "lamina" in user_response:
                detected_service = "rolado"
            elif "suministro" in user_response:
                detected_service = "suministros"
        
        # Si aún no se detecta, reintentar
        if not detected_service:
            state = self.rolados_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ ROLADOS {phone_number} - 3 intentos fallidos en paso 1")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❓ No entendí bien. ¿Necesitas:
- Rolado (venta de láminas)
- Suministros (otros materiales)

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.rolados_form_state[phone_number]
        state["data"]["servicio"] = detected_service
        state["step"] = 2
        state["retry_count"] = 0
        
        logger.info(f"✅ Servicio (IA): {detected_service}")
        
        message = """📝 *Paso 2 de 5:* ¿En qué estado y municipio?

Ejemplo: Puebla, Puebla o Tlaxcala, Tenancingo"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")

    async def _step_2_ubicacion(self, phone_number: str, user_response: str):
        """Paso 2: IA valida ubicación"""
        
        if len(user_response.strip()) < 3:
            state = self.rolados_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ ROLADOS {phone_number} - 3 intentos fallidos en paso 2")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❓ Por favor especifica tu ubicación

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.rolados_form_state[phone_number]
        state["data"]["ubicacion"] = user_response.strip()
        state["step"] = 3
        state["retry_count"] = 0
        
        logger.info(f"✅ Ubicación: {user_response.strip()}")
        
        message = """📝 *Paso 3 de 5:* ¿Cuántos kilos o toneladas necesitas?

Ejemplos válidos:
- 100 kilos
- 100 kg
- 2 toneladas
- 1.5 ton
- cien kilos
- media tonelada"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")

    async def _step_3_cantidad(self, phone_number: str, user_response: str):
        """Paso 3: IA extrae cantidad de múltiples formatos"""
        
        # Usar IA para extraer cantidad de forma inteligente
        ia_prompt = f"""Extrae la cantidad de esta respuesta del usuario.

Respuesta: "{user_response}"

Normaliza el resultado a formato: "número unidad" (ejemplo: "100 kg", "2 toneladas")

Responde SOLO con el formato normalizado, o "INVALIDO" si no puedes extraer."""
        
        try:
            ia_response = await self.ai.generate_response(ia_prompt)
            extracted_quantity = ia_response.strip()
            
            if extracted_quantity.lower() == "invalido":
                raise ValueError("IA marcó como inválido")
            
            # Validar que IA extrajo algo sensato
            if not any(unit in extracted_quantity.lower() for unit in ["kg", "tonelada", "ton", "kilo"]):
                raise ValueError("Formato inválido")
            
            cantidad = extracted_quantity
            logger.info(f"✅ Cantidad (IA): {cantidad}")
        
        except:
            # Fallback: intentar regex simple
            pattern = r"(\d+[\.,]?\d*)\s*(kg|kilogramo|kilos|tonelada|ton|t)"
            match = re.search(pattern, user_response.lower())
            
            if not match:
                state = self.rolados_form_state[phone_number]
                state["retry_count"] += 1
                
                if state["retry_count"] >= 3:
                    logger.warning(f"⚠️ ROLADOS {phone_number} - 3 intentos fallidos en paso 3")
                    await self._send_vendor_contact(phone_number)
                    return
                
                message = f"""❓ No entendí la cantidad. Por favor especifica:
- Número: 100, 50, 2.5, etc.
- Unidad: kg, kilos, toneladas, ton

Ejemplo: "100 kg" o "2 toneladas"

*Intento {state["retry_count"]} de 3*"""
                
                self.client.send_text_message(phone_number, message)
                self.db.save_message(phone_number, message, "sent")
                return
            
            cantidad = f"{match.group(1)} {match.group(2)}"
        
        state = self.rolados_form_state[phone_number]
        state["data"]["cantidad"] = cantidad
        state["step"] = 4  # Avanzar a Step 4 (no 3.5)
        state["retry_count"] = 0
        
        # Verificar si es ROLADO o SUMINISTROS
        servicio = state["data"].get("servicio", "")
        
        if servicio == "rolado":
            # Paso 4: Tipo de lámina
            message = """📝 *Paso 4 de 5:* ¿Qué tipo de lámina?

Opciones:
- Zintro Alum
- Pintro

(Escribe cualquiera de estas)"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            logger.info(f"📋 Paso 4: Preguntando tipo de lámina")
        else:
            # Si es suministros, saltamos a confirmación
            state["step"] = 6
            await self._step_6_confirmation(phone_number, None)

    async def _step_4_lamina(self, phone_number: str, user_response: str):
        """Paso 4: IA detecta tipo de lámina"""
        
        # Usar IA para detectar lámina
        ia_prompt = f"""Analiza esta respuesta y detecta qué tipo de lámina quiere:
- "zintro_alum": Lámina Zintro Alum (zinc y aluminio)
- "pintro": Lámina Pintro (acabado pintado)
- "invalido": No es claro

Respuesta: "{user_response}"

Responde SOLO con: zintro_alum, pintro o invalido"""
        
        try:
            ia_response = await self.ai.generate_response(ia_prompt)
            detected_lamina = ia_response.strip().lower()
            
            if detected_lamina not in ["zintro_alum", "pintro"]:
                raise ValueError("Respuesta inválida")
        except:
            detected_lamina = None
        
        # Fallback: palabras clave simples
        if not detected_lamina:
            user_lower = user_response.lower()
            if "zintro" in user_lower:
                detected_lamina = "zintro_alum"
            elif "pintro" in user_lower:
                detected_lamina = "pintro"
        
        if not detected_lamina:
            state = self.rolados_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ ROLADOS {phone_number} - 3 intentos fallidos en paso 4")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❓ No entendí. ¿Quieres:
- Zintro Alum
- Pintro

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.rolados_form_state[phone_number]
        state["data"]["lamina"] = detected_lamina
        state["step"] = 5
        state["retry_count"] = 0
        
        lamina_display = "Zintro Alum" if detected_lamina == "zintro_alum" else "Pintro"
        logger.info(f"✅ Lámina (IA): {lamina_display}")
        
        message = """📝 *Paso 5 de 5:* ¿Qué calibre necesitas?

Disponemos de:
- Calibre 18 (2.4mm)
- Calibre 20 (1.6mm)
- Calibre 22 (1.2mm)
- Calibre 24 (0.8mm)

(Escribe: cal 18, cal 20, cal 22 o cal 24)"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")

    async def _step_5_calibre(self, phone_number: str, user_response: str):
        """Paso 5: IA detecta calibre"""
        
        # Usar IA para detectar calibre
        ia_prompt = f"""Extrae el número de calibre de esta respuesta.

Respuesta: "{user_response}"

Calibres disponibles: 18, 20, 22, 24

Responde SOLO con el número (18, 20, 22 o 24) o "INVALIDO"."""
        
        try:
            ia_response = await self.ai.generate_response(ia_prompt)
            calibre_num = ia_response.strip()
            
            if calibre_num not in ["18", "20", "22", "24"]:
                raise ValueError("Calibre inválido")
            
            calibre_id = f"cal_{calibre_num}"
        except:
            calibre_id = None
        
        # Fallback: regex simple
        if not calibre_id:
            pattern = r"(18|20|22|24)"
            match = re.search(pattern, user_response)
            
            if match:
                calibre_id = f"cal_{match.group(1)}"
        
        if not calibre_id:
            state = self.rolados_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ ROLADOS {phone_number} - 3 intentos fallidos en paso 5")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❓ Calibre no reconocido. Disponibles:
- 18 (2.4mm)
- 20 (1.6mm)
- 22 (1.2mm)
- 24 (0.8mm)

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.rolados_form_state[phone_number]
        state["data"]["calibre"] = calibre_id
        state["step"] = 6
        state["retry_count"] = 0
        
        logger.info(f"✅ Calibre (IA): {calibre_id}")
        
        await self._step_6_confirmation(phone_number, None)

    async def _step_6_confirmation(self, phone_number: str, user_response: Optional[str]):
        """Paso 6: Confirmación"""
        
        state = self.rolados_form_state[phone_number]
        data = state["data"]
        
        if user_response is None:
            # Mostrar resumen
            resumen = f"""✅ *RESUMEN DE TU SOLICITUD*

📦 *Servicio:* {data.get('servicio', 'N/A').upper()}
📍 *Ubicación:* {data.get('ubicacion', 'N/A')}
⚖️ *Cantidad:* {data.get('cantidad', 'N/A')}"""
            
            if data.get('servicio') == 'rolado':
                lamina_display = "Zintro Alum" if data.get('lamina') == 'zintro_alum' else data.get('lamina', 'N/A')
                calibre_display = data.get('calibre', 'N/A').replace('cal_', 'Cal ')
                resumen += f"""
📋 *Lámina:* {lamina_display}
📏 *Calibre:* {calibre_display}"""
            
            resumen += """

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
            logger.info(f"✅ Formulario ROLADOS completado para {phone_number}")
            
            # Guardar lead
            self.db.save_lead_analysis(phone_number, {
                "lead_score": 8,
                "is_qualified_lead": True,
                "lead_type": "rolados_form",
                "summary_for_seller": f"Solicitud ROLADOS: {data.get('cantidad')}",
                "project_info": data
            })
            
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
            
            await self._notify_vendor(phone_number, data)
            
            del self.rolados_form_state[phone_number]
        
        elif user_intent == "cancela":
            message = """🔄 Entendido. Cancelando solicitud.

Si cambias de idea, escribe cualquier mensaje para empezar de nuevo."""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            
            del self.rolados_form_state[phone_number]
        
        else:
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ ROLADOS {phone_number} - Cancelado")
                await self._send_vendor_contact(phone_number)
                return
            
            message = f"""❓ No entendí. Por favor responde:
- Sí (para confirmar)
- No (para cancelar)

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