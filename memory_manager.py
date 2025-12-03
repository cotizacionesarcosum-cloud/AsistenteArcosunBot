import logging
from datetime import datetime, timedelta
from typing import Dict
from database import Database

logger = logging.getLogger(__name__)

class MemoryManager:
    """Gestiona la limpieza de memoria de conversaciones inactivas"""

    def __init__(self, database: Database, inactivity_hours: int = 1):
        self.db = database
        self.inactivity_hours = inactivity_hours

    def cleanup_inactive_sessions(self):
        """
        Limpia las sesiones de memoria de usuarios inactivos por más de X horas

        Esto NO borra las conversaciones del historial, solo marca que la
        conversación debe iniciar "fresca" la próxima vez
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=self.inactivity_hours)

            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Contar usuarios inactivos
            cursor.execute('''
                SELECT COUNT(*) as count
                FROM users
                WHERE last_interaction < ?
                AND state != 'inactive'
            ''', (cutoff_time.strftime("%Y-%m-%d %H:%M:%S"),))

            count = cursor.fetchone()['count']

            if count > 0:
                # Marcar usuarios como inactivos
                cursor.execute('''
                    UPDATE users
                    SET state = 'inactive'
                    WHERE last_interaction < ?
                    AND state != 'inactive'
                ''', (cutoff_time.strftime("%Y-%m-%d %H:%M:%S"),))

                conn.commit()
                logger.info(f"🧹 Limpieza de memoria: {count} usuarios marcados como inactivos")
            else:
                logger.debug("No hay sesiones para limpiar")

            conn.close()

            return count

        except Exception as e:
            logger.error(f"Error en limpieza de memoria: {str(e)}")
            return 0

    def reactivate_user(self, phone_number: str):
        """Reactiva un usuario cuando vuelve a escribir"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE users
                SET state = 'active', last_interaction = CURRENT_TIMESTAMP
                WHERE phone_number = ?
            ''', (phone_number,))

            conn.commit()
            conn.close()

            logger.debug(f"Usuario {phone_number} reactivado")

        except Exception as e:
            logger.error(f"Error reactivando usuario: {str(e)}")

    def get_fresh_context_limit(self, phone_number: str) -> int:
        """
        Determina cuántos mensajes de historial usar según actividad

        - Si el usuario está activo (< 1 hora): usar últimos 10 mensajes
        - Si está inactivo (> 1 hora): usar solo últimos 3 mensajes (conversación fresca)
        """
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT state, last_interaction
                FROM users
                WHERE phone_number = ?
            ''', (phone_number,))

            user = cursor.fetchone()
            conn.close()

            if not user:
                return 3  # Usuario nuevo, contexto mínimo

            state = user['state']

            if state == 'inactive':
                logger.info(f"👤 Usuario {phone_number} inactivo, usando contexto reducido (3 msgs)")
                return 3  # Contexto reducido para conversación fresca
            else:
                return 10  # Contexto completo para conversación activa

        except Exception as e:
            logger.error(f"Error obteniendo límite de contexto: {str(e)}")
            return 5  # Valor por defecto seguro
