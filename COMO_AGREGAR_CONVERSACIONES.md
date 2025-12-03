# 📝 Cómo Agregar Conversaciones de Ejemplo

## 🎯 Para Qué Sirve

Las conversaciones de ejemplo entrenan al bot para:
- Detectar mejor los leads calificados
- Responder de forma más natural
- Asignar puntuaciones correctas

---

## ✅ **Método 1: Editar conversation_examples.json Directamente**

### Paso 1: Abre el archivo

```bash
# Edita este archivo:
conversation_examples.json
```

### Paso 2: Agrega una nueva conversación

Busca la sección `"ejemplos_cotizaciones_exitosas"` y agrega:

```json
{
  "id": 6,
  "tipo": "nombre_descriptivo",
  "conversacion": [
    {
      "cliente": "Primer mensaje del cliente",
      "bot": "Respuesta ideal del bot"
    },
    {
      "cliente": "Segundo mensaje del cliente",
      "bot": "Otra respuesta del bot"
    }
  ],
  "lead_score": 9,
  "motivo_calificacion": "Por qué este es un buen lead"
}
```

### Ejemplo Real:

```json
{
  "id": 6,
  "tipo": "estructura_bodega_urgente",
  "conversacion": [
    {
      "cliente": "Buenos días, necesito estructura metálica urgente",
      "bot": "¡Hola! Con gusto te ayudo. ¿Para qué tipo de proyecto y qué dimensiones necesitas?"
    },
    {
      "cliente": "Es para una bodega de 15x30 metros en Puebla, necesito para la próxima semana",
      "bot": "Perfecto, 450m² en Puebla con entrega urgente. ¿Ya tienes los planos o diseño?"
    },
    {
      "cliente": "Sí tengo planos, te los puedo enviar",
      "bot": "Excelente! Envíamelos por favor. Con los planos puedo darte cotización formal en 24hrs. ¿Cuál es tu nombre y empresa?"
    }
  ],
  "lead_score": 10,
  "motivo_calificacion": "Lead caliente: proyecto definido, urgente, tiene planos, ubicación clara"
}
```

---

## 📄 **Método 2: Pegar Texto Plano (Más Fácil)**

### Crea un archivo de texto simple

Crea: `nueva_conversacion.txt`

```
TIPO: estructura_bodega_urgente
SCORE: 10
MOTIVO: Lead caliente con proyecto definido

CLIENTE: Buenos días, necesito estructura metálica urgente
BOT: ¡Hola! Con gusto te ayudo. ¿Para qué tipo de proyecto y qué dimensiones necesitas?

CLIENTE: Es para una bodega de 15x30 metros en Puebla, necesito para la próxima semana
BOT: Perfecto, 450m² en Puebla con entrega urgente. ¿Ya tienes los planos o diseño?

CLIENTE: Sí tengo planos, te los puedo enviar
BOT: Excelente! Envíamelos por favor. Con los planos puedo darte cotización formal en 24hrs. ¿Cuál es tu nombre y empresa?
```

**Luego yo te ayudo a convertirlo a JSON** o puedes usar el script que te voy a crear.

---

## 🔄 **Método 3: Usar el Script Automático** (Lo Mejor)

Voy a crear un script que convierte texto plano a JSON automáticamente.

---

## 📊 **Guía de Puntuaciones**

| Score | Tipo de Lead | Ejemplo |
|-------|-------------|---------|
| 1-3 | Consulta general | "¿Horario?", "¿Dónde están?" |
| 4-6 | Interés tibio | "Quiero info", "Para dentro de 6 meses" |
| 7-8 | Lead bueno | Dimensiones + ubicación + timeline |
| 9-10 | Lead caliente | Todo lo anterior + planos/empresa/urgente |

---

## ✨ **Tips para Crear Buenos Ejemplos**

1. **Usa conversaciones REALES** que hayas tenido
2. **Incluye el contexto completo** (no solo un mensaje)
3. **Marca claramente** qué hace que sea un buen/mal lead
4. **Varía los escenarios**:
   - Arcotechos
   - Estructuras metálicas
   - Laminados
   - Urgentes vs planeados
   - Con/sin planos

---

## 🚀 **Después de Agregar Ejemplos**

1. Guarda el archivo `conversation_examples.json`
2. Haz commit: `git add conversation_examples.json && git commit -m "Agregar nuevos ejemplos"`
3. Push: `git push`
4. Render se actualiza automáticamente
5. El bot usa los nuevos ejemplos inmediatamente

---

## 📝 **Template Vacío para Copiar**

```json
{
  "id": X,
  "tipo": "nombre_descriptivo",
  "conversacion": [
    {
      "cliente": "",
      "bot": ""
    }
  ],
  "lead_score": 0,
  "motivo_calificacion": ""
}
```

---

## ❓ **Preguntas Frecuentes**

**Q: ¿Cuántos ejemplos puedo agregar?**
A: Los que quieras, pero el bot usa los primeros 3 más relevantes.

**Q: ¿Puedo agregar ejemplos de leads NO calificados?**
A: Sí! Agrégalos en la sección `"ejemplos_consultas_generales"` con score 1-3.

**Q: ¿Los cambios se aplican inmediatamente?**
A: Sí, cuando Render se actualice (1-2 minutos después del push).

---

**Última actualización**: 28/11/2025
