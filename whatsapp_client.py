import requests
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class WhatsAppClient:
    """Cliente para interactuar con WhatsApp Business API"""
    
    def __init__(self, access_token: str, phone_number_id: str):
        """
        Args:
            access_token: Token de acceso de tu app de Meta
            phone_number_id: ID del número de teléfono de WhatsApp Business
        """
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.base_url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    def send_text_message(self, to: str, message: str) -> Dict:
        """
        Envía un mensaje de texto simple
        
        Args:
            to: Número de teléfono destino (formato: 52XXXXXXXXXX)
            message: Texto del mensaje
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message
            }
        }
        
        try:
            response = requests.post(self.base_url, json=payload, headers=self.headers)
            response.raise_for_status()
            logger.info(f"Message sent successfully to {to}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending message: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            raise
    
    def send_template_message(self, to: str, template_name: str, language_code: str = "es_MX",
                            parameters: Optional[List[str]] = None) -> Dict:
        """
        Envía un mensaje usando una plantilla aprobada

        Args:
            to: Número de teléfono destino
            template_name: Nombre de la plantilla aprobada en Meta
            language_code: Código de idioma (por defecto español México)
            parameters: Lista de valores para las variables de la plantilla {{1}}, {{2}}, etc.
        """
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language_code
                }
            }
        }

        # Agregar parámetros si existen
        if parameters:
            payload["template"]["components"] = [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": str(param)
                        }
                        for param in parameters
                    ]
                }
            ]

        try:
            response = requests.post(self.base_url, json=payload, headers=self.headers)
            response.raise_for_status()
            logger.info(f"Template message sent to {to}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending template: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            raise
    
    def send_interactive_buttons(self, to: str, body_text: str, buttons: List[Dict]) -> Dict:
        """
        Envía un mensaje con botones interactivos
        
        Args:
            to: Número destino
            body_text: Texto del mensaje
            buttons: Lista de botones [{"id": "1", "title": "Opción 1"}, ...]
        """
        if len(buttons) > 3:
            raise ValueError("WhatsApp solo permite máximo 3 botones")
        
        button_components = [
            {
                "type": "button",
                "reply": {
                    "id": btn["id"],
                    "title": btn["title"]
                }
            }
            for btn in buttons
        ]
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": body_text
                },
                "action": {
                    "buttons": button_components
                }
            }
        }
        
        try:
            response = requests.post(self.base_url, json=payload, headers=self.headers)
            response.raise_for_status()
            logger.info(f"Interactive buttons sent to {to}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending buttons: {str(e)}")
            raise
    
    def send_interactive_list(self, to: str, body_text: str, button_text: str, sections: List[Dict]) -> Dict:
        """
        Envía un mensaje con lista interactiva
        
        Args:
            to: Número destino
            body_text: Texto del mensaje
            button_text: Texto del botón principal
            sections: Lista de secciones con opciones
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {
                    "text": body_text
                },
                "action": {
                    "button": button_text,
                    "sections": sections
                }
            }
        }
        
        try:
            response = requests.post(self.base_url, json=payload, headers=self.headers)
            response.raise_for_status()
            logger.info(f"Interactive list sent to {to}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending list: {str(e)}")
            raise
    
    def send_image(self, to: str, image_url: str, caption: Optional[str] = None) -> Dict:
        """
        Envía una imagen
        
        Args:
            to: Número destino
            image_url: URL pública de la imagen
            caption: Texto opcional para la imagen
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "image",
            "image": {
                "link": image_url
            }
        }
        
        if caption:
            payload["image"]["caption"] = caption
        
        try:
            response = requests.post(self.base_url, json=payload, headers=self.headers)
            response.raise_for_status()
            logger.info(f"Image sent to {to}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending image: {str(e)}")
            raise
    
    def send_document(self, to: str, document_url: str, filename: str, caption: Optional[str] = None) -> Dict:
        """
        Envía un documento (PDF, Excel, etc)
        
        Args:
            to: Número destino
            document_url: URL pública del documento
            filename: Nombre del archivo
            caption: Texto opcional
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "document",
            "document": {
                "link": document_url,
                "filename": filename
            }
        }
        
        if caption:
            payload["document"]["caption"] = caption
        
        try:
            response = requests.post(self.base_url, json=payload, headers=self.headers)
            response.raise_for_status()
            logger.info(f"Document sent to {to}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending document: {str(e)}")
            raise
    
    def mark_as_read(self, message_id: str) -> Dict:
        """
        Marca un mensaje como leído
        
        Args:
            message_id: ID del mensaje a marcar como leído
        """
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        
        try:
            response = requests.post(self.base_url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error marking as read: {str(e)}")
            raise