import sqlite3
import os
import logging
from datetime import datetime

# Usar ruta absoluta para evitar conflictos con el directorio de ejecución
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "sio_optima.db")

logger = logging.getLogger(__name__)

def init_db():
    logger.info(f"Inicializando base de datos en: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            day_of_week INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def add_task(user_id, description):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks (user_id, description)
        VALUES (?, ?)
    ''', (user_id, description))
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id

def get_tasks(user_id, status=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if status:
        cursor.execute('''
            SELECT id, description, status, created_at FROM tasks
            WHERE user_id = ? AND status = ?
            ORDER BY created_at DESC
        ''', (user_id, status))
    else:
        cursor.execute('''
            SELECT id, description, status, created_at FROM tasks
            WHERE user_id = ?
            ORDER BY status DESC, created_at DESC
        ''', (user_id,))
    tasks = cursor.fetchall()
    conn.close()
    return tasks

def update_task_status(task_id, user_id, status):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE tasks SET status = ?
        WHERE id = ? AND user_id = ?
    ''', (status, task_id, user_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def delete_task(task_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM tasks
        WHERE id = ? AND user_id = ?
    ''', (task_id, user_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def add_study_block(user_id, subject, day_of_week, start_time, end_time):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO study_blocks (user_id, subject, day_of_week, start_time, end_time)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, subject, day_of_week, start_time, end_time))
    block_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return block_id

def get_study_blocks(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, subject, day_of_week, start_time, end_time FROM study_blocks
        WHERE user_id = ?
        ORDER BY day_of_week, start_time
    ''', (user_id,))
    blocks = cursor.fetchall()
    conn.close()
    return blocks

def delete_study_block(block_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM study_blocks
        WHERE id = ? AND user_id = ?
    ''', (block_id, user_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def get_blocks_for_reminder(day_of_week, time_str):
    """Obtiene bloques que inician en el tiempo indicado para enviar recordatorio."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, subject, start_time, end_time FROM study_blocks
        WHERE day_of_week = ? AND start_time = ?
    ''', (day_of_week, time_str))
    blocks = cursor.fetchall()
    conn.close()
    return blocks
