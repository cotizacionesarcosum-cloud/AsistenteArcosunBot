import os
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

class Config:
    # WhatsApp Business API
    WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "ARCOSUM_WEBHOOK_2024")
    WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "")
    
    # Base de datos
    DATABASE_PATH = os.getenv("DATABASE_PATH", "whatsapp_bot.db")
    
    # Servidor
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    
    # Información del negocio
    BUSINESS_NAME = os.getenv("BUSINESS_NAME", "ARCOSUM")
    BUSINESS_PHONE = os.getenv("BUSINESS_PHONE", "+52 222 123 4567")
    BUSINESS_EMAIL = os.getenv("BUSINESS_EMAIL", "contacto@arcosum.com")
    BUSINESS_WEBSITE = os.getenv("BUSINESS_WEBSITE", "www.arcosum.com")
    BUSINESS_ADDRESS = os.getenv("BUSINESS_ADDRESS", "Puebla, México")
    
    # Horarios de atención
    BUSINESS_HOURS_WEEKDAY = os.getenv("BUSINESS_HOURS_WEEKDAY", "9:00 AM - 6:00 PM")
    BUSINESS_HOURS_SATURDAY = os.getenv("BUSINESS_HOURS_SATURDAY", "9:00 AM - 2:00 PM")
    BUSINESS_HOURS_SUNDAY = os.getenv("BUSINESS_HOURS_SUNDAY", "Cerrado")
    
    # Integración con Claude AI
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    USE_AI_RESPONSES = os.getenv("USE_AI_RESPONSES", "True").lower() == "true"
    AI_MODEL = os.getenv("AI_MODEL", "claude-4-haiku-20250101")
    
    # Notificaciones a vendedores - Separados por división
    # TECHOS
    SELLER_PHONE_NUMBERS_TECHOS = os.getenv("SELLER_PHONE_NUMBERS_TECHOS", "").split(",")
    SELLER_EMAILS_TECHOS = os.getenv("SELLER_EMAILS_TECHOS", "").split(",")

    # ROLADOS
    SELLER_PHONE_NUMBERS_ROLADOS = os.getenv("SELLER_PHONE_NUMBERS_ROLADOS", "").split(",")
    SELLER_EMAILS_ROLADOS = os.getenv("SELLER_EMAILS_ROLADOS", "").split(",")

    NOTIFY_ON_QUALIFIED_LEAD = os.getenv("NOTIFY_ON_QUALIFIED_LEAD", "True").lower() == "true"
    MIN_LEAD_SCORE_TO_NOTIFY = int(os.getenv("MIN_LEAD_SCORE_TO_NOTIFY", 7))

    # Plantilla de WhatsApp para vendedores
    WHATSAPP_TEMPLATE_NAME = os.getenv("WHATSAPP_TEMPLATE_NAME", "")
    WHATSAPP_TEMPLATE_LANGUAGE = os.getenv("WHATSAPP_TEMPLATE_LANGUAGE", "es_MX")
    
    # Configuración SMTP para emails
    SMTP_ENABLED = os.getenv("SMTP_ENABLED", "False").lower() == "true"
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "True").lower() == "true"
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "whatsapp_bot.log")
    
    @classmethod
    def validate(cls):
        required = [
            ("WHATSAPP_ACCESS_TOKEN", cls.WHATSAPP_ACCESS_TOKEN),
            ("WHATSAPP_PHONE_NUMBER_ID", cls.WHATSAPP_PHONE_NUMBER_ID),
            ("ANTHROPIC_API_KEY", cls.ANTHROPIC_API_KEY),
        ]
        
        missing = [name for name, value in required if not value]
        
        if missing:
            logger.warning(f"Faltan configuraciones: {', '.join(missing)}")
        
        # Verificar que al menos una división tenga vendedores configurados
        has_techos_vendors = cls.SELLER_PHONE_NUMBERS_TECHOS and cls.SELLER_PHONE_NUMBERS_TECHOS[0]
        has_rolados_vendors = cls.SELLER_PHONE_NUMBERS_ROLADOS and cls.SELLER_PHONE_NUMBERS_ROLADOS[0]

        if cls.NOTIFY_ON_QUALIFIED_LEAD and not (has_techos_vendors or has_rolados_vendors):
            logger.warning("No hay números de vendedores configurados en ninguna división")
        
        return True
    
    @classmethod
    def print_config(cls):
        print("\n" + "="*50)
        print("CONFIGURACIÓN DEL SISTEMA")
        print("="*50)
        print(f"Business Name: {cls.BUSINESS_NAME}")
        print(f"Phone: {cls.BUSINESS_PHONE}")
        print(f"Database: {cls.DATABASE_PATH}")
        print(f"Server: {cls.HOST}:{cls.PORT}")
        print(f"AI Responses: {cls.USE_AI_RESPONSES}")
        print("="*50 + "\n")