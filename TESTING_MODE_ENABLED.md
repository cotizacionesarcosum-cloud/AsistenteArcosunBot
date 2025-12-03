# ⚠️ MODO TESTING ACTIVADO ⚠️

## 🧪 Configuración Actual

El sistema está configurado en **MODO TESTING** para probar las notificaciones.

### Cambios Temporales:

1. **MIN_LEAD_SCORE_TO_NOTIFY = 0** (en `.env`)
   - Esto significa que **TODOS los mensajes** dispararán notificaciones
   - Normalmente debería ser `7` para producción

2. **Vendedores Configurados:**
   - Arcotechos: `522224234611` (recibirá notificaciones)
   - Rolados: `522221148841` (recibirá notificaciones)

3. **Emails Configurados:**
   - cotizaciones.arcosum@gmail.com
   - rolados.arcosum@gmail.com

---

## 🎯 Para Probar:

### 1. Iniciar el bot:
```bash
python start.py
```

### 2. Probar con endpoint de testing:
```bash
curl -X POST http://localhost:8000/test-notification
```

### 3. Probar con mensaje real:
Envía cualquier mensaje desde WhatsApp al bot. **TODOS los mensajes** dispararán notificación.

---

## 📊 Qué Verás en los Logs:

```
🎯 Threshold de notificación: score >= 0 (TESTING MODE: True)
🔍 Evaluación de notificación - Lead Score: X/10, ¿Notificar?: True
🚀 Activando notificación a vendedores
============================================================
🔔 NOTIFICACIÓN DE LEAD CALIFICADO ACTIVADA
Vendedores configurados (WhatsApp): 2 números
📤 Enviando notificación WhatsApp a: 522224234611
✅ WhatsApp enviado exitosamente a 522224234611
📤 Enviando notificación WhatsApp a: 522221148841
✅ WhatsApp enviado exitosamente a 522221148841
============================================================
```

---

## 🚨 IMPORTANTE: Volver a Producción

### Cuando termines las pruebas, DEBES hacer esto:

1. **Editar `.env`:**
```bash
# Cambiar de:
MIN_LEAD_SCORE_TO_NOTIFY=0

# A:
MIN_LEAD_SCORE_TO_NOTIFY=7
```

2. **Reiniciar el bot:**
```bash
# Ctrl+C para detener
python start.py
```

3. **Verificar en logs:**
Deberías ver:
```
🎯 Threshold de notificación: score >= 7 (TESTING MODE: False)
```

---

## 📞 Información de Contacto Actualizada:

### ARCOSUM TECHOS:
- Teléfono: +52 1 222 423 4611
- Email: cotizaciones.arcosum@gmail.com
- Web: www.arcosum.com
- Ubicación: Tlaxcala, México

### ARCOSUM ROLADOS:
- Teléfono: +52 222 114 8841
- Email: rolados.arcosum@gmail.com
- Web: www.arcosumrolados.com
- Ubicación: Tlaxcala, México

---

## ✅ Checklist de Testing:

- [ ] Bot inicia correctamente
- [ ] Se cargan 3 ejemplos de conversaciones
- [ ] Endpoint /test-notification funciona
- [ ] Ambos vendedores reciben notificación de prueba
- [ ] Mensaje real de WhatsApp dispara notificación
- [ ] Logs muestran "TESTING MODE: True"
- [ ] Mensaje de bienvenida muestra ambas divisiones

## 🔄 Cuando Todo Funcione:

1. Cambiar `MIN_LEAD_SCORE_TO_NOTIFY=7` en `.env`
2. Reiniciar bot
3. **ELIMINAR este archivo** (TESTING_MODE_ENABLED.md)
4. Hacer commit de cambios finales
