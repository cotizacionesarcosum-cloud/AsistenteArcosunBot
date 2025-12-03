import sqlite3
from datetime import datetime
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)

class Database:
    """Maneja todas las operaciones de base de datos"""
    
    def __init__(self, db_path: str = "whatsapp_bot.db"):
        """
        Inicializa la conexión a la base de datos
        
        Args:
            db_path: Ruta al archivo de base de datos SQLite
        """
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Crea una nueva conexión a la base de datos"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Para obtener resultados como diccionarios
        return conn
    
    def init_database(self):
        """Crea las tablas necesarias si no existen"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Tabla de usuarios
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT UNIQUE NOT NULL,
                name TEXT,
                email TEXT,
                company TEXT,
                state TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de mensajes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT NOT NULL,
                message_text TEXT NOT NULL,
                message_type TEXT DEFAULT 'text',
                direction TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (phone_number) REFERENCES users (phone_number)
            )
        ''')
        
        # Tabla de cotizaciones
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT NOT NULL,
                project_type TEXT,
                dimensions TEXT,
                location TEXT,
                estimated_time TEXT,
                additional_info TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (phone_number) REFERENCES users (phone_number)
            )
        ''')
        
        # Tabla de conversaciones (para tracking de contexto)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT NOT NULL,
                context TEXT,
                state TEXT,
                data TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (phone_number) REFERENCES users (phone_number)
            )
        ''')
        
        # Tabla de análisis de leads por IA
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lead_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT NOT NULL,
                lead_score INTEGER,
                lead_type TEXT,
                is_qualified BOOLEAN,
                project_info TEXT,
                summary TEXT,
                next_action TEXT,
                notified BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (phone_number) REFERENCES users (phone_number)
            )
        ''')

        # Agregar columna division a users si no existe
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN division TEXT")
            logger.info("Columna 'division' agregada a tabla users")
        except sqlite3.OperationalError:
            # La columna ya existe
            pass

        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    
    def create_user(self, phone_number: str, name: Optional[str] = None) -> bool:
        """
        Crea un nuevo usuario
        
        Args:
            phone_number: Número de teléfono del usuario
            name: Nombre opcional del usuario
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO users (phone_number, name)
                VALUES (?, ?)
            ''', (phone_number, name))
            
            conn.commit()
            conn.close()
            logger.info(f"User created: {phone_number}")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"User already exists: {phone_number}")
            return False
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            return False
    
    def user_exists(self, phone_number: str) -> bool:
        """Verifica si un usuario existe"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT 1 FROM users WHERE phone_number = ?', (phone_number,))
        exists = cursor.fetchone() is not None
        
        conn.close()
        return exists
    
    def get_user(self, phone_number: str) -> Optional[Dict]:
        """Obtiene información de un usuario"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE phone_number = ?', (phone_number,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def update_user(self, phone_number: str, **kwargs):
        """
        Actualiza información de un usuario
        
        Args:
            phone_number: Número del usuario
            **kwargs: Campos a actualizar (name, email, company, etc.)
        """
        if not kwargs:
            return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Construir query dinámicamente
        fields = ', '.join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [phone_number]
        
        cursor.execute(f'''
            UPDATE users 
            SET {fields}, last_interaction = CURRENT_TIMESTAMP
            WHERE phone_number = ?
        ''', values)
        
        conn.commit()
        conn.close()
    
    def update_user_state(self, phone_number: str, state: str):
        """Actualiza el estado del usuario (para flujos de conversación)"""
        self.update_user(phone_number, state=state)

    def set_user_division(self, phone_number: str, division: str):
        """
        Establece la división del usuario (techos o rolados)

        Args:
            phone_number: Número del usuario
            division: 'techos' o 'rolados'
        """
        self.update_user(phone_number, division=division)
        logger.info(f"División '{division}' guardada para {phone_number}")

    def get_user_division(self, phone_number: str) -> Optional[str]:
        """
        Obtiene la división del usuario

        Args:
            phone_number: Número del usuario

        Returns:
            'techos', 'rolados', o None si no está definida
        """
        user = self.get_user(phone_number)
        if user:
            return user.get('division')
        return None
    
    def save_message(self, phone_number: str, message_text: str, direction: str):
        """
        Guarda un mensaje en la base de datos
        
        Args:
            phone_number: Número del usuario
            message_text: Contenido del mensaje
            direction: 'received' o 'sent'
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO messages (phone_number, message_text, direction)
            VALUES (?, ?, ?)
        ''', (phone_number, message_text, direction))
        
        # Actualizar última interacción del usuario
        cursor.execute('''
            UPDATE users 
            SET last_interaction = CURRENT_TIMESTAMP
            WHERE phone_number = ?
        ''', (phone_number,))
        
        conn.commit()
        conn.close()
    
    def get_conversation_history(self, phone_number: str, limit: int = 10) -> List[Dict]:
        """
        Obtiene el historial de conversación de un usuario
        
        Args:
            phone_number: Número del usuario
            limit: Cantidad de mensajes a obtener
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM messages
            WHERE phone_number = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (phone_number, limit))
        
        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return messages[::-1]  # Invertir para orden cronológico
    
    def create_quote(self, phone_number: str, **kwargs) -> int:
        """
        Crea una nueva solicitud de cotización
        
        Args:
            phone_number: Número del usuario
            **kwargs: Datos de la cotización
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO quotes (
                phone_number, 
                project_type, 
                dimensions, 
                location, 
                estimated_time,
                additional_info
            )
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            phone_number,
            kwargs.get('project_type'),
            kwargs.get('dimensions'),
            kwargs.get('location'),
            kwargs.get('estimated_time'),
            kwargs.get('additional_info')
        ))
        
        quote_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Quote created: {quote_id} for {phone_number}")
        return quote_id
    
    def get_pending_quotes(self) -> List[Dict]:
        """Obtiene todas las cotizaciones pendientes"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT q.*, u.name, u.email, u.company
            FROM quotes q
            JOIN users u ON q.phone_number = u.phone_number
            WHERE q.status = 'pending'
            ORDER BY q.created_at DESC
        ''')
        
        quotes = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return quotes
    
    def update_quote_status(self, quote_id: int, status: str):
        """Actualiza el estado de una cotización"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE quotes
            SET status = ?
            WHERE id = ?
        ''', (status, quote_id))
        
        conn.commit()
        conn.close()
    
    def get_statistics(self) -> Dict:
        """Obtiene estadísticas generales del bot"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Total de usuarios
        cursor.execute('SELECT COUNT(*) as total FROM users')
        total_users = cursor.fetchone()['total']
        
        # Usuarios activos hoy
        cursor.execute('''
            SELECT COUNT(*) as active 
            FROM users 
            WHERE DATE(last_interaction) = DATE('now')
        ''')
        active_today = cursor.fetchone()['active']
        
        # Total de mensajes
        cursor.execute('SELECT COUNT(*) as total FROM messages')
        total_messages = cursor.fetchone()['total']
        
        # Cotizaciones pendientes
        cursor.execute('''
            SELECT COUNT(*) as pending 
            FROM quotes 
            WHERE status = 'pending'
        ''')
        pending_quotes = cursor.fetchone()['pending']
        
        conn.close()
        
        return {
            'total_users': total_users,
            'active_today': active_today,
            'total_messages': total_messages,
            'pending_quotes': pending_quotes
        }
    
    def save_lead_analysis(self, phone_number: str, analysis: Dict):
        """
        Guarda el análisis de IA del lead
        
        Args:
            phone_number: Número del cliente
            analysis: Resultado del análisis de IA
        """
        import json
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO lead_analysis (
                phone_number,
                lead_score,
                lead_type,
                is_qualified,
                project_info,
                summary,
                next_action
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            phone_number,
            analysis.get('lead_score', 0),
            analysis.get('lead_type', ''),
            analysis.get('is_qualified_lead', False),
            json.dumps(analysis.get('project_info', {})),
            analysis.get('summary_for_seller', ''),
            analysis.get('next_action', '')
        ))
        
        conn.commit()
        conn.close()
    
    def get_lead_analysis_history(self, phone_number: str) -> List[Dict]:
        """Obtiene el historial de análisis de un lead"""
        import json
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM lead_analysis
            WHERE phone_number = ?
            ORDER BY created_at DESC
        ''', (phone_number,))
        
        analyses = []
        for row in cursor.fetchall():
            analysis = dict(row)
            # Convertir JSON string a dict
            if analysis.get('project_info'):
                analysis['project_info'] = json.loads(analysis['project_info'])
            analyses.append(analysis)
        
        conn.close()
        return analyses