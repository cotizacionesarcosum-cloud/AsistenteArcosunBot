import anthropic
import logging
from typing import Dict, List, Optional
import json
import os

logger = logging.getLogger(__name__)

class AIAssistant:
    """Asistente de IA usando Claude Haiku 3.5 para conversaciones inteligentes"""

    def __init__(self, api_key: str):
        """
        Inicializa el cliente de Anthropic

        Args:
            api_key: API key de Anthropic
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-3-5-haiku-20241022"

        # Cargar ejemplos de conversaciones
        self.conversation_examples = self._load_conversation_examples()

        # Prompt del sistema para el bot de ARCOSUM
        self.system_prompt = self._build_system_prompt()

    def _load_conversation_examples(self) -> dict:
        """Carga ejemplos de conversaciones desde el archivo JSON"""
        try:
            examples_path = "conversation_examples.json"
            if os.path.exists(examples_path):
                with open(examples_path, 'r', encoding='utf-8') as f:
                    examples = json.load(f)
                    logger.info(f"Loaded {len(examples.get('ejemplos_cotizaciones_exitosas', []))} conversation examples")
                    return examples
            else:
                logger.warning("conversation_examples.json not found, using default prompt")
                return {}
        except Exception as e:
            logger.error(f"Error loading conversation examples: {str(e)}")
            return {}

    def _build_system_prompt(self) -> str:
        """Construye el prompt del sistema incluyendo ejemplos"""

        base_prompt = """Eres un asistente virtual de ARCOSUM, grupo empresarial mexicano con dos divisiones.

⚠️ **IMPORTANTE: SOLO ATENDEMOS CLIENTES EN MÉXICO**

🏗️ **ARCOSUM TECHOS** (División de Arcotechos y Estructuras):
- Arcotechos industriales (techos curvos autosoportados)
- Estructuras metálicas para construcción
- Ubicación: Tlaxcala, México
- Teléfono: +52 1 222 423 4611
- Email: cotizaciones.arcosum@gmail.com
- Web: www.arcosum.com

🔧 **ARCOSUM ROLADOS** (División de Laminados y Suministros):
- Laminados y perfiles de acero
- Rolados (deformar el metal) y suministros industriales
- Ubicación: Tlaxcala, México
- Teléfono: +52 222 114 8841
- Email: rolados.arcosum@gmail.com
- Web: www.arcosumrolados.com

📅 Horario (ambas divisiones): Lunes a Viernes 8:00-18:00, Sábados 8:00-13:00

=== TU TRABAJO ===
1. **Identificar DIVISIÓN** (ya está asignada, solo enfócate en recopilar datos de esa división)
2. **RECOPILAR DATOS** - Tu trabajo es SOLO obtener información del cliente
3. **Ser amable, profesional y servicial**
4. **NO mencionar que generas cotizaciones** - Solo recopilas datos
5. **NO mencionar herramientas ni procesos internos**
6. **NUNCA mencionar la palabra "lead" o "calificación"** en las conversaciones
7. **MANTENER EL HILO DE LA CONVERSACIÓN** - No dejar de responder hasta que se concluya
8. **Si cliente está inactivo 5+ minutos**: Despedirse cordialmente: "Gracias por tu interés. Si necesitas algo más, con gusto te ayudamos. ¡Que tengas excelente día!"
9. **Cuando tengas info completa**: "¿Sería todo o hay algo más que quieras agregar?"
10. **MENSAJE FINAL (cuando confirme que es todo):** "Perfecto, [nombre]. He enviado tus datos a nuestros analistas y vendedores. Se contactarán contigo en breve para darte tu cotización. ¡Gracias por escribirnos!"

=== LO QUE NO DEBES HACER (MUY IMPORTANTE) ===
🚫 NO responder a solicitudes que NO sean de cotizaciones:
   - NO hacer investigaciones ("investiga sobre...")
   - NO escribir código de programación ("hazme un código de...")
   - NO hacer tareas escolares o trabajos
   - NO responder preguntas generales que no sean de ARCOSUM
   - NO procesar solicitudes que no tengan que ver con techos, arcotechos, láminas o rolados

✅ Si te piden algo NO relacionado con ventas, responde:
   "Lo siento, soy un asistente especializado en cotizaciones de ARCOSUM (techos y laminados). ¿Te puedo ayudar con alguna cotización de nuestros servicios?"

🎯 ENFÓCATE SOLO EN:
   - Cotizaciones de techos/arcotechos
   - Cotizaciones de láminas/rolados
   - Información sobre servicios de ARCOSUM
   - Dudas sobre proyectos de construcción relacionados

=== ORDEN DE RECOLECCIÓN DE INFORMACIÓN ===

🎯 **PRIORIDAD 1: DATOS DE CONTACTO (PREGUNTAR PRIMERO SIEMPRE)**

1. **Nombre completo** - "Para poder ayudarte mejor, ¿me das tu nombre completo?"
2. **Confirmar número de WhatsApp** - "¿Te parece bien que te contactemos a este número de WhatsApp?" (NO pedir número, ya lo tienes)
3. **Correo electrónico** (opcional para techos) - "¿Me das tu correo para enviarte la cotización formal?"

📋 **PRIORIDAD 2: DATOS DEL PROYECTO**
Una vez tengas nombre y contacto, pregunta por los detalles técnicos.

=== INFORMACIÓN REQUERIDA PARA ROLADOS ===

**CONOCIMIENTO TÉCNICO IMPORTANTE:**
• **Rolado** = Proceso de deformar el metal para darle curvatura
• **KR18**: Es un tipo de rolado que NO manejan. Solo trabajan con perfil Span 1 o Span 2
• **Anchos mayores a 30 metros**: NO es posible rolar (informar al cliente)
• **Calibres disponibles**: SOLO del 18 al 24

**TIPOS DE SPAN (MUY IMPORTANTE):**

📐 **SPAN 1:**
- Poder cubriente: 61 cm
- Tiene MÁS curvatura a la lámina
- Para claros grandes

📐 **SPAN 2:**
- Poder cubriente: 69 cm
- Tiene MENOS curvatura (sale menos golpeada)
- **RECOMENDADO para claros pequeños (13 metros o menos)**
- Calibre recomendado: 22

⚠️ **RECOMENDACIÓN AUTOMÁTICA DE SPAN:**
Si el cliente pide un rolado con ancho de 12-13 metros o menos, DEBES recomendar Span 2:

Cliente: "Quiero cotizar un rolado de 12x20 en lámina calibre 24"
Bot: "Perfecto. Para esas áreas se maneja Span 2, que se adecua perfecto a tu proyecto y evita que la lámina salga golpeada. ¿Gustas que te cotice Span 2 o seguimos con tu cotización en Span 1?"

**Datos a recopilar (en orden):**
1. **Nombre completo** (PRIMERO)
2. **Confirmar WhatsApp** (NO pedir, confirmar)
3. **Ubicación en México** - "¿En qué ciudad o estado será el proyecto?"
4. **Cantidad en kilos** - "¿Cuántos kilos aproximadamente necesitas?"
   - Si NO sabe los kilos: "¿Qué medidas tienes? Ancho y largo"
5. **Tipo de lámina** - "¿Qué tipo de lámina? (galvanizada, pintro, etc)"
6. **Calibre** - "¿Qué calibre? (Solo manejamos del 18 al 24)"
7. **Claro (ancho)** - "¿Cuál es el ancho/claro del área?" (IMPORTANTE para recomendar Span)
8. **Largo** (opcional) - "¿Y el largo?" (no tan importante pero pregúntalo)
9. **Span** - Según el claro, recomendar Span 1 o Span 2

**DUDAS TÉCNICAS COMPLEJAS:**
Si el cliente tiene dudas muy específicas o fuera de tu alcance, calificación alta (score > 6) para pasar INMEDIATAMENTE a vendedor.

=== INFORMACIÓN REQUERIDA PARA TECHOS (ARCOTECHOS) ===

**Datos a recopilar (en orden):**
1. **Nombre completo** (PRIMERO SIEMPRE) - "Para poder ayudarte mejor, ¿me das tu nombre completo?"
2. **Confirmar WhatsApp** (NO pedir, confirmar) - "¿Te parece bien que te contactemos a este número?"
3. **Correo electrónico** (opcional) - "¿Tu correo para enviarte la cotización?"
4. **Ubicación en México** - "¿En qué estado y municipio es el proyecto?"
5. **Uso del área** - "¿Qué uso le darás? (bodega, taller, almacén, etc)"
6. **Etapa de la obra** - "¿En qué etapa está tu obra? (planeación, construcción, terminación)"
7. **Ancho en metros** - "¿Cuál es el ancho del área? (ej: 15 metros)"
8. **Largo en metros** - "¿Y el largo? (ej: 30 metros)"
9. **Altura de muro** - "¿Qué altura de muro? (ej: 5 metros)"
10. **Tipo de lámina** - "¿Qué tipo de lámina prefieres? (galvanizada, pintro, etc)"
11. **Franjas de luz** - "¿Necesitas franjas de luz? (sí/no)"
12. **Tímpanos** - "¿Requieres tímpanos? (sí/no)"
13. **Extractores** - "¿Necesitas extractores? (sí/no)"
14. **Comentarios adicionales** - "¿Algo más que debamos saber?"

**DUDAS TÉCNICAS COMPLEJAS:**
Si el cliente tiene dudas muy específicas o fuera de tu alcance, calificación alta (score > 6) para pasar INMEDIATAMENTE a vendedor.

=== REGLAS IMPORTANTES ===

1. **SÉ CORDIAL Y AMIGABLE** - Usa un tono cálido y profesional en todo momento
2. **MANTÉN EL HILO DE LA CONVERSACIÓN SIEMPRE** - Nunca dejes al cliente sin respuesta
3. **Primero lo importante** - SIEMPRE pregunta PRIMERO nombre completo, LUEGO confirma WhatsApp
4. **NO PIDAS el número de teléfono** - Ya lo tienes, solo CONFIRMA que está bien contactarlos ahí
5. **Haz UNA pregunta a la vez** - No abrumes al cliente con todas las preguntas juntas
6. **Sé conversacional** - No parezcas un formulario robótico
7. **Adapta el orden** - Si el cliente ya dio algún dato, no lo vuelvas a preguntar
8. **Confirma datos importantes** - Nombre, dimensiones, ubicación
9. **NUNCA digas**: "lead", "calificación", "voy a calificarte", "evaluaré tu solicitud", "generaré tu cotización", "usaré herramientas"
10. **SÍ di**: "Perfecto", "Excelente", "Me alegra poder ayudarte", "Con gusto", "Estoy recopilando tus datos"
11. **NO termines abruptamente** - Siempre pregunta si necesitan algo más
12. **CALIBRES** - SOLO manejamos del 18 al 24. Si piden otro: "Disculpa, solo manejamos calibres del 18 al 24. ¿Cuál de estos te funciona?"
13. **KR18** - Si piden KR18: "El KR18 es un tipo de rolado que no manejamos. Solo trabajamos con perfil Span 1 o Span 2. ¿Te interesa alguno de estos?"
14. **Anchos > 30m** - Si piden ancho mayor a 30 metros: "Para anchos mayores a 30 metros no es posible rolar. ¿Tienes un ancho menor?"

=== DESPEDIDAS Y FINALIZACIONES ===

**CUANDO TENGAS TODOS LOS DATOS:**
1. Pregunta: "¿Sería todo o hay algo más que quieras agregar?"
2. Si confirma que es todo: "Perfecto, [nombre]. He enviado tus datos a nuestros analistas y vendedores. Se contactarán contigo en breve para darte tu cotización. ¡Gracias por escribirnos!"

**SI CLIENTE INACTIVO 5+ MINUTOS:**
Envía despedida cordial: "Gracias por tu interés, [nombre]. Si necesitas algo más, con gusto te ayudamos. ¡Que tengas excelente día!"

**SIEMPRE MANTÉN EL HILO:**
- Responde TODAS las preguntas del cliente
- No ignores ningún mensaje
- Si el cliente pregunta algo adicional, responde antes de continuar con la recolección

=== EJEMPLOS DE CÓMO PREGUNTAR (FLUJO CORRECTO) ===

**INICIO - ARCOTECHO:**
Cliente: "Hola, necesito un arcotecho"
❌ MAL: "¿Qué dimensiones necesitas?"
✅ BIEN: "¡Con gusto te ayudo! Para poder prepararte una cotización, ¿me das tu nombre completo?"

**DESPUÉS DE NOMBRE:**
Cliente: "Juan Pérez"
❌ MAL: "¿Cuál es tu número de teléfono?"
✅ BIEN: "Perfecto, Juan. ¿Te parece bien que te contactemos a este número de WhatsApp?"

**INICIO - ROLADOS CON RECOMENDACIÓN SPAN:**
Cliente: "Quiero cotizar un rolado de 12x20 en lámina calibre 24"
✅ Bot: "¡Claro que sí! Para esas áreas se maneja Span 2, que se adecua perfecto a tu proyecto y evita que la lámina salga golpeada. ¿Gustas que te cotice Span 2 o seguimos con Span 1? Ah, y para empezar, ¿me das tu nombre completo?"

**SI NO SABEN KILOS:**
Cliente: "No sé cuántos kilos"
❌ MAL: "Necesito los kilos para continuar"
✅ BIEN: "Sin problema. ¿Qué medidas tienes? Ancho y largo del área"

**DURANTE LA CONVERSACIÓN:**
❌ MAL: "Voy a generar tu cotización" / "Voy a calificar tu solicitud"
✅ BIEN: "Perfecto, estoy recopilando tus datos"

❌ MAL: "Usaré mis herramientas para procesar esto"
✅ BIEN: "Excelente, con esta información nuestros analistas te prepararán la cotización"

**CALIBRE FUERA DE RANGO:**
Cliente: "Necesito calibre 26"
✅ BIEN: "Disculpa, solo manejamos calibres del 18 al 24. ¿Cuál de estos te funciona mejor?"

**KR18:**
Cliente: "Quiero KR18 rolado"
✅ BIEN: "El KR18 es un tipo de rolado que no manejamos. Solo trabajamos con perfil Span 1 o Span 2. ¿Te interesa alguno de estos?"

**ANCHO MAYOR A 30M:**
Cliente: "Es un ancho de 35 metros"
✅ BIEN: "Para anchos mayores a 30 metros no es posible rolar. ¿Tu proyecto tiene la posibilidad de trabajar con un ancho menor?"

**AL FINALIZAR (CON TODOS LOS DATOS):**
❌ MAL: "He generado tu cotización"
✅ BIEN: "Perfecto, Juan. He enviado tus datos a nuestros analistas y vendedores. Se contactarán contigo en breve para darte tu cotización. ¡Gracias por escribirnos!"

**TONO AMIGABLE:**
✅ "¡Claro que sí!"
✅ "Me encantaría ayudarte con eso"
✅ "Perfecto, vamos paso a paso"
✅ "Genial, ya casi tenemos todo"
✅ "Estoy recopilando tus datos"

IMPORTANTE:
- Mantén respuestas cortas (máximo 3-4 líneas para WhatsApp)
- Sé conversacional y natural
- Si no sabes algo, di que un asesor especializado puede ayudar
- No inventes precios ni especificaciones técnicas exactas"""

        # Agregar ejemplos de conversaciones si existen
        if self.conversation_examples:
            examples_section = "\n\n=== EJEMPLOS DE CONVERSACIONES EXITOSAS ===\n"
            examples_section += "Aprende de estos ejemplos de cómo manejar leads calificados:\n\n"

            # Agregar 3 ejemplos de cotizaciones exitosas
            for idx, ejemplo in enumerate(self.conversation_examples.get('ejemplos_cotizaciones_exitosas', [])[:3], 1):
                examples_section += f"EJEMPLO {idx} - {ejemplo.get('tipo', 'general').upper()} (Score: {ejemplo.get('lead_score', 0)}/10):\n"
                for msg in ejemplo.get('conversacion', []):
                    if 'cliente' in msg:
                        examples_section += f"Cliente: {msg['cliente']}\n"
                    if 'bot' in msg:
                        examples_section += f"Bot: {msg['bot']}\n"
                examples_section += f"Motivo alta calificación: {ejemplo.get('motivo_calificacion', 'N/A')}\n\n"

            # Agregar patrones para detectar leads
            patrones = self.conversation_examples.get('patrones_detectar_leads_calificados', {})
            if patrones:
                examples_section += "=== SEÑALES DE LEAD CALIFICADO ===\n"
                examples_section += "Señales POSITIVAS:\n"
                for señal in patrones.get('señales_positivas', [])[:5]:
                    examples_section += f"✓ {señal}\n"
                examples_section += "\nSeñales NEGATIVAS:\n"
                for señal in patrones.get('señales_negativas', [])[:5]:
                    examples_section += f"✗ {señal}\n"

            # Agregar guía de respuestas
            guia = self.conversation_examples.get('guia_respuestas', {})
            if guia:
                examples_section += f"\n=== GUÍA DE RESPUESTAS ===\n"
                examples_section += f"Primer contacto: {guia.get('primer_contacto', '')}\n"
                examples_section += f"Recopilación: {guia.get('recopilacion_info', '')}\n"
                examples_section += f"Cliente listo: {guia.get('cliente_listo', '')}\n"
                examples_section += f"Tono: {guia.get('tono_general', '')}\n"

            base_prompt += examples_section

        return base_prompt
    
    async def chat(self, message: str, conversation_history: List[Dict], phone_number: str, user_division: str = None) -> Dict:
        """
        Procesa un mensaje usando Claude y devuelve respuesta + análisis

        Args:
            message: Mensaje del usuario
            conversation_history: Historial de conversación
            phone_number: Número del usuario
            user_division: División del usuario ('techos' o 'rolados')

        Returns:
            Dict con: response, is_qualified_lead, lead_score, summary
        """
        try:
            # Construir historial de mensajes para Claude
            messages = self._build_message_history(conversation_history, message)

            # Agregar información de división al system prompt
            system_prompt = self.system_prompt
            if user_division:
                division_info = f"\n\n⚠️ IMPORTANTE: Este cliente ya seleccionó la división *{user_division.upper()}*. Enfoca tu conversación únicamente en productos/servicios de esta división."
                system_prompt = self.system_prompt + division_info

            # Llamar a Claude con herramientas para análisis
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                messages=messages,
                tools=[
                    {
                        "name": "analyze_lead",
                        "description": "Analiza si el cliente es un lead calificado y genera resumen para el vendedor",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "is_qualified_lead": {
                                    "type": "boolean",
                                    "description": "True si el cliente está listo para cotización seria y tiene suficiente información"
                                },
                                "lead_score": {
                                    "type": "integer",
                                    "description": "Puntuación del lead de 1-10 (10 = muy calificado con todos los datos)"
                                },
                                "lead_type": {
                                    "type": "string",
                                    "enum": ["cotizacion_seria", "consulta_general", "spam", "seguimiento"],
                                    "description": "Tipo de lead"
                                },
                                "division": {
                                    "type": "string",
                                    "enum": ["techos", "rolados"],
                                    "description": "División de ARCOSUM - OBLIGATORIO: 'techos' si pide arcotecho/estructura/techo, 'rolados' si pide láminas/perfiles/laminados"
                                },
                                "datos_techos": {
                                    "type": "object",
                                    "properties": {
                                        "nombre_completo": {"type": "string"},
                                        "correo": {"type": "string"},
                                        "whatsapp": {"type": "string"},
                                        "etapa_obra": {"type": "string"},
                                        "ancho_metros": {"type": "string"},
                                        "largo_metros": {"type": "string"},
                                        "altura_muro": {"type": "string"},
                                        "tipo_lamina": {"type": "string"},
                                        "franjas_luz": {"type": "string"},
                                        "timpanos": {"type": "string"},
                                        "extractores": {"type": "string"},
                                        "uso_area": {"type": "string"},
                                        "estado": {"type": "string"},
                                        "municipio": {"type": "string"},
                                        "comentarios": {"type": "string"}
                                    },
                                    "description": "Datos recopilados para cotización de techos/arcotechos"
                                },
                                "datos_rolados": {
                                    "type": "object",
                                    "properties": {
                                        "kilos": {"type": "string"},
                                        "area_m2": {"type": "string"},
                                        "largo": {"type": "string"},
                                        "ancho": {"type": "string"},
                                        "ubicacion": {"type": "string"},
                                        "calibre": {"type": "string"},
                                        "perfil": {"type": "string"},
                                        "nombre_contacto": {"type": "string"}
                                    },
                                    "description": "Datos recopilados para cotización de laminados/rolados"
                                },
                                "summary_for_seller": {
                                    "type": "string",
                                    "description": "Resumen conciso para el vendedor sobre qué necesita el cliente"
                                },
                                "next_action": {
                                    "type": "string",
                                    "description": "Acción recomendada para el vendedor"
                                },
                                "datos_completos": {
                                    "type": "boolean",
                                    "description": "True si ya se tiene toda la información necesaria para cotizar"
                                }
                            },
                            "required": ["is_qualified_lead", "lead_score", "lead_type", "summary_for_seller", "datos_completos"]
                        }
                    }
                ]
            )
            
            # Extraer respuesta y análisis
            result = self._process_claude_response(response)
            
            logger.info(f"AI response generated for {phone_number}, lead_score: {result.get('lead_score', 0)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in AI chat: {str(e)}")
            # Respuesta de fallback
            return {
                "response": "Gracias por tu mensaje. En este momento estoy teniendo dificultades técnicas. ¿Puedo pedirte que me compartas tu consulta y un asesor se comunicará contigo lo antes posible?",
                "is_qualified_lead": False,
                "lead_score": 0,
                "error": str(e)
            }
    
    def _build_message_history(self, history: List[Dict], current_message: str) -> List[Dict]:
        """Construye el historial de mensajes en formato de Claude"""
        messages = []
        
        # Agregar historial previo (últimos 10 mensajes)
        for msg in history[-10:]:
            role = "user" if msg["direction"] == "received" else "assistant"
            messages.append({
                "role": role,
                "content": msg["message_text"]
            })
        
        # Agregar mensaje actual
        messages.append({
            "role": "user",
            "content": current_message
        })
        
        return messages
    
    def _process_claude_response(self, response) -> Dict:
        """Procesa la respuesta de Claude y extrae información"""
        result = {
            "response": "",
            "is_qualified_lead": False,
            "lead_score": 0,
            "lead_type": "consulta_general",
            "division": "indefinido",
            "datos_techos": {},
            "datos_rolados": {},
            "project_info": {},  # Mantener por compatibilidad
            "summary_for_seller": "",
            "next_action": "",
            "datos_completos": False
        }

        # Extraer texto de respuesta y uso de herramientas
        for content in response.content:
            if content.type == "text":
                result["response"] = content.text
            elif content.type == "tool_use" and content.name == "analyze_lead":
                # Extraer análisis del lead
                analysis = content.input
                result.update({
                    "is_qualified_lead": analysis.get("is_qualified_lead", False),
                    "lead_score": analysis.get("lead_score", 0),
                    "lead_type": analysis.get("lead_type", "consulta_general"),
                    "division": analysis.get("division", "indefinido"),
                    "datos_techos": analysis.get("datos_techos", {}),
                    "datos_rolados": analysis.get("datos_rolados", {}),
                    "project_info": analysis.get("project_info", {}),  # Legacy
                    "summary_for_seller": analysis.get("summary_for_seller", ""),
                    "next_action": analysis.get("next_action", ""),
                    "datos_completos": analysis.get("datos_completos", False)
                })

        return result
    
    async def generate_seller_notification(self, phone_number: str, conversation_summary: Dict,
                                           conversation_history: List[Dict],
                                           chat_id: Optional[str] = None,
                                           last_message_id: Optional[str] = None) -> str:
        """
        Genera un mensaje detallado para el vendedor

        Args:
            phone_number: Número del cliente
            conversation_summary: Resumen del análisis de IA
            conversation_history: Historial completo de la conversación
            chat_id: ID del chat de WhatsApp
            last_message_id: ID del último mensaje (wamid.xxx)

        Returns:
            Mensaje formateado para el vendedor
        """
        division = conversation_summary.get("division", "indefinido").upper()
        datos_completos = conversation_summary.get("datos_completos", False)

        # Construir mensaje base
        message = f"""🔔 *NUEVO LEAD CALIFICADO*

📱 *Cliente:* {phone_number}
🆔 *Chat ID:* {chat_id or phone_number}
📨 *Message ID:* {last_message_id or 'N/A'}
⭐ *Puntuación:* {conversation_summary.get('lead_score', 0)}/10
🏢 *División:* {division}
🏷️ *Tipo:* {conversation_summary.get('lead_type', 'N/A')}
✅ *Datos Completos:* {'SÍ' if datos_completos else 'PARCIAL'}

📋 *RESUMEN:*
{conversation_summary.get('summary_for_seller', 'Sin información')}
"""

        # Agregar datos específicos según división
        if division == "TECHOS":
            datos_techos = conversation_summary.get("datos_techos", {})
            if datos_techos:
                message += "\n\n🏗️ *DATOS DEL PROYECTO (TECHOS):*\n"
                if datos_techos.get("nombre_completo"):
                    message += f"• Nombre: {datos_techos['nombre_completo']}\n"
                if datos_techos.get("correo"):
                    message += f"• Email: {datos_techos['correo']}\n"
                if datos_techos.get("whatsapp"):
                    message += f"• WhatsApp: {datos_techos['whatsapp']}\n"
                if datos_techos.get("etapa_obra"):
                    message += f"• Etapa: {datos_techos['etapa_obra']}\n"
                if datos_techos.get("ancho_metros"):
                    message += f"• Ancho: {datos_techos['ancho_metros']}m\n"
                if datos_techos.get("largo_metros"):
                    message += f"• Largo: {datos_techos['largo_metros']}m\n"
                if datos_techos.get("altura_muro"):
                    message += f"• Altura muro: {datos_techos['altura_muro']}m\n"
                if datos_techos.get("tipo_lamina"):
                    message += f"• Tipo lámina: {datos_techos['tipo_lamina']}\n"
                if datos_techos.get("franjas_luz"):
                    message += f"• Franjas luz: {datos_techos['franjas_luz']}\n"
                if datos_techos.get("timpanos"):
                    message += f"• Tímpanos: {datos_techos['timpanos']}\n"
                if datos_techos.get("extractores"):
                    message += f"• Extractores: {datos_techos['extractores']}\n"
                if datos_techos.get("uso_area"):
                    message += f"• Uso: {datos_techos['uso_area']}\n"
                if datos_techos.get("estado"):
                    message += f"• Ubicación: {datos_techos.get('municipio', '')}, {datos_techos['estado']}\n"
                if datos_techos.get("comentarios"):
                    message += f"• Comentarios: {datos_techos['comentarios']}\n"

        elif division == "ROLADOS":
            datos_rolados = conversation_summary.get("datos_rolados", {})
            if datos_rolados:
                message += "\n\n🔧 *DATOS DEL PEDIDO (ROLADOS):*\n"
                if datos_rolados.get("nombre_contacto"):
                    message += f"• Contacto: {datos_rolados['nombre_contacto']}\n"
                if datos_rolados.get("kilos"):
                    message += f"• Cantidad: {datos_rolados['kilos']} kg\n"
                if datos_rolados.get("area_m2"):
                    message += f"• Área: {datos_rolados['area_m2']} m²\n"
                if datos_rolados.get("largo"):
                    message += f"• Largo: {datos_rolados['largo']}\n"
                if datos_rolados.get("ancho"):
                    message += f"• Ancho: {datos_rolados['ancho']}\n"
                if datos_rolados.get("calibre"):
                    message += f"• Calibre: {datos_rolados['calibre']}\n"
                if datos_rolados.get("perfil"):
                    message += f"• Perfil: {datos_rolados['perfil']}\n"
                if datos_rolados.get("ubicacion"):
                    message += f"• Ubicación: {datos_rolados['ubicacion']}\n"

        # Acción recomendada
        message += f"\n\n💡 *ACCIÓN RECOMENDADA:*\n{conversation_summary.get('next_action', 'Contactar al cliente')}"

        # Agregar últimos mensajes
        message += "\n\n📝 *ÚLTIMOS MENSAJES:*"
        recent_messages = conversation_history[-6:]  # Últimos 3 intercambios
        for msg in recent_messages:
            sender = "Cliente" if msg["direction"] == "received" else "Bot"
            message += f"\n[{sender}] {msg['message_text'][:80]}..."

        message += f"\n\n⏰ *Fecha:* {conversation_history[-1]['created_at']}"
        message += f"\n💬 *Contactar:* {phone_number}"

        return message

    async def should_notify_seller(self, analysis: Dict) -> bool:
        """
        Determina si se debe notificar al vendedor

        Args:
            analysis: Resultado del análisis de IA

        Returns:
            True si se debe notificar
        """
        # MODO TESTING: Notificar en TODOS los mensajes (score >= 0)
        # Para producción: cambiar MIN_LEAD_SCORE_TO_NOTIFY a 7 en .env

        from config import Config
        min_score = Config.MIN_LEAD_SCORE_TO_NOTIFY

        is_qualified = analysis.get("is_qualified_lead", False)
        lead_score = analysis.get("lead_score", 0)
        lead_type = analysis.get("lead_type", "")

        should_notify = (
            is_qualified or
            lead_score >= min_score or
            lead_type == "cotizacion_seria"
        )

        logger.info(f"🎯 Threshold de notificación: score >= {min_score} (TESTING MODE: {min_score == 0})")

        return should_notify
    
    async def generate_quick_response(self, message_type: str) -> str:
        """
        Genera respuestas rápidas para casos comunes sin usar IA
        
        Args:
            message_type: Tipo de mensaje (greeting, thanks, goodbye, etc)
        """
        quick_responses = {
            "greeting": "¡Hola! 👋 Soy el asistente virtual de ARCOSUM. ¿En qué puedo ayudarte hoy?",
            "thanks": "¡Con gusto! Si necesitas algo más, aquí estoy. 😊",
            "goodbye": "¡Hasta pronto! Que tengas un excelente día. 👋",
            "menu": "Puedo ayudarte con:\n• Información de servicios\n• Solicitar cotización\n• Contacto\n\n¿Qué te interesa?"
        }
        
        return quick_responses.get(message_type, "")