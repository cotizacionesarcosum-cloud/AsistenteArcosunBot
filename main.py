from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from datetime import datetime
import logging
import os
import sys

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
        # Configuración simplificada para notificación (usando los teléfonos del .env)
        notification_service = NotificationService(
            whatsapp_client=whatsapp_client,
            seller_phones_techos=Config.SELLER_PHONE_NUMBERS_TECHOS,
            seller_emails_techos=Config.SELLER_EMAILS_TECHOS,
            seller_phones_rolados=Config.SELLER_PHONE_NUMBERS_ROLADOS,
            seller_emails_rolados=Config.SELLER_EMAILS_ROLADOS,
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
        # No matamos el proceso para permitir depuración, pero logueamos crítico
        pass


# -------------------------------
# PANEL DE ADMINISTRACIÓN
# -------------------------------
@app.get("/", response_class=HTMLResponse)
async def root():
    """Página principal"""
    try:
        with open("admin_panel.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Panel no encontrado</h1>", status_code=404)


# -------------------------------
# WEBHOOK DE VERIFICACIÓN
# -------------------------------
@app.get("/webhook")
async def verify_webhook(request: Request):
    """Verificación del webhook de WhatsApp Business API"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == Config.WHATSAPP_VERIFY_TOKEN:
            logger.info("✅ Webhook verificado exitosamente!")
            return PlainTextResponse(content=challenge, status_code=200)
        else:
            logger.warning("❌ Fallo en verificación de webhook")
            raise HTTPException(status_code=403, detail="Verification failed")
            
    return {"status": "ok", "message": "Webhook endpoint ready"}


# -------------------------------
# WEBHOOK PARA RECIBIR MENSAJES (CORREGIDO PARA BOTONES)
# -------------------------------
@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """Recibe mensajes entrantes de WhatsApp"""
    try:
        body = await request.json()
        
        # Verificar que es un mensaje de WhatsApp
        if body.get("object") != "whatsapp_business_account":
            return JSONResponse(content={"status": "ignored"}, status_code=200)

        entry = body.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        
        if "messages" in value:
            message = value["messages"][0]
            
            # Datos básicos
            from_number = message["from"]
            message_id = message["id"]
            message_type = message["type"]
            
            # Variables para extraer contenido
            message_text = ""
            media_url = None
            media_type = None
            
            # 1. Mensajes de Texto
            if message_type == "text":
                message_text = message["text"]["body"]
                
            # 2. Mensajes Interactivos (Botones y Listas) - CRÍTICO PARA EL NUEVO FLUJO
            elif message_type == "interactive":
                interactive = message["interactive"]
                if interactive["type"] == "button_reply":
                    # Extraemos el título para mostrarlo en logs, pero el ID va en el objeto raw
                    message_text = interactive["button_reply"]["title"]
                elif interactive["type"] == "list_reply":
                    message_text = interactive["list_reply"]["title"]
            
            # 3. Multimedia
            elif message_type in ["image", "document", "audio"]:
                media_type = message_type
                # Aquí normalmente se procesaría la descarga usando el ID
                if message_type == "image":
                    message_text = message["image"].get("caption", "[IMAGEN]")
                    media_url = message["image"].get("id") # Guardamos ID como referencia
                elif message_type == "document":
                    message_text = message["document"].get("caption", "[DOCUMENTO]")
                    media_url = message["document"].get("id")

            logger.info(f"📨 Mensaje recibido de {from_number} (Tipo: {message_type}): {message_text}")

            # Usamos BackgroundTasks para no bloquear el webhook (respuesta rápida a Meta)
            background_tasks.add_task(
                message_handler.process_message,
                from_number=from_number,
                message_text=message_text,
                message_id=message_id,
                media_url=media_url,
                media_type=media_type,
                message_raw=message  # <--- ESTO ES LO QUE FALTABA: Pasamos el objeto completo
            )
            
        return JSONResponse(content={"status": "received"}, status_code=200)

    except Exception as e:
        logger.error(f"❌ Error procesando webhook: {str(e)}")
        # Siempre responder 200 a Meta para evitar reintentos infinitos
        return JSONResponse(content={"status": "error"}, status_code=200)


# -------------------------------
# ENDPOINTS DE ESTADO Y TEST
# -------------------------------
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/test-message")
async def test_message(phone: str, message: str, background_tasks: BackgroundTasks):
    """Envía un mensaje de prueba (simulado) al sistema"""
    try:
        # Simulamos un mensaje de texto simple llegando al bot
        background_tasks.add_task(
            message_handler.process_message,
            from_number=phone,
            message_text=message,
            message_id=f"test_{datetime.now().timestamp()}",
            message_raw={"type": "text"}
        )
        return {"status": "processing", "message": "Mensaje encolado para procesamiento"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)