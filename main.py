from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from datetime import datetime
import logging
import os

# Importar módulos del sistema
from config import Config
from whatsapp_client import WhatsAppClient
from database import Database
from message_handler import MessageHandler
from ai_assistant import AIAssistant
from notification_service import NotificationService
from admin_routes import router as admin_router

# Configurar logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="WhatsApp Business Automation with AI")

# Servir archivos estáticos
if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Incluir rutas del panel de administración
app.include_router(admin_router)

# Inicializar componentes globales
db = None
whatsapp_client = None
ai_assistant = None
notification_service = None
message_handler = None


# -------------------------------
# INICIALIZACIÓN DEL SISTEMA
# -------------------------------
@app.on_event("startup")
async def startup_event():
    """Inicializa todos los componentes al arrancar el servidor"""
    global db, whatsapp_client, ai_assistant, notification_service, message_handler
    
    try:
        Config.validate()
        Config.print_config()
        
        logger.info("Inicializando base de datos...")
        db = Database(Config.DATABASE_PATH)
        
        logger.info("Inicializando cliente de WhatsApp...")
        whatsapp_client = WhatsAppClient(
            access_token=Config.WHATSAPP_ACCESS_TOKEN,
            phone_number_id=Config.WHATSAPP_PHONE_NUMBER_ID
        )
        
        logger.info("Inicializando asistente de IA...")
        ai_assistant = AIAssistant(api_key=Config.ANTHROPIC_API_KEY)
        
        logger.info("Inicializando servicio de notificaciones...")
        smtp_config = {
            "enabled": Config.SMTP_ENABLED,
            "smtp_server": Config.SMTP_SERVER,
            "smtp_port": Config.SMTP_PORT,
            "username": Config.SMTP_USERNAME,
            "password": Config.SMTP_PASSWORD,
            "from_email": Config.SMTP_FROM_EMAIL,
            "use_tls": Config.SMTP_USE_TLS
        }
        
        notification_service = NotificationService(
            whatsapp_client=whatsapp_client,
            smtp_config=smtp_config,
            seller_phones_techos=[p.strip() for p in Config.SELLER_PHONE_NUMBERS_TECHOS if p.strip()],
            seller_emails_techos=[e.strip() for e in Config.SELLER_EMAILS_TECHOS if e.strip()],
            seller_phones_rolados=[p.strip() for p in Config.SELLER_PHONE_NUMBERS_ROLADOS if p.strip()],
            seller_emails_rolados=[e.strip() for e in Config.SELLER_EMAILS_ROLADOS if e.strip()],
            template_name=Config.WHATSAPP_TEMPLATE_NAME,
            template_language=Config.WHATSAPP_TEMPLATE_LANGUAGE
        )
        
        logger.info("Inicializando manejador de mensajes...")
        message_handler = MessageHandler(
            whatsapp_client=whatsapp_client,
            database=db,
            ai_assistant=ai_assistant,
            notification_service=notification_service
        )
        
        logger.info("✅ Sistema inicializado correctamente!")
        
    except Exception as e:
        logger.error(f"❌ Error durante inicialización: {str(e)}")
        raise


# -------------------------------
# PANEL
# -------------------------------
@app.get("/", response_class=HTMLResponse)
async def root():
    """Página principal - Panel de administración"""
    try:
        with open("admin_panel.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Error: admin_panel.html no encontrado</h1>", status_code=500)

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel():
    """Panel de administración"""
    try:
        with open("admin_panel.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Error: admin_panel.html no encontrado</h1>", status_code=500)



# -------------------------------
# WEBHOOK DE VERIFICACIÓN (CORREGIDO)
# -------------------------------
@app.get("/webhook")
async def verify_webhook(request: Request):
    """Verificación del webhook de WhatsApp Business API"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    logger.info(f"Webhook verification request - Mode: {mode}")
    logger.info(f"Token recibido: {token}")
    logger.info(f"Challenge recibido: {challenge}")

    # Si alguien visita /webhook sin parámetros (tu navegador)
    if mode is None and token is None and challenge is None:
        return {"status": "ok", "message": "WhatsApp webhook endpoint"}

    # Validación oficial para Meta
    if mode == "subscribe" and token == Config.WHATSAPP_VERIFY_TOKEN and challenge:
        logger.info("✅ Webhook verificado exitosamente!")
        # Responder challenge como TEXTO PLANO (Meta lo requiere)
        return PlainTextResponse(content=challenge, status_code=200)

    logger.warning("❌ Verificación de webhook fallida!")
    raise HTTPException(status_code=403, detail="Verification token mismatch")



# -------------------------------
# WEBHOOK PARA RECIBIR MENSAJES
# -------------------------------
@app.post("/webhook")
async def receive_webhook(request: Request):
    """Recibe mensajes entrantes de WhatsApp y los procesa con IA"""
    try:
        body = await request.json()
        logger.info(f"Webhook recibido: {body}")
        
        if body.get("object") == "whatsapp_business_account":
            entries = body.get("entry", [])
            
            for entry in entries:
                changes = entry.get("changes", [])
                
                for change in changes:
                    value = change.get("value", {})
                    
                    if "messages" in value:
                        messages = value["messages"]
                        
                        for message in messages:
                            from_number = message.get("from")
                            message_id = message.get("id")
                            message_type = message.get("type")
                            
                            if message_type == "text":
                                text_body = message.get("text", {}).get("body", "")
                                logger.info(f"📨 Mensaje de texto de {from_number}: {text_body}")

                                await message_handler.process_message(
                                    from_number=from_number,
                                    message_text=text_body,
                                    message_id=message_id
                                )

                            elif message_type == "image":
                                image_data = message.get("image", {})
                                image_id = image_data.get("id")
                                caption = image_data.get("caption", "")
                                logger.info(f"🖼️ Imagen recibida de {from_number}")

                                await message_handler.process_message(
                                    from_number=from_number,
                                    message_text=caption or "📸 Imagen enviada",
                                    message_id=message_id,
                                    media_url=image_id,
                                    media_type="image"
                                )

                            elif message_type == "document":
                                doc_data = message.get("document", {})
                                doc_id = doc_data.get("id")
                                filename = doc_data.get("filename", "documento")
                                caption = doc_data.get("caption", "")
                                logger.info(f"📄 Documento recibido de {from_number}: {filename}")

                                await message_handler.process_message(
                                    from_number=from_number,
                                    message_text=caption or f"📄 {filename}",
                                    message_id=message_id,
                                    media_url=doc_id,
                                    media_type=f"document ({filename})"
                                )

                            elif message_type == "interactive":
                                interactive = message.get("interactive", {})
                                response_text = ""

                                if interactive.get("type") == "button_reply":
                                    response_text = interactive.get("button_reply", {}).get("title", "")
                                elif interactive.get("type") == "list_reply":
                                    response_text = interactive.get("list_reply", {}).get("title", "")

                                if response_text:
                                    await message_handler.process_message(
                                        from_number=from_number,
                                        message_text=response_text,
                                        message_id=message_id
                                    )

                            else:
                                logger.info(f"ℹ️ Tipo de mensaje: {message_type}")
                    
                    if "statuses" in value:
                        statuses = value["statuses"]
                        for status in statuses:
                            logger.debug(f"Estado de mensaje: {status}")
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"❌ Error procesando webhook: {str(e)}")
        return {"status": "error", "message": str(e)}



# -------------------------------
# ESTADO DEL SERVICIO
# -------------------------------
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "ai_enabled": Config.USE_AI_RESPONSES,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/stats")
async def get_statistics():
    if db:
        stats = db.get_statistics()
        return {
            "status": "success",
            "data": stats
        }
    return {"status": "error", "message": "Database not initialized"}

@app.get("/ai-prompt")
async def get_ai_prompt():
    """Muestra el prompt completo que está usando la IA (incluyendo ejemplos)"""
    if ai_assistant:
        return {
            "status": "success",
            "model": ai_assistant.model,
            "system_prompt": ai_assistant.system_prompt,
            "examples_loaded": len(ai_assistant.conversation_examples.get('ejemplos_cotizaciones_exitosas', [])),
            "prompt_length": len(ai_assistant.system_prompt)
        }
    return {"status": "error", "message": "AI Assistant not initialized"}



# -------------------------------
# TEST DE ENVÍO DE MENSAJES
# -------------------------------
@app.post("/test-message")
async def test_message(phone: str, message: str):
    try:
        result = whatsapp_client.send_text_message(phone, message)
        return {
            "status": "success",
            "message": "Mensaje enviado",
            "result": result
        }
    except Exception as e:
        logger.error(f"Error enviando mensaje de prueba: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------
# TEST DE NOTIFICACIONES A VENDEDORES
# -------------------------------
@app.post("/test-notification")
async def test_notification(lead_score: int = 9):
    """
    Endpoint para probar el sistema de notificaciones a vendedores

    Args:
        lead_score: Puntuación del lead (1-10) para simular
    """
    try:
        # Crear datos de prueba de un lead calificado
        test_lead_data = {
            "phone_number": "5212221234567",
            "lead_score": lead_score,
            "lead_type": "cotizacion_seria",
            "project_info": {
                "tipo_proyecto": "Arcotecho industrial",
                "ubicacion": "Puebla, México",
                "dimension_aproximada": "20x40 metros (800m²)",
                "tiempo_estimado": "2-3 meses",
                "presupuesto_mencionado": "Por definir"
            },
            "summary_for_seller": "Cliente interesado en arcotecho para bodega nueva. Proyecto bien definido con dimensiones claras.",
            "next_action": "Contactar en 24hrs para agendar visita técnica sin costo",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # Generar mensaje de notificación
        notification_message = f"""🔔 *NUEVO LEAD CALIFICADO (TEST)*

📱 *Cliente:* {test_lead_data['phone_number']}
⭐ *Puntuación:* {test_lead_data['lead_score']}/10
🏷️ *Tipo:* {test_lead_data['lead_type']}

📋 *RESUMEN DEL PROYECTO:*
{test_lead_data['summary_for_seller']}

🔧 *DETALLES:*
• Tipo: {test_lead_data['project_info']['tipo_proyecto']}
• Ubicación: {test_lead_data['project_info']['ubicacion']}
• Dimensión: {test_lead_data['project_info']['dimension_aproximada']}
• Timeline: {test_lead_data['project_info']['tiempo_estimado']}

💡 *ACCIÓN RECOMENDADA:*
{test_lead_data['next_action']}

⏰ *Fecha:* {test_lead_data['timestamp']}

⚠️ *ESTO ES UNA PRUEBA DEL SISTEMA DE NOTIFICACIONES*"""

        logger.info("="*60)
        logger.info("🧪 INICIANDO PRUEBA DE NOTIFICACIONES")
        logger.info("="*60)

        # Enviar notificación
        await notification_service.notify_qualified_lead(test_lead_data, notification_message)

        return {
            "status": "success",
            "message": "Notificación de prueba enviada",
            "lead_data": test_lead_data,
            "notification_sent_to": {
                "whatsapp_phones": notification_service.seller_phones,
                "emails": notification_service.seller_emails
            }
        }

    except Exception as e:
        logger.error(f"Error en prueba de notificación: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



# -------------------------------
# EJECUCIÓN LOCAL
# -------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host=Config.HOST, 
        port=Config.PORT, 
        reload=Config.DEBUG
    )
