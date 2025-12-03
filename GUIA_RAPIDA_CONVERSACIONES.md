# 🚀 Guía Rápida: Agregar Conversaciones

## 3 Formas de Hacerlo

---

## ✅ **Opción 1: Texto Plano + Script** (MÁS FÁCIL)

### Paso 1: Crea un archivo .txt

Crea `mi_conversacion.txt`:

```
TIPO: nombre_del_tipo
SCORE: 9
MOTIVO: Por qué es un buen lead

CLIENTE: Primer mensaje del cliente
BOT: Respuesta del bot

CLIENTE: Segundo mensaje
BOT: Otra respuesta
```

### Paso 2: Ejecuta el script

```bash
python agregar_conversacion.py mi_conversacion.txt
```

### Resultado:
```
✅ Conversación agregada exitosamente!
   ID: 4
   Sección: ejemplos_cotizaciones_exitosas
   Score: 9/10
   Tipo: nombre_del_tipo
```

---

## 📝 **Opción 2: Modo Interactivo**

```bash
python agregar_conversacion.py
```

El script te preguntará paso por paso:
1. Tipo de conversación
2. Score (1-10)
3. Motivo
4. Cada mensaje (CLIENTE: ... o BOT: ...)
5. Escribe `FIN` cuando termines

---

## ⚡ **Opción 3: Editar JSON Directamente**

Abre `conversation_examples.json` y agrega en la sección correcta:

```json
{
  "id": 6,
  "tipo": "tu_tipo",
  "conversacion": [
    {"cliente": "mensaje"},
    {"bot": "respuesta"}
  ],
  "lead_score": 9,
  "motivo_calificacion": "explicación"
}
```

---

## 📊 **Ejemplo Completo (Copia y Pega)**

Crea `nueva.txt`:

```
TIPO: arcotecho_urgente
SCORE: 10
MOTIVO: Lead caliente con urgencia y presupuesto

CLIENTE: Necesito arcotecho de 30x50m urgente
BOT: ¡Hola! ¿Para cuándo necesitas el proyecto?

CLIENTE: Para dentro de 1 mes en Puebla
BOT: Perfecto. ¿Tienes presupuesto estimado o diseño?

CLIENTE: Presupuesto hasta 800mil pesos
BOT: Excelente. Un asesor te contactará en 2 horas para agendar visita técnica sin costo.
```

Luego:
```bash
python agregar_conversacion.py nueva.txt
```

---

## 🔄 **Después de Agregar**

```bash
# Ver los cambios
git status

# Hacer commit
git add conversation_examples.json
git commit -m "Agregar nuevos ejemplos de conversaciones"

# Subir a Render
git push

# Render se actualiza automáticamente en 1-2 minutos
```

---

## 📖 **Guía de Scores**

- **1-3**: Consultas generales ("horario", "ubicación")
- **4-6**: Interés tibio (info sin compromiso)
- **7-8**: Lead bueno (proyecto + timeline)
- **9-10**: Lead caliente (todo lo anterior + urgencia/presupuesto)

---

## 💡 **Tips**

1. ✅ **Usa conversaciones REALES**
2. ✅ **Incluye 3-5 mensajes** por conversación
3. ✅ **Varía los tipos** (arcotechos, estructuras, laminados)
4. ✅ **Marca bien el score** según qué tan calificado está
5. ✅ **Explica el motivo** del score

---

## ❓ **Ayuda**

```bash
# Ver ejemplo incluido
cat ejemplo_conversacion.txt

# Probarlo
python agregar_conversacion.py ejemplo_conversacion.txt
```

---

**¿Dudas?** Lee `COMO_AGREGAR_CONVERSACIONES.md` para más detalles.
