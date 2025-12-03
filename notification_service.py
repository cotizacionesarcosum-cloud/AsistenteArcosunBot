import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from typing import Optional, List
from whatsapp_client import WhatsAppClient

logger = logging.getLogger(__name__)

class NotificationService:
    """Servicio para enviar notificaciones a vendedores por WhatsApp y Email"""

    def __init__(self, whatsapp_client: WhatsAppClient,
                 smtp_config: Optional[dict] = None,
                 seller_phones_techos: Optional[List[str]] = None,
                 seller_emails_techos: Optional[List[str]] = None,
                 seller_phones_rolados: Optional[List[str]] = None,
                 seller_emails_rolados: Optional[List[str]] = None,
                 template_name: Optional[str] = None,
                 template_language: str = "es_MX"):
        """
        Inicializa el servicio de notificaciones

        Args:
            whatsapp_client: Cliente de WhatsApp para enviar mensajes
            smtp_config: Configuración SMTP para emails
            seller_phones_techos: Lista de números de vendedores de TECHOS
            seller_emails_techos: Lista de emails de vendedores de TECHOS
            seller_phones_rolados: Lista de números de vendedores de ROLADOS
            seller_emails_rolados: Lista de emails de vendedores de ROLADOS
            template_name: Nombre de la plantilla aprobada en Meta
            template_language: Código de idioma de la plantilla
        """
        self.whatsapp = whatsapp_client
        self.smtp_config = smtp_config or {}
        self.seller_phones_techos = seller_phones_techos or []
        self.seller_emails_techos = seller_emails_techos or []
        self.seller_phones_rolados = seller_phones_rolados or []
        self.seller_emails_rolados = seller_emails_rolados or []
        self.template_name = template_name
        self.template_language = template_language
    
    async def notify_qualified_lead(self, lead_data: dict, notification_message: str):
        """
        Notifica a vendedores sobre un lead calificado

        Args:
            lead_data: Datos del lead (phone, score, etc)
            notification_message: Mensaje formateado para el vendedor
        """
        client_phone = lead_data.get("phone_number", "")
        lead_score = lead_data.get("lead_score", 0)
        media_files = lead_data.get("media_files", [])
        division = lead_data.get("division", "indefinido").lower()

        # Determinar a qué vendedores enviar según división
        seller_phones = []
        seller_emails = []

        if division == "techos":
            seller_phones = self.seller_phones_techos
            seller_emails = self.seller_emails_techos
            division_nombre = "TECHOS"
        elif division == "rolados":
            seller_phones = self.seller_phones_rolados
            seller_emails = self.seller_emails_rolados
            division_nombre = "ROLADOS"
        else:
            # Si no es techos ni rolados, no enviar notificación
            logger.warning(f"⚠️ División '{division}' no válida. Solo se acepta 'techos' o 'rolados'. NO se enviará notificación.")
            logger.warning("="*60)
            return

        logger.info("="*60)
        logger.info(f"🔔 NOTIFICACIÓN DE LEAD CALIFICADO ACTIVADA")
        logger.info(f"Cliente: {client_phone}")
        logger.info(f"Lead Score: {lead_score}/10")
        logger.info(f"División: {division_nombre}")
        logger.info(f"Tipo: {lead_data.get('lead_type', 'N/A')}")
        logger.info(f"Archivos multimedia: {len(media_files)}")
        logger.info(f"Vendedores a notificar (WhatsApp): {len(seller_phones)} números")
        logger.info(f"Vendedores a notificar (Email): {len(seller_emails)} emails")
        logger.info("="*60)

        # Notificar por WhatsApp
        whatsapp_success = await self._notify_via_whatsapp(notification_message, media_files, lead_data, seller_phones)

        # Notificar por Email (si está configurado)
        email_success = False
        if self.smtp_config.get("enabled", False) and seller_emails:
            email_success = await self._notify_via_email(lead_data, notification_message, seller_emails)

        logger.info(f"✅ Notificación completada - WhatsApp: {whatsapp_success}, Email: {email_success}")
        logger.info("="*60)
    
    async def _notify_via_whatsapp(self, message: str, media_files: list = None, lead_data: dict = None, seller_phones: list = None) -> bool:
        """
        Envía notificación por WhatsApp a los vendedores especificados

        Args:
            message: Mensaje de texto de la notificación
            media_files: Lista opcional de archivos multimedia para reenviar
            lead_data: Datos del lead para construir parámetros de plantilla
            seller_phones: Lista de números de vendedores a notificar
        """
        if not seller_phones or (len(seller_phones) == 1 and not seller_phones[0]):
            logger.warning("⚠️ No hay números de vendedores para esta división")
            return False

        success_count = 0
        for seller_phone in seller_phones:
            if not seller_phone or seller_phone.strip() == "":
                logger.warning("⚠️ Número de vendedor vacío, saltando...")
                continue

            try:
                logger.info(f"📤 Enviando notificación WhatsApp a: {seller_phone}")

                # PASO 1: Enviar plantilla aprobada para abrir ventana de 24 horas
                if self.template_name and lead_data:
                    try:
                        # Preparar parámetros de la plantilla
                        # {{1}}: Cliente, {{2}}: Tipo, {{3}}: Resumen, {{4}}: Detalles, {{5}}: Acción, {{6}}: Fecha
                        template_params = self._build_template_parameters(lead_data)

                        logger.info(f"📋 Enviando plantilla '{self.template_name}' a {seller_phone}")
                        template_result = self.whatsapp.send_template_message(
                            to=seller_phone,
                            template_name=self.template_name,
                            language_code=self.template_language,
                            parameters=template_params
                        )
                        logger.info(f"✅ Plantilla enviada exitosamente a {seller_phone}")
                        logger.debug(f"Respuesta plantilla: {template_result}")
                    except Exception as e:
                        logger.error(f"⚠️ Error enviando plantilla (intentando mensaje normal): {str(e)}")
                        # Si falla la plantilla, continuar con mensaje normal

                # PASO 2: Enviar mensaje detallado con información del lead
                result = self.whatsapp.send_text_message(seller_phone, message)
                logger.info(f"✅ Mensaje detallado enviado exitosamente a {seller_phone}")
                logger.debug(f"Respuesta API: {result}")

                # PASO 3: Reenviar archivos multimedia si existen
                if media_files:
                    await self._forward_media_files(seller_phone, media_files)

                success_count += 1

            except Exception as e:
                logger.error(f"❌ Error enviando WhatsApp a {seller_phone}: {str(e)}")

        return success_count > 0

    def _build_template_parameters(self, lead_data: dict) -> list:
        """
        Construye los parámetros para la plantilla de WhatsApp

        Args:
            lead_data: Datos del lead

        Returns:
            Lista de parámetros para {{1}}, {{2}}, {{3}}, etc.
        """
        # {{1}}: Cliente (número de teléfono)
        cliente = lead_data.get("phone_number", "No disponible")

        # {{2}}: Tipo de lead
        tipo = lead_data.get("lead_type", "consulta_general")
        if not tipo or tipo.strip() == "":
            tipo = "consulta_general"

        # {{3}}: Resumen
        resumen = lead_data.get("summary_for_seller", "Cliente interesado en cotización")
        if not resumen or resumen.strip() == "":
            resumen = "Cliente interesado en cotización"

        # {{4}}: Detalles del proyecto
        project_info = lead_data.get("project_info", {})
        if project_info and any(v for v in project_info.values() if v):
            detalles = "\n".join([f"{k}: {v}" for k, v in project_info.items() if v])
        else:
            detalles = "Pendiente de recopilar más detalles"

        # Si detalles quedó vacío por alguna razón, poner valor por defecto
        if not detalles or detalles.strip() == "":
            detalles = "Pendiente de recopilar más detalles"

        # {{5}}: Acción recomendada
        accion = lead_data.get("next_action", "Contactar al cliente lo antes posible")
        if not accion or accion.strip() == "":
            accion = "Contactar al cliente lo antes posible"

        # {{6}}: Fecha
        fecha = lead_data.get("timestamp", "Ahora")
        if not fecha or fecha.strip() == "":
            fecha = "Ahora"

        # Log para debugging
        logger.info(f"📋 Parámetros de plantilla construidos:")
        logger.info(f"   {{{{1}}}}: {cliente[:50]}...")
        logger.info(f"   {{{{2}}}}: {tipo}")
        logger.info(f"   {{{{3}}}}: {resumen[:50]}...")
        logger.info(f"   {{{{4}}}}: {detalles[:50]}...")
        logger.info(f"   {{{{5}}}}: {accion[:50]}...")
        logger.info(f"   {{{{6}}}}: {fecha}")

        return [cliente, tipo, resumen, detalles, accion, fecha]

    async def _forward_media_files(self, seller_phone: str, media_files: list):
        """
        Reenvía archivos multimedia al vendedor

        Args:
            seller_phone: Número del vendedor
            media_files: Lista de archivos multimedia
        """
        for media in media_files:
            try:
                media_type = media.get("type", "")
                media_url = media.get("url", "")

                if not media_url:
                    continue

                logger.info(f"📎 Reenviando {media_type} a {seller_phone}")

                # Nota: Aquí usamos el media_id que recibimos del webhook
                # WhatsApp API permite reenviar usando el ID del medio
                if "image" in media_type.lower():
                    # Para imágenes se requiere la URL completa o el media_id
                    self.whatsapp.send_text_message(
                        seller_phone,
                        f"📸 Imagen del cliente: {media_url}"
                    )
                elif "document" in media_type.lower() or "pdf" in media_type.lower():
                    # Para documentos/PDFs
                    self.whatsapp.send_text_message(
                        seller_phone,
                        f"📄 Documento del cliente: {media_url}"
                    )

                logger.info(f"✅ Multimedia reenviado a {seller_phone}")

            except Exception as e:
                logger.error(f"❌ Error reenviando multimedia: {str(e)}")
    
    async def _notify_via_email(self, lead_data: dict, message_body: str, seller_emails: list = None) -> bool:
        """Envía notificación por email a los vendedores especificados"""

        if not self.smtp_config.get("enabled", False):
            logger.info("ℹ️ SMTP no habilitado, notificación por email omitida")
            return False

        if not seller_emails or (len(seller_emails) == 1 and not seller_emails[0]):
            logger.warning("⚠️ No hay emails de vendedores para esta división")
            return False

        subject = f"🔔 Nuevo Lead Calificado - Score: {lead_data.get('lead_score', 0)}/10"

        # Crear email HTML
        html_body = self._create_email_html(lead_data, message_body)

        success_count = 0
        for email in seller_emails:
            if not email or email.strip() == "":
                logger.warning("⚠️ Email de vendedor vacío, saltando...")
                continue

            try:
                logger.info(f"📧 Enviando email a: {email}")
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = self.smtp_config.get('from_email', '')
                msg['To'] = email

                # Agregar versión de texto plano
                text_part = MIMEText(message_body, 'plain', 'utf-8')
                msg.attach(text_part)

                # Agregar versión HTML
                html_part = MIMEText(html_body, 'html', 'utf-8')
                msg.attach(html_part)

                # Enviar email
                with smtplib.SMTP(self.smtp_config['smtp_server'],
                                 self.smtp_config['smtp_port']) as server:
                    if self.smtp_config.get('use_tls', True):
                        server.starttls()

                    server.login(
                        self.smtp_config['username'],
                        self.smtp_config['password']
                    )

                    server.send_message(msg)

                logger.info(f"✅ Email enviado exitosamente a {email}")
                success_count += 1

            except Exception as e:
                logger.error(f"❌ Error enviando email a {email}: {str(e)}")

        return success_count > 0
    
    def _create_email_html(self, lead_data: dict, message_body: str) -> str:
        """Crea un email HTML formateado para el vendedor"""
        
        project_info = lead_data.get("project_info", {})
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    border-radius: 10px 10px 0 0;
                    text-align: center;
                }}
                .content {{
                    background: #f9f9f9;
                    padding: 30px;
                    border-radius: 0 0 10px 10px;
                }}
                .info-box {{
                    background: white;
                    padding: 20px;
                    margin: 15px 0;
                    border-radius: 8px;
                    border-left: 4px solid #667eea;
                }}
                .score {{
                    font-size: 48px;
                    font-weight: bold;
                    color: #667eea;
                    margin: 10px 0;
                }}
                .label {{
                    font-weight: bold;
                    color: #667eea;
                }}
                .action-button {{
                    display: inline-block;
                    padding: 12px 30px;
                    background: #667eea;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    margin-top: 20px;
                }}
                .whatsapp-link {{
                    color: #25D366;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔔 Nuevo Lead Calificado</h1>
                    <div class="score">{lead_data.get('lead_score', 0)}/10</div>
                </div>
                
                <div class="content">
                    <div class="info-box">
                        <p><span class="label">📱 Cliente:</span> {lead_data.get('phone_number', 'N/A')}</p>
                        <p><span class="label">🏷️ Tipo:</span> {lead_data.get('lead_type', 'N/A')}</p>
                        <p><span class="label">⏰ Fecha:</span> {lead_data.get('timestamp', 'N/A')}</p>
                    </div>
                    
                    <div class="info-box">
                        <h3>📋 Resumen del Proyecto</h3>
                        <p>{lead_data.get('summary_for_seller', 'No disponible')}</p>
                    </div>
                    
                    <div class="info-box">
                        <h3>🔧 Detalles del Proyecto</h3>
                        <ul>
                            {''.join([f"<li><strong>{k}:</strong> {v}</li>" for k, v in project_info.items() if v])}
                        </ul>
                    </div>
                    
                    <div class="info-box">
                        <h3>💡 Acción Recomendada</h3>
                        <p>{lead_data.get('next_action', 'Contactar al cliente')}</p>
                    </div>
                    
                    <div style="text-align: center;">
                        <a href="https://wa.me/{lead_data.get('phone_number', '').replace('+', '')}" 
                           class="action-button">
                            💬 Contactar por WhatsApp
                        </a>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    async def notify_new_message(self, from_number: str, message_text: str):
        """
        Notificación simple de nuevo mensaje (opcional, para todos los mensajes)
        
        Args:
            from_number: Número que envió el mensaje
            message_text: Contenido del mensaje
        """
        notification = f"""📨 *Nuevo mensaje*

De: {from_number}
Mensaje: {message_text[:100]}{'...' if len(message_text) > 100 else ''}"""
        
        # Solo enviar a un número principal (no saturar)
        if self.seller_phones:
            main_seller = self.seller_phones[0]
            try:
                self.whatsapp.send_text_message(main_seller, notification)
            except Exception as e:
                logger.error(f"Error sending new message notification: {str(e)}")
    
    async def notify_error(self, error_message: str, context: dict):
        """
        Notifica errores críticos al equipo técnico
        
        Args:
            error_message: Descripción del error
            context: Contexto adicional del error
        """
        notification = f"""⚠️ *ERROR EN BOT DE WHATSAPP*

Error: {error_message}

Contexto:
{context}

Por favor revisar logs del sistema."""
        
        # Enviar solo al primer número (admin/técnico)
        if self.seller_phones:
            try:
                self.whatsapp.send_text_message(self.seller_phones[0], notification)
            except:
                logger.error("Failed to send error notification")