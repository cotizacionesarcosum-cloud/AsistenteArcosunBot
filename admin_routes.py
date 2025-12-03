from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import json
import os
from datetime import datetime, timedelta
from database import Database

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Modelos Pydantic
class WhatsAppConfig(BaseModel):
    access_token: str
    phone_number_id: str
    business_account_id: Optional[str] = None
    verify_token: str

class AIConfig(BaseModel):
    api_key: str
    model: str = "claude-3-5-haiku-20241022"
    enabled: bool = True
    min_lead_score: int = 7

class BusinessConfig(BaseModel):
    name: str
    phone: str
    email: str
    website: Optional[str] = None
    hours_weekday: Optional[str] = None
    hours_saturday: Optional[str] = None

class SystemPromptConfig(BaseModel):
    system_prompt: str

class SellerCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    priority: int = 5
    active: bool = True

# Ruta al archivo de configuración JSON
CONFIG_FILE = "config.json"

def load_config_file():
    """Carga la configuración desde el archivo JSON"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "whatsapp": {},
        "ai": {},
        "business": {},
        "sellers": []
    }

def save_config_file(config):
    """Guarda la configuración en el archivo JSON"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

# ============= ENDPOINTS DE CONFIGURACIÓN =============

@router.get("/config")
async def get_configuration():
    """Obtiene toda la configuración"""
    return load_config_file()

@router.post("/config/whatsapp")
async def save_whatsapp_config(config: WhatsAppConfig):
    """Guarda configuración de WhatsApp"""
    full_config = load_config_file()
    full_config["whatsapp"] = config.dict()
    save_config_file(full_config)
    
    # Actualizar variables de entorno
    update_env_file("WHATSAPP_ACCESS_TOKEN", config.access_token)
    update_env_file("WHATSAPP_PHONE_NUMBER_ID", config.phone_number_id)
    update_env_file("WHATSAPP_VERIFY_TOKEN", config.verify_token)
    if config.business_account_id:
        update_env_file("WHATSAPP_BUSINESS_ACCOUNT_ID", config.business_account_id)
    
    return {"status": "success", "message": "Configuración de WhatsApp guardada"}

@router.post("/config/ai")
async def save_ai_config(config: AIConfig):
    """Guarda configuración de IA"""
    full_config = load_config_file()
    full_config["ai"] = config.dict()
    save_config_file(full_config)
    
    # Actualizar variables de entorno
    update_env_file("ANTHROPIC_API_KEY", config.api_key)
    update_env_file("AI_MODEL", config.model)
    update_env_file("USE_AI_RESPONSES", str(config.enabled))
    update_env_file("MIN_LEAD_SCORE_TO_NOTIFY", str(config.min_lead_score))
    
    return {"status": "success", "message": "Configuración de IA guardada"}

@router.post("/config/business")
async def save_business_config(config: BusinessConfig):
    """Guarda información del negocio"""
    full_config = load_config_file()
    full_config["business"] = config.dict()
    save_config_file(full_config)
    
    # Actualizar variables de entorno
    update_env_file("BUSINESS_NAME", config.name)
    update_env_file("BUSINESS_PHONE", config.phone)
    update_env_file("BUSINESS_EMAIL", config.email)
    if config.website:
        update_env_file("BUSINESS_WEBSITE", config.website)
    if config.hours_weekday:
        update_env_file("BUSINESS_HOURS_WEEKDAY", config.hours_weekday)
    if config.hours_saturday:
        update_env_file("BUSINESS_HOURS_SATURDAY", config.hours_saturday)
    
    return {"status": "success", "message": "Información del negocio guardada"}

@router.post("/config/prompt")
async def save_system_prompt(config: SystemPromptConfig):
    """Guarda el system prompt personalizado"""
    full_config = load_config_file()
    if "ai" not in full_config:
        full_config["ai"] = {}
    full_config["ai"]["system_prompt"] = config.system_prompt
    save_config_file(full_config)
    
    return {"status": "success", "message": "System prompt guardado"}

# ============= GESTIÓN DE VENDEDORES =============

@router.get("/sellers")
async def get_sellers():
    """Obtiene lista de vendedores"""
    config = load_config_file()
    return config.get("sellers", [])

@router.post("/sellers")
async def create_seller(seller: SellerCreate):
    """Crea un nuevo vendedor"""
    config = load_config_file()
    
    if "sellers" not in config:
        config["sellers"] = []
    
    # Generar ID único
    seller_id = max([s.get("id", 0) for s in config["sellers"]], default=0) + 1
    
    seller_data = seller.dict()
    seller_data["id"] = seller_id
    seller_data["created_at"] = datetime.now().isoformat()
    
    config["sellers"].append(seller_data)
    save_config_file(config)
    
    # Actualizar variable de entorno con lista de teléfonos
    update_seller_phones(config["sellers"])
    
    return {"status": "success", "seller": seller_data}

@router.put("/sellers/{seller_id}")
async def update_seller(seller_id: int, seller: SellerCreate):
    """Actualiza un vendedor existente"""
    config = load_config_file()
    
    sellers = config.get("sellers", [])
    seller_index = next((i for i, s in enumerate(sellers) if s["id"] == seller_id), None)
    
    if seller_index is None:
        raise HTTPException(status_code=404, detail="Vendedor no encontrado")
    
    sellers[seller_index].update(seller.dict())
    sellers[seller_index]["updated_at"] = datetime.now().isoformat()
    
    config["sellers"] = sellers
    save_config_file(config)
    
    update_seller_phones(sellers)
    
    return {"status": "success", "seller": sellers[seller_index]}

@router.delete("/sellers/{seller_id}")
async def delete_seller(seller_id: int):
    """Elimina un vendedor"""
    config = load_config_file()
    
    sellers = config.get("sellers", [])
    config["sellers"] = [s for s in sellers if s["id"] != seller_id]
    
    save_config_file(config)
    update_seller_phones(config["sellers"])
    
    return {"status": "success", "message": "Vendedor eliminado"}

# ============= ESTADÍSTICAS =============

@router.get("/stats")
async def get_statistics():
    """Obtiene estadísticas del sistema"""
    try:
        # Si no hay db, crear instancia
        if db is None:
            from config import Config
            db = Database(Config.DATABASE_PATH)
        
        # Obtener estadísticas básicas
        stats = db.get_statistics()
        
        # Mensajes de hoy
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) as count 
            FROM messages 
            WHERE DATE(created_at) = DATE('now')
        ''')
        messages_today = cursor.fetchone()['count']
        
        # Leads calificados
        cursor.execute('''
            SELECT COUNT(*) as count 
            FROM lead_analysis 
            WHERE is_qualified = 1
        ''')
        qualified_leads = cursor.fetchone()['count']
        
        conn.close()
        
        return {
            "status": "online",
            "total_users": stats.get("total_users", 0),
            "messages_today": messages_today,
            "qualified_leads": qualified_leads,
            "pending_quotes": stats.get("pending_quotes", 0)
        }
    except Exception as e:
        return {
            "status": "error",
            "total_users": 0,
            "messages_today": 0,
            "qualified_leads": 0,
            "pending_quotes": 0,
            "error": str(e)
        }

# ============= LOGS =============

@router.get("/logs")
async def get_logs(last: int = 50):
    """Obtiene los últimos logs del sistema"""
    try:
        from config import Config
        
        if not os.path.exists(Config.LOG_FILE):
            return []
        
        with open(Config.LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        logs = []
        for line in lines[-last:]:
            # Parsear formato de log
            parts = line.split(' - ')
            if len(parts) >= 3:
                logs.append({
                    "timestamp": parts[0],
                    "level": parts[2].strip(),
                    "message": ' - '.join(parts[3:]).strip()
                })
        
        return logs
    except Exception as e:
        return [{"timestamp": datetime.now().isoformat(), "level": "ERROR", "message": str(e)}]

# ============= UTILIDADES =============

def update_env_file(key: str, value: str):
    """Actualiza una variable en el archivo .env"""
    env_file = ".env"
    
    if not os.path.exists(env_file):
        with open(env_file, 'w') as f:
            f.write(f"{key}={value}\n")
        return
    
    with open(env_file, 'r') as f:
        lines = f.readlines()
    
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            found = True
            break
    
    if not found:
        lines.append(f"{key}={value}\n")
    
    with open(env_file, 'w') as f:
        f.writelines(lines)

def update_seller_phones(sellers: List[dict]):
    """Actualiza la lista de teléfonos de vendedores en .env"""
    active_sellers = [s for s in sellers if s.get("active", True)]
    active_sellers.sort(key=lambda x: x.get("priority", 0), reverse=True)
    
    phones = ",".join([s["phone"] for s in active_sellers])
    emails = ",".join([s["email"] for s in active_sellers if s.get("email")])
    
    update_env_file("SELLER_PHONE_NUMBERS", phones)
    if emails:
        update_env_file("SELLER_EMAILS", emails)