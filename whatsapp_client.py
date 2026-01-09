import requests
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class WhatsAppClient:
    """Cliente para interactuar con WhatsApp Business API"""
    
    def __init__(self, access_token: str, phone_number_id: str):
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.base_url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    def _send_request(self, payload: Dict) -> Dict:
        """Método centralizado para enviar peticiones y manejar errores"""
        try:
            response = requests.post(self.base_url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            # Loguear el error exacto que devuelve Meta (útil para depurar el 400 Bad Request)
            logger.error(f"❌ Error HTTP {e.response.status_code}: {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error de conexión: {str(e)}")
            raise

    def send_text_message(self, to: str, message: str) -> Dict:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": message}
        }
        return self._send_request(payload)

    def send_interactive_buttons(self, to: str, body_text: str, buttons: List[Dict]) -> Dict:
        """
        Envía botones. Corrige el 'type' y recorta títulos largos automáticamente.
        """
        if len(buttons) > 3:
            logger.warning("Recortando lista de botones a 3 (límite de WhatsApp)")
            buttons = buttons[:3]
        
        button_components = []
        for btn in buttons:
            # BLINDAJE: WhatsApp da error 400 si el título supera 20 caracteres.
            # Lo recortamos automáticamente para evitar que el bot se caiga.
            title_safe = btn["title"][:20]
            
            button_components.append({
                "type": "reply",  # <--- AQUÍ ESTABA EL ERROR (antes decía "button")
                "reply": {
                    "id": btn["id"],
                    "title": title_safe
                }
            })
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": body_text[:1024] # Límite de cuerpo
                },
                "action": {
                    "buttons": button_components
                }
            }
        }
        
        logger.info(f"Enviando botones a {to}: {[b['reply']['title'] for b in button_components]}")
        return self._send_request(payload)
    
    def send_interactive_list(self, to: str, body_text: str, button_text: str, sections: List[Dict]) -> Dict:
        """Envía lista de opciones (Menú)"""
        # Blindaje para listas
        button_text_safe = button_text[:20]
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {
                    "text": body_text[:1024]
                },
                "action": {
                    "button": button_text_safe,
                    "sections": sections
                }
            }
        }
        return self._send_request(payload)
    
    def send_template_message(self, to: str, template_name: str, language_code: str = "es_MX",
                            parameters: Optional[List[str]] = None) -> Dict:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code}
            }
        }

        if parameters:
            payload["template"]["components"] = [{
                "type": "body",
                "parameters": [{"type": "text", "text": str(p)} for p in parameters]
            }]

        return self._send_request(payload)

    def mark_as_read(self, message_id: str) -> Dict:
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        return self._send_request(payload)
    
    # Métodos multimedia (sin cambios, solo usan el _send_request centralizado)
    def send_image(self, to: str, image_url: str, caption: Optional[str] = None) -> Dict:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "image",
            "image": {"link": image_url}
        }
        if caption:
            payload["image"]["caption"] = caption
        return self._send_request(payload)
    
    def send_document(self, to: str, document_url: str, filename: str, caption: Optional[str] = None) -> Dict:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "document",
            "document": {"link": document_url, "filename": filename}
        }
        if caption:
            payload["document"]["caption"] = caption
        return self._send_request(payload)