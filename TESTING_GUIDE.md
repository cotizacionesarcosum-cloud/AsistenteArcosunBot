# Guía de Testing y Mejoras del Bot

## 🎯 Nuevas Funcionalidades Implementadas

### 1. **Base de Datos de Ejemplos de Conversaciones**

Hemos creado un sistema de "entrenamiento" para el bot usando ejemplos reales de conversaciones exitosas.

**Archivo:** `conversation_examples.json`

Este archivo contiene:
- ✅ Ejemplos de cotizaciones exitosas (leads calificados)
- ✅ Ejemplos de consultas generales (leads no calificados)
- ✅ Patrones para detectar leads calificados
- ✅ Guía de respuestas para el bot

**Cómo funciona:**
- El bot carga estos ejemplos al iniciar
- Los incluye en el prompt del sistema de Claude
- Claude aprende de estos patrones para calificar mejor los leads

### 2. **Logging Detallado de Notificaciones**

Ahora puedes rastrear exactamente qué pasa cuando el bot detecta un lead calificado.

**En los logs verás:**
```
🔍 Evaluación de notificación - Lead Score: 9/10, Calificado: True, Tipo: cotizacion_seria, ¿Notificar?: True
🚀 Activando notificación a vendedores para 5212221234567
============================================================
🔔 NOTIFICACIÓN DE LEAD CALIFICADO ACTIVADA
Cliente: 5212221234567
Lead Score: 9/10
Tipo: cotizacion_seria
Vendedores configurados (WhatsApp): 1 números
Vendedores configurados (Email): 0 emails
============================================================
📤 Enviando notificación WhatsApp a: 522221148841
✅ WhatsApp enviado exitosamente a 522221148841
✅ Notificación completada - WhatsApp: True, Email: False
============================================================
```

### 3. **Endpoints de Testing**

#### **A) Probar Notificaciones: `POST /test-notification`**

Simula un lead calificado y envía notificación a vendedores.

```bash
# Prueba básica (lead score 9)
curl -X POST "http://localhost:8000/test-notification"

# Prueba con score personalizado
curl -X POST "http://localhost:8000/test-notification?lead_score=10"
```

**Lo que hace:**
- Crea datos de prueba de un lead calificado
- Envía notificación por WhatsApp a los vendedores configurados
- Registra todo en los logs
- Te devuelve confirmación de a quién se envió

#### **B) Ver Prompt de IA: `GET /ai-prompt`**

Verifica qué ejemplos está usando el bot.

```bash
curl http://localhost:8000/ai-prompt
```

**Respuesta:**
```json
{
  "status": "success",
  "model": "claude-3-5-haiku-20241022",
  "system_prompt": "...[todo el prompt incluyendo ejemplos]...",
  "examples_loaded": 3,
  "prompt_length": 2500
}
```

## 🧪 Cómo Probar el Sistema

### **Paso 1: Verificar Configuración**

Asegúrate de que en `.env` tengas:
```bash
SELLER_PHONE_NUMBERS=522221148841  # Tu número (debe empezar con código país)
NOTIFY_ON_QUALIFIED_LEAD=True
MIN_LEAD_SCORE_TO_NOTIFY=7
```

### **Paso 2: Iniciar el Servidor**

```bash
python start.py
```

Verás en los logs:
```
INFO - Loaded 3 conversation examples
```

Esto confirma que se cargaron los ejemplos.

### **Paso 3: Probar Notificaciones**

Desde otra terminal:

```bash
# Enviar notificación de prueba
curl -X POST http://localhost:8000/test-notification
```

**Deberías recibir:**
- ✅ Un mensaje de WhatsApp en tu número configurado
- ✅ Logs detallados en la consola
- ✅ Respuesta JSON confirmando el envío

### **Paso 4: Probar con Mensaje Real**

Envía un mensaje desde WhatsApp simulando un cliente calificado:

```
"Hola, necesito un arcotecho de 30x50 metros para una bodega en Puebla. Para dentro de 2 meses."
```

**El bot debería:**
1. Responder al cliente con preguntas calificadoras
2. Detectar que es un lead calificado (score alto)
3. Enviarte una notificación automáticamente

**Revisa los logs:**
```bash
tail -f whatsapp_bot.log
```

Busca líneas como:
- `🔍 Evaluación de notificación`
- `🚀 Activando notificación`
- `📤 Enviando notificación WhatsApp`

## 📊 Verificar si las Notificaciones Funcionan

### **Escenario 1: Lead Calificado (Score ≥ 7)**

**Mensaje del cliente:**
```
"Necesito cotización para estructura metálica de 20x30m en Cholula,
tengo planos y es para dentro de 1 mes"
```

**Resultado esperado:**
- Lead Score: 8-10
- ✅ SE ENVÍA notificación al vendedor
- Log: `¿Notificar?: True`

### **Escenario 2: Consulta General (Score < 7)**

**Mensaje del cliente:**
```
"Qué horario tienen?"
```

**Resultado esperado:**
- Lead Score: 1-2
- ❌ NO se envía notificación
- Log: `¿Notificar?: False`

## 🔧 Agregar Más Ejemplos de Conversaciones

Edita `conversation_examples.json` y agrega nuevos ejemplos en la sección:

```json
"ejemplos_cotizaciones_exitosas": [
  {
    "id": 4,
    "tipo": "tu_nuevo_tipo",
    "conversacion": [
      {
        "cliente": "Mensaje del cliente",
        "bot": "Respuesta ideal del bot"
      }
    ],
    "lead_score": 9,
    "motivo_calificacion": "Por qué es un buen lead"
  }
]
```

**Reinicia el servidor** para que cargue los nuevos ejemplos.

## 📈 Monitoreo en Tiempo Real

### Ver logs en vivo:
```bash
tail -f whatsapp_bot.log | grep -E "🔔|🔍|📤|✅|❌"
```

Esto muestra solo las líneas relevantes de notificaciones.

### Verificar estadísticas:
```bash
curl http://localhost:8000/stats
```

## ❓ Troubleshooting

### **Problema: No se envían notificaciones**

**Verifica:**
1. ¿Está configurado `SELLER_PHONE_NUMBERS` en `.env`?
   ```bash
   echo $SELLER_PHONE_NUMBERS
   ```

2. ¿El número tiene formato correcto? (código país + número sin +)
   - ✅ Correcto: `522221148841`
   - ❌ Incorrecto: `+52 222 114 8841` o `2221148841`

3. Revisa los logs:
   ```bash
   grep "Vendedores configurados" whatsapp_bot.log
   ```

### **Problema: Ejemplos no se cargan**

**Verifica:**
1. ¿Existe el archivo?
   ```bash
   ls -la conversation_examples.json
   ```

2. ¿Es JSON válido?
   ```bash
   python -m json.tool conversation_examples.json
   ```

3. Busca en logs:
   ```bash
   grep "conversation examples" whatsapp_bot.log
   ```

### **Problema: Score siempre bajo**

Los ejemplos ayudan al AI a detectar mejor, pero verifica:
- ¿El mensaje tiene señales positivas? (dimensiones, timeline, ubicación)
- ¿Se están enviando en el contexto de una conversación o solo un mensaje aislado?

Prueba con el endpoint de IA:
```bash
curl http://localhost:8000/ai-prompt | jq '.examples_loaded'
```

Debería retornar `3` o más.

## 🎓 Entender el Sistema de Puntuación

El AI asigna scores basándose en:

**Score 8-10 (Lead Caliente):**
- ✅ Dimensiones específicas
- ✅ Timeline definido (< 3 meses)
- ✅ Ubicación clara
- ✅ Menciona empresa/negocio
- ✅ Pide cotización formal

**Score 5-7 (Lead Tibio):**
- ⚠️ Interés real pero sin urgencia
- ⚠️ Timeline > 3 meses
- ⚠️ Información parcial

**Score 1-4 (Lead Frío):**
- ❌ Solo preguntas generales
- ❌ Sin proyecto definido
- ❌ No responde a calificación

## 📞 Soporte

Si necesitas ayuda, revisa:
1. `whatsapp_bot.log` - Logs completos
2. `/health` - Estado del sistema
3. `/stats` - Estadísticas de uso
4. `/ai-prompt` - Configuración de IA
