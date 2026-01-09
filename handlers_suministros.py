import logging
from typing import Optional, Dict
from datetime import datetime
import asyncio
import re

logger = logging.getLogger(__name__)

class SuministrosHandler:
    """Maneja formulario y lógica de ARCOSUM SUMINISTROS"""

    def __init__(self, client, database, ai_assistant, notifier):
        self.client = client
        self.db = database
        self.ai = ai_assistant
        self.notifier = notifier
        
        self.suministros_form_state = {}  # {phone_number: {"step": int, "data": {...}, "retry_count": int}}
        
        # Datos de vendedor SUMINISTROS (mismo que ROLADOS)
        self.vendor_phone = "+52 222 114 8841"
        
        # Productos de SUMINISTROS
        self.productos = {
            "lamina_lisa": {
                "nombre": "Lámina Lisa para Arcotecho (Rollo 3\")",
                "opciones": [
                    {"id": "pintro", "title": "Pintro"},
                    {"id": "zintro_alum", "title": "Zintro Alum"}
                ]
            },
            "lamina_estructural": {
                "nombre": "Lámina Estructural a Medida",
                "opciones": [
                    {"id": "r72", "title": "R-72"},
                    {"id": "r101", "title": "R-101"}
                ]
            },
            "extractores": {
                "nombre": "Extractores Atmosféricos"
            },
            "poliacrilica": {
                "nombre": "Rollo Lámina Poliacrílica para Franjas de Luz",
                "especificacion": "Medida única: 25 metros x 3 pies de ancho"
            },
            "vigas_trabes": {
                "nombre": "Vigas y Trabes",
                "opciones": [
                    {"id": "ipr", "title": "IPR"},
                    {"id": "hss", "title": "HSS"}
                ]
            }
        }

    async def handle_suministros_message(self, phone_number: str, message_text: str, message_id: str):
        """Maneja mensajes para SUMINISTROS"""
        
        if phone_number in self.suministros_form_state:
            await self._handle_suministros_form_response(phone_number, message_text)
        else:
            await self._init_suministros_form(phone_number)

    async def _init_suministros_form(self, phone_number: str):
        """Inicia el formulario de SUMINISTROS"""
        
        self.suministros_form_state[phone_number] = {
            "step": 1,
            "data": {},
            "retry_count": 0,
            "producto_seleccionado": None
        }
        
        logger.info(f"🆕 Formulario SUMINISTROS iniciado para {phone_number}")
        
        message = """🏢 *FORMULARIO SUMINISTROS* 📋

¿Qué producto de ARCOSUM SUMINISTROS necesitas?

Responde con el número:

1️⃣ Lámina Lisa para Arcotecho (Pintro, Zintro Alum)
2️⃣ Lámina Estructural a Medida (R-72, R-101)
3️⃣ Extractores Atmosféricos
4️⃣ Lámina Poliacrílica para Franjas de Luz
5️⃣ Vigas y Trabes (IPR, HSS)"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")

    async def _handle_suministros_form_response(self, phone_number: str, message_text: str):
        """Maneja respuestas del formulario"""
        
        state = self.suministros_form_state[phone_number]
        current_step = state["step"]
        
        logger.info(f"📋 SUMINISTROS Form - Step: {current_step}, Message: {message_text}")
        
        try:
            if current_step == 1:
                await self._step_1_producto(phone_number, message_text)
            elif current_step == 2:
                await self._step_2_especificacion(phone_number, message_text)
            elif current_step == 3:
                await self._step_3_cantidad_medidas(phone_number, message_text)
            elif current_step == 4:
                await self._step_4_largo(phone_number, message_text)
            elif current_step == 5:
                await self._step_5_confirmation(phone_number, message_text)
        except Exception as e:
            logger.error(f"Error en formulario SUMINISTROS: {str(e)}")
            await self._send_suministros_vendor_contact(phone_number)

    async def _step_1_producto(self, phone_number: str, user_response: str):
        """Paso 1: Seleccionar producto"""
        
        user_response = user_response.strip()
        
        productos_map = {
            "1": "lamina_lisa",
            "2": "lamina_estructural",
            "3": "extractores",
            "4": "poliacrilica",
            "5": "vigas_trabes"
        }
        
        if user_response not in productos_map:
            state = self.suministros_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ SUMINISTROS {phone_number} - 3 intentos fallidos en paso 1")
                await self._send_suministros_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor responde con un número válido (1, 2, 3, 4 o 5)

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.suministros_form_state[phone_number]
        producto_key = productos_map[user_response]
        state["producto_seleccionado"] = producto_key
        state["data"]["producto"] = self.productos[producto_key]["nombre"]
        state["step"] = 2
        state["retry_count"] = 0
        
        logger.info(f"✅ Producto seleccionado: {producto_key}")
        
        # Siguiente paso depende del producto
        await self._step_2_especificacion(phone_number, None)

    async def _step_2_especificacion(self, phone_number: str, user_response: Optional[str]):
        """Paso 2: Seleccionar especificación (tipo de lámina, sección, etc.)"""
        
        state = self.suministros_form_state[phone_number]
        producto_key = state["producto_seleccionado"]
        
        # Si es None, mostrar opciones
        if user_response is None:
            producto_info = self.productos[producto_key]
            
            # Algunos productos no tienen especificaciones
            if producto_key == "extractores":
                state["data"]["especificacion"] = "Extractores Atmosféricos"
                state["step"] = 3
                await self._step_3_cantidad_medidas(phone_number, None)
                return
            
            elif producto_key == "poliacrilica":
                state["data"]["especificacion"] = "25m x 3 pies"
                message = f"""📝 *LÁMINA POLIACRÍLICA PARA FRANJAS DE LUZ*

📌 *Especificación:* {producto_info['especificacion']}

¿Cuántos rollos necesitas?"""
                
                self.client.send_text_message(phone_number, message)
                self.db.save_message(phone_number, message, "sent")
                state["step"] = 3
                return
            
            # Productos con opciones
            mensaje = f"""📝 *{producto_info['nombre']}*

Selecciona el tipo:

"""
            for idx, opcion in enumerate(producto_info["opciones"], 1):
                mensaje += f"{idx}️⃣ {opcion['title']}\n"
            
            self.client.send_text_message(phone_number, mensaje)
            self.db.save_message(phone_number, mensaje, "sent")
            return
        
        # Validar respuesta
        producto_info = self.productos[producto_key]
        user_response = user_response.strip()
        
        valid_opciones = [str(i) for i in range(1, len(producto_info["opciones"]) + 1)]
        
        if user_response not in valid_opciones:
            state = self.suministros_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ SUMINISTROS {phone_number} - 3 intentos fallidos en paso 2")
                await self._send_suministros_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor selecciona una opción válida

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        # Guardar especificación
        opcion_idx = int(user_response) - 1
        opcion_seleccionada = producto_info["opciones"][opcion_idx]
        
        state["data"]["especificacion"] = opcion_seleccionada["title"]
        state["step"] = 3
        state["retry_count"] = 0
        
        logger.info(f"✅ Especificación: {opcion_seleccionada['title']}")
        
        # Siguiente paso
        await self._step_3_cantidad_medidas(phone_number, None)

    async def _step_3_cantidad_medidas(self, phone_number: str, user_response: Optional[str]):
        """Paso 3: Cantidad (para extractores, poliacrilica) o Medidas (para estructurales)"""
        
        state = self.suministros_form_state[phone_number]
        producto_key = state["producto_seleccionado"]
        
        if user_response is None:
            if producto_key == "lamina_estructural":
                message = """📏 *MEDIDAS DE LÁMINA ESTRUCTURAL*

¿Qué medida necesitas?

Especifica:
• Ancho (en metros o pies)
• Alto (en metros o pies)

Ejemplo: "2 metros x 3 metros" o "6 pies x 9 pies" """
            
            elif producto_key in ["extractores", "poliacrilica"]:
                message = f"""📦 *CANTIDAD REQUERIDA*

¿Cuántas unidades necesitas?

(Solo números, ejemplo: 5)"""
            
            else:
                message = f"""📦 *CANTIDAD REQUERIDA*

¿Cuántas unidades necesitas?"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        # Validar respuesta
        if not self._is_valid_cantidad_medida(user_response, producto_key):
            state = self.suministros_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ SUMINISTROS {phone_number} - 3 intentos fallidos en paso 3")
                await self._send_suministros_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor especifica una cantidad o medida válida

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state["data"]["cantidad_medidas"] = user_response.strip()
        state["step"] = 4
        state["retry_count"] = 0
        
        # Para estructurales, pedir largo
        if producto_key == "lamina_estructural":
            message = """📏 *LARGO DE LA LÁMINA*

¿Cuál es el largo?

Especifica en metros o pies:
Ejemplo: "3 metros" o "10 pies" """
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
        else:
            # Saltar a confirmación
            state["step"] = 5
            await self._step_5_confirmation(phone_number, None)

    async def _step_4_largo(self, phone_number: str, user_response: str):
        """Paso 4: Largo de lámina estructural"""
        
        if not self._is_valid_medida(user_response):
            state = self.suministros_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ SUMINISTROS {phone_number} - 3 intentos fallidos en paso 4")
                await self._send_suministros_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor especifica un largo válido

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.suministros_form_state[phone_number]
        state["data"]["largo"] = user_response.strip()
        state["step"] = 5
        state["retry_count"] = 0
        
        await self._step_5_confirmation(phone_number, None)

    async def _step_5_confirmation(self, phone_number: str, user_response: Optional[str]):
        """Paso 5: Confirmación"""
        
        state = self.suministros_form_state[phone_number]
        data = state["data"]
        
        if user_response is None:
            # Mostrar resumen
            resumen = f"""✅ *RESUMEN DE TU SOLICITUD*

📦 *Producto:* {data.get('producto', 'N/A')}
📋 *Especificación:* {data.get('especificacion', 'N/A')}
⚖️ *Cantidad/Medidas:* {data.get('cantidad_medidas', 'N/A')}
"""
            
            if data.get('largo'):
                resumen += f"📏 *Largo:* {data.get('largo', 'N/A')}\n"
            
            resumen += """
¿Es correcto? Responde:
✅ Sí, enviar
❌ No, cancelar"""
            
            self.client.send_text_message(phone_number, resumen)
            self.db.save_message(phone_number, resumen, "sent")
            return
        
        if user_response.lower() in ["sí", "si", "✅", "ok", "enviar"]:
            logger.info(f"✅ Formulario SUMINISTROS completado para {phone_number}")
            
            # Guardar lead
            self.db.save_lead_analysis(phone_number, {
                "lead_score": 8,
                "is_qualified_lead": True,
                "lead_type": "suministros_form",
                "summary_for_seller": f"Solicitud SUMINISTROS: {data.get('producto')} - {data.get('especificacion')}",
                "project_info": data
            })
            
            # Mensaje de despedida MANUAL (sin IA)
            goodbye = f"""✅ *¡Solicitud Enviada Correctamente!*

Tu solicitud de ARCOSUM SUMINISTROS ha sido registrada exitosamente y enviada al Vendedor de ARCOSUM.

📦 *Detalles registrados:*
• Producto: {data.get('producto')}
• Especificación: {data.get('especificacion')}
• Cantidad/Medidas: {data.get('cantidad_medidas')}"""
            
            if data.get('largo'):
                goodbye += f"\n• Largo: {data.get('largo')}"
            
            goodbye += f"""

📞 *El Vendedor de ARCOSUM se pondrá en contacto contigo en las próximas 2 horas.*

Si es urgente: {self.vendor_phone}

*¡Gracias por confiar en ARCOSUM!* 🏭"""
            
            self.client.send_text_message(phone_number, goodbye)
            self.db.save_message(phone_number, goodbye, "sent")
            
            # Notificar vendedor
            await self._notify_suministros_vendor(phone_number, data)
            
            # Limpiar
            del self.suministros_form_state[phone_number]
        else:
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ SUMINISTROS {phone_number} - Cancelado")
                await self._send_suministros_vendor_contact(phone_number)
                return
            
            message = f"""❌ Responde con:
✅ Sí (enviar)
❌ No (cancelar)

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")

    async def _notify_suministros_vendor(self, phone_number: str, form_data: Dict):
        """Notifica al vendedor de SUMINISTROS"""
        
        notification = f"""🚨 *NUEVA SOLICITUD SUMINISTROS*

📱 *Cliente:* {phone_number}

📦 *Producto:* {form_data.get('producto', 'N/A')}
📋 *Especificación:* {form_data.get('especificacion', 'N/A')}
⚖️ *Cantidad/Medidas:* {form_data.get('cantidad_medidas', 'N/A')}
"""
        
        if form_data.get('largo'):
            notification += f"📏 *Largo:* {form_data.get('largo', 'N/A')}\n"
        
        notification += "\n⏰ *Contactar en los próximos 30 minutos*"
        
        try:
            self.client.send_text_message(self.vendor_phone, notification)
            logger.info(f"📧 Notificación enviada al vendedor SUMINISTROS")
        except Exception as e:
            logger.error(f"Error notificando: {str(e)}")

    async def _send_suministros_vendor_contact(self, phone_number: str):
        """Envía contacto del vendedor cuando hay problemas"""
        
        message = f"""⚠️ Parece que hay un inconveniente con el formulario.

Te conectaremos directamente con el **Vendedor de ARCOSUM**:

☎️ WhatsApp: {self.vendor_phone}

Te atenderá en menos de 30 minutos. ¡Gracias por tu paciencia!"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")
        
        if phone_number in self.suministros_form_state:
            del self.suministros_form_state[phone_number]
        
        logger.info(f"📞 Contacto vendedor enviado")

    def _is_valid_cantidad_medida(self, respuesta: str, producto_key: str) -> bool:
        """Valida cantidad o medidas según el producto"""
        respuesta_lower = respuesta.lower()
        
        if producto_key == "lamina_estructural":
            # Validar formato de medidas: "X metros x Y metros" o similar
            pattern = r"(\d+[\.,]?\d*)\s*(metros|m|pies|feet|')\s*x\s*(\d+[\.,]?\d*)\s*(metros|m|pies|feet|')"
            return bool(re.search(pattern, respuesta_lower, re.IGNORECASE))
        else:
            # Validar que sea un número
            pattern = r"^\d+[\.,]?\d*$"
            return bool(re.search(pattern, respuesta.strip()))

    def _is_valid_medida(self, respuesta: str) -> bool:
        """Valida una medida (largo)"""
        respuesta_lower = respuesta.lower()
        pattern = r"(\d+[\.,]?\d*)\s*(metros|m|pies|feet|')"
        return bool(re.search(pattern, respuesta_lower, re.IGNORECASE))