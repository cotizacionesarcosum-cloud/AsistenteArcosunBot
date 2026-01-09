import logging
from typing import Optional, Dict
from datetime import datetime
import asyncio
import re

logger = logging.getLogger(__name__)

class SuministrosHandler:
    """Maneja formulario y lógica de ARCOSUM SUMINISTROS con IA asistida"""

    def __init__(self, client, database, ai_assistant, notifier, message_handler=None):
        self.client = client
        self.db = database
        self.ai = ai_assistant
        self.notifier = notifier
        self.message_handler = message_handler  # Referencia al orquestador principal
        
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

    def _detect_division_change(self, message: str) -> str:
        """Detecta si el usuario quiere cambiar a otra división.
        
        Retorna:
        - 'techos': si menciona TECHOS
        - 'rolados': si menciona ROLADOS
        - 'otros': si menciona OTROS
        - None: si no quiere cambiar
        """
        
        message_lower = message.lower()
        
        # Detección de TECHOS
        if any(word in message_lower for word in ["techo", "arcotecho", "estructura", "metalica"]):
            return "techos"
        
        # Detección de ROLADOS
        if any(word in message_lower for word in ["rolados", "rolado", "lamina", "laminado", "calibre"]):
            return "rolados"
        
        # Detección de OTROS
        if any(word in message_lower for word in ["otros", "otra cosa", "otra division", "consulta"]):
            return "otros"
        
        return None

    async def handle_suministros_message(self, phone_number: str, message_text: str, message_id: str):
        """Maneja mensajes para SUMINISTROS"""
        
        # Detectar cambio de división en CUALQUIER momento
        division_change = self._detect_division_change(message_text)
        if division_change:
            await self._redirect_division(phone_number, division_change)
            return
        
        if phone_number in self.suministros_form_state:
            await self._handle_suministros_form_response(phone_number, message_text)
        else:
            await self._init_suministros_form(phone_number)

    async def _redirect_division(self, phone_number: str, division: str):
        """Redirige el usuario a otra división"""
        division_names = {
            "techos": "🏗️ ARCOSUM TECHOS",
            "rolados": "🔧 ARCOSUM ROLADOS",
            "otros": "❓ ARCOSUM OTROS"
        }
        
        message = f"""Perfecto, te conecto con {division_names.get(division)}.

Por favor escribe "hola" para comenzar de nuevo."""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")
        
        # Limpiar estado del formulario si existe
        if phone_number in self.suministros_form_state:
            del self.suministros_form_state[phone_number]
        
        logger.info(f"🔄 Usuario redirigido a {division}")

    async def _init_suministros_form(self, phone_number: str):
        """Inicia el formulario de SUMINISTROS"""
        
        self.suministros_form_state[phone_number] = {
            "step": 0,  # Nuevo paso 0: pedir nombre
            "data": {},
            "retry_count": 0,
            "producto_seleccionado": None
        }
        
        logger.info(f"🆕 Formulario SUMINISTROS iniciado para {phone_number}")
        
        message = """🏢 *FORMULARIO SUMINISTROS* 📋

Te ayudaré a procesar tu solicitud de suministros.

📝 *Paso 1 de 6:* ¿Cuál es tu nombre completo?

(Formato: Nombre Apellido)"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")

    async def _handle_suministros_form_response(self, phone_number: str, message_text: str):
        """Maneja respuestas del formulario"""
        
        state = self.suministros_form_state[phone_number]
        current_step = state["step"]
        
        logger.info(f"📋 SUMINISTROS Form - Step: {current_step}, Message: {message_text}")
        
        try:
            if current_step == 0:
                await self._step_0_nombre(phone_number, message_text)
            elif current_step == 1:
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

    async def _step_0_nombre(self, phone_number: str, user_response: str):
        """Paso 0: Nombre del cliente"""
        
        if not self._is_valid_full_name(user_response):
            state = self.suministros_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ SUMINISTROS {phone_number} - 3 intentos fallidos en paso 0")
                await self._send_suministros_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor ingresa nombre y apellido válidos

Formato: Juan Pérez

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.suministros_form_state[phone_number]
        state["data"]["nombre"] = user_response.strip()
        state["step"] = 1
        state["retry_count"] = 0
        
        logger.info(f"✅ Nombre guardado: {user_response}")
        
        nombre_corto = user_response.split()[0]
        message = f"""✅ Gracias, {nombre_corto}!

📝 *Paso 2 de 6:* ¿Qué producto de ARCOSUM SUMINISTROS necesitas?

Responde con el número:

1️⃣ Lámina Lisa para Arcotecho (Pintro, Zintro Alum)
2️⃣ Lámina Estructural a Medida (R-72, R-101)
3️⃣ Extractores Atmosféricos
4️⃣ Lámina Poliacrílica para Franjas de Luz
5️⃣ Vigas y Trabes (IPR, HSS)"""
        
        self.client.send_text_message(phone_number, message)
        self.db.save_message(phone_number, message, "sent")

    async def _step_1_producto(self, phone_number: str, user_response: str):
        """Paso 1: Seleccionar producto - IA asistida"""
        
        user_response = user_response.strip()
        
        # Usar IA para detectar intención
        ia_prompt = f"""Analiza esta respuesta y detecta qué producto de SUMINISTROS quiere:
- "1": Lámina Lisa para Arcotecho
- "2": Lámina Estructural a Medida
- "3": Extractores Atmosféricos
- "4": Lámina Poliacrílica para Franjas de Luz
- "5": Vigas y Trabes
- "invalido": No es claro

Respuesta: "{user_response}"

Responde SOLO con: 1, 2, 3, 4, 5 o invalido"""
        
        try:
            ia_response = await self.ai.generate_response(ia_prompt)
            detected_option = ia_response.strip()
            
            if detected_option in ["1", "2", "3", "4", "5"]:
                user_response = detected_option
        except:
            # Fallback: usar respuesta original
            pass
        
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

Opciones:
1️⃣ Lámina Lisa
2️⃣ Lámina Estructural
3️⃣ Extractores
4️⃣ Lámina Poliacrílica
5️⃣ Vigas y Trabes

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
        """Paso 2: Seleccionar especificación (tipo de lámina, sección, etc.) - IA asistida"""
        
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
        
        # Validar respuesta con IA
        producto_info = self.productos[producto_key]
        user_response = user_response.strip()
        
        # IA para detectar opción
        ia_prompt = f"""El usuario está seleccionando entre estas opciones:
"""
        for idx, opcion in enumerate(producto_info["opciones"], 1):
            ia_prompt += f"{idx}. {opcion['title']}\n"
        
        ia_prompt += f"""
Respuesta del usuario: "{user_response}"

¿Cuál es la opción seleccionada? Responde SOLO con el número (1, 2, 3...) o "invalido"."""
        
        try:
            ia_response = await self.ai.generate_response(ia_prompt)
            detected_option = ia_response.strip()
            
            if detected_option.isdigit():
                user_response = detected_option
        except:
            # Fallback: usar respuesta original
            pass
        
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
        """Paso 3: Cantidad (para extractores, poliacrilica) o Tonelaje/Kilos (para láminas) o Medidas (para estructurales) - IA asistida"""
        
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
            
            elif producto_key == "lamina_lisa":
                message = """⚖️ *CANTIDAD DE LÁMINA LISA*

¿Cuántos kilos o toneladas necesitas?

*Opción 1 - Si sabes el tonelaje:*
- 100 kg
- 2 toneladas
- 1.5 ton

*Opción 2 - Si NO sabes el tonelaje:*
Dame las medidas del rollo
Formato: Ancho x Largo
Ejemplo: 3x30"""
            
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
        
        # Usar IA para validar cantidad/medidas/tonelaje
        ia_prompt = f"""Valida si esta respuesta es una cantidad, tonelaje, medidas o kilos válido:

Respuesta: "{user_response}"

Responde SOLO con: "valido" o "invalido"."""
        
        is_valid = False
        try:
            ia_response = await self.ai.generate_response(ia_prompt)
            is_valid = "valido" in ia_response.lower()
        except:
            # Fallback: validación por regex
            is_valid = self._is_valid_cantidad_medida_tonelaje(user_response, producto_key)
        
        if not is_valid:
            state = self.suministros_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ SUMINISTROS {phone_number} - 3 intentos fallidos en paso 3")
                await self._send_suministros_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor especifica una cantidad, tonelaje o medida válida

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
        """Paso 4: Largo de lámina estructural - IA asistida"""
        
        # Usar IA para validar medida
        ia_prompt = f"""Valida si esta es una medida válida (largo):

Respuesta: "{user_response}"

Responde SOLO con: "valido" o "invalido"."""
        
        is_valid = False
        try:
            ia_response = await self.ai.generate_response(ia_prompt)
            is_valid = "valido" in ia_response.lower()
        except:
            # Fallback: validación por regex
            is_valid = self._is_valid_medida(user_response)
        
        if not is_valid:
            state = self.suministros_form_state[phone_number]
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ SUMINISTROS {phone_number} - 3 intentos fallidos en paso 4")
                await self._send_suministros_vendor_contact(phone_number)
                return
            
            message = f"""❌ Por favor especifica un largo válido

Ejemplo: "3 metros" o "10 pies"

*Intento {state["retry_count"]} de 3*"""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            return
        
        state = self.suministros_form_state[phone_number]
        state["data"]["largo"] = user_response.strip()
        state["step"] = 5
        state["retry_count"] = 0
        
        logger.info(f"✅ Largo guardado: {user_response.strip()}")
        
        await self._step_5_confirmation(phone_number, None)

    async def _step_5_confirmation(self, phone_number: str, user_response: Optional[str]):
        """Paso 5: Confirmación - IA asistida"""
        
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
            logger.info(f"✅ Formulario SUMINISTROS completado para {phone_number}")
            
            # Guardar lead
            self.db.save_lead_analysis(phone_number, {
                "lead_score": 8,
                "is_qualified_lead": True,
                "lead_type": "suministros_form",
                "summary_for_seller": f"Solicitud SUMINISTROS: {data.get('producto')} - {data.get('especificacion')}",
                "project_info": data
            })
            
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
            
            # Mostrar menú principal
            await self._show_main_menu(phone_number)
            
            del self.suministros_form_state[phone_number]
        
        elif user_intent == "cancela":
            message = """🔄 Entendido. Cancelando solicitud.

Si cambias de idea, escribe cualquier mensaje para empezar de nuevo."""
            
            self.client.send_text_message(phone_number, message)
            self.db.save_message(phone_number, message, "sent")
            
            del self.suministros_form_state[phone_number]
        
        else:
            state["retry_count"] += 1
            
            if state["retry_count"] >= 3:
                logger.warning(f"⚠️ SUMINISTROS {phone_number} - Cancelado")
                await self._send_suministros_vendor_contact(phone_number)
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
        
        # Limpiar estado del formulario SUMINISTROS
        if phone_number in self.suministros_form_state:
            del self.suministros_form_state[phone_number]
        
        logger.info(f"📋 Redirigiendo a menú principal para {phone_number}")
        
        # Llamar al MessageHandler para mostrar el menú principal
        if self.message_handler:
            await self.message_handler.send_main_menu(phone_number)
            logger.info(f"✅ Menú principal enviado por MessageHandler para {phone_number}")
        else:
            # Fallback si no hay referencia al message_handler
            logger.warning(f"⚠️ No hay referencia a MessageHandler para {phone_number}")

    async def _notify_suministros_vendor(self, phone_number: str, form_data: Dict):
        """Notifica al vendedor de SUMINISTROS usando plantilla o mensaje directo"""
        
        try:
            # Parámetros para plantilla
            template_params = [
                "N/A",  # {{1}} Nombre (no requerido para suministros)
                phone_number,  # {{2}} Cliente
                form_data.get('producto', 'N/A'),  # {{3}} Descripción/Producto
                form_data.get('cantidad_medidas', 'N/A'),  # {{4}} Cantidad
                form_data.get('ubicacion', 'N/A') or form_data.get('especificacion', 'N/A'),  # {{5}}
                form_data.get('largo', 'N/A'),  # {{6}}
            ]
            
            self.client.send_template_message(
                to=self.vendor_phone,
                template_name="notificacion_lead_calificado",
                language_code="es_MX",
                parameters=template_params
            )
            logger.info(f"📧 Notificación enviada al vendedor SUMINISTROS (plantilla)")
            return
        except Exception as e:
            logger.error(f"❌ Error enviando plantilla: {str(e)}")
        
        # Si falla plantilla: Mensaje de texto normal
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
            logger.info(f"📧 Notificación (texto) enviada al vendedor SUMINISTROS")
        except Exception as e:
            logger.error(f"❌ Error notificando al vendedor: {str(e)}")
            logger.error(f"💡 Solución: Crea una plantilla aprobada en Meta/WhatsApp")

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
        
        logger.info(f"📞 Contacto vendedor SUMINISTROS enviado")

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

    def _is_valid_cantidad_medida_tonelaje(self, respuesta: str, producto_key: str) -> bool:
        """Valida cantidad, medidas o tonelaje según el producto"""
        respuesta_lower = respuesta.lower()
        
        if producto_key == "lamina_estructural":
            # Validar formato de medidas: "X metros x Y metros" o similar
            pattern = r"(\d+[\.,]?\d*)\s*(metros|m|pies|feet|')\s*x\s*(\d+[\.,]?\d*)\s*(metros|m|pies|feet|')"
            return bool(re.search(pattern, respuesta_lower, re.IGNORECASE))
        
        elif producto_key == "lamina_lisa":
            # Validar tonelaje/kilos O medidas de rollo
            # Tonelaje: "100 kg", "2 toneladas", "1.5 ton"
            tonelaje_pattern = r"(\d+[\.,]?\d*)\s*(kg|kilogramo|kilos|tonelada|ton|t)"
            # Medidas rollo: "3x30", "1.5 x 2"
            medidas_pattern = r"(\d+[\.,]?\d*)\s*x\s*(\d+[\.,]?\d*)"
            
            return bool(re.search(tonelaje_pattern, respuesta_lower, re.IGNORECASE)) or \
                   bool(re.search(medidas_pattern, respuesta_lower, re.IGNORECASE))
        
        else:
            # Para otros productos, validar que sea un número
            pattern = r"^\d+[\.,]?\d*$"
            return bool(re.search(pattern, respuesta.strip()))

    def _is_valid_medida(self, respuesta: str) -> bool:
        """Valida una medida (largo)"""
        respuesta_lower = respuesta.lower()
        pattern = r"(\d+[\.,]?\d*)\s*(metros|m|pies|feet|')"
        return bool(re.search(pattern, respuesta_lower, re.IGNORECASE))

    def _is_valid_full_name(self, name: str) -> bool:
        """Valida nombre y apellido"""
        parts = name.strip().split()
        if len(parts) < 2:
            return False
        pattern = r"^[a-záéíóúñA-ZÁÉÍÓÚÑ\s]+$"
        return bool(re.match(pattern, name.strip()))