import os
import asyncio
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, constants
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from google.genai import types
import database

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TOKEN or not GEMINI_API_KEY:
    raise ValueError("Faltan TELEGRAM_BOT_TOKEN o GEMINI_API_KEY en el archivo .env")

# Inicializar cliente de Gemini
genai_client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTION = (
    "Eres SIO OPTIMA, un gestor y administrador de tareas avanzado en Telegram. "
    "Tu objetivo es ayudar al usuario a organizar su vida y trabajo. "
    "Puedes crear tareas, listarlas, marcarlas como completadas y eliminarlas. "
    "Analiza imágenes y audios para extraer tareas o información relevante. "
    "Si detectas que el usuario quiere recordar algo o tiene una tarea pendiente en su mensaje, "
    "identifícala claramente. Responde siempre de forma profesional, eficiente y motivadora."
)

import unicodedata

DAY_NAMES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

def _strip_accents(text):
    """Elimina acentos y diacríticos de un texto."""
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.category(c).startswith('M'))

def normalize_day(raw):
    """
    Reconoce un día de la semana a partir de texto flexible.
    Acepta: con/sin tildes, abreviaciones, errores comunes.
    Retorna el número del día (0=lunes..6=domingo) o None.
    """
    s = _strip_accents(raw.strip().lower())

    # Mapeo amplio: variantes completas, abreviaciones y errores comunes
    day_variants = {
        0: ['lunes', 'lun', 'lu', 'lns'],
        1: ['martes', 'mar', 'ma', 'marte', 'marts'],
        2: ['miercoles', 'mie', 'mi', 'miérc', 'mx', 'mier', 'miercole'],
        3: ['jueves', 'jue', 'ju', 'juev', 'juves'],
        4: ['viernes', 'vie', 'vi', 'vir', 'viern', 'viermes'],
        5: ['sabado', 'sab', 'sa', 'sabdo'],
        6: ['domingo', 'dom', 'do', 'domin', 'dmgo', 'dgo'],
    }

    for day_num, variants in day_variants.items():
        if s in variants:
            return day_num

    # Fallback: coincidencia parcial (si el input es prefijo de alguna variante larga)
    for day_num, variants in day_variants.items():
        full_name = variants[0]  # nombre completo sin tildes
        if full_name.startswith(s) and len(s) >= 2:
            return day_num

    return None

def parse_time(time_str):
    """Valida y normaliza una hora en formato HH:MM. Acepta H:MM también."""
    # Aceptar formatos como "3:00" -> "03:00"
    try:
        t = datetime.strptime(time_str, "%H:%M")
        return t.strftime("%H:%M")
    except ValueError:
        pass
    try:
        t = datetime.strptime(time_str, "%I:%M%p")
        return t.strftime("%H:%M")
    except ValueError:
        return None

# --- Comandos del Bot ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        rf"¡Hola {user.mention_html()}! Soy <b>SIO OPTIMA</b>, tu administrador de tareas personal. "
        "\n\nUsa /help para ver los comandos disponibles o simplemente envíame un mensaje, foto o audio para empezar a organizar tus pendientes."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "<b>Comandos SIO OPTIMA:</b>\n"
        "/add [descripción] - Añade una nueva tarea\n"
        "/list - Muestra tus tareas pendientes\n"
        "/done [ID] - Marca una tarea como completada\n"
        "/delete [ID] - Elimina una tarea\n"
        "/help - Muestra este mensaje\n\n"
        "También puedes enviarme fotos de notas, capturas de pantalla o audios, y yo me encargaré de extraer las tareas por ti."
    )
    await update.message.reply_html(help_text)

async def add_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    description = " ".join(context.args)
    if not description:
        await update.message.reply_text("Por favor, proporciona una descripción para la tarea. Ej: /add Comprar leche")
        return
    
    task_id = database.add_task(update.effective_user.id, description)
    await update.message.reply_text(f"✅ Tarea añadida con éxito (ID: {task_id}): {description}")

async def list_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    tasks = database.get_tasks(user_id, status='pending')
    
    if not tasks:
        await update.message.reply_text("No tienes tareas pendientes. ¡Buen trabajo! 😊")
        return
    
    response = "<b>📋 Tus Tareas Pendientes:</b>\n\n"
    for task in tasks:
        response += f"• <b>[{task[0]}]</b> {task[1]}\n"
    
    await update.message.reply_html(response)

async def done_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /done [ID]")
        return
    
    try:
        task_id = int(context.args[0])
        success = database.update_task_status(task_id, update.effective_user.id, 'completed')
        if success:
            await update.message.reply_text(f"🏁 Tarea {task_id} marcada como completada.")
        else:
            await update.message.reply_text(f"❌ No se encontró la tarea con ID {task_id}.")
    except ValueError:
        await update.message.reply_text("El ID debe ser un número.")

async def delete_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /delete [ID]")
        return
    
    try:
        task_id = int(context.args[0])
        success = database.delete_task(task_id, update.effective_user.id)
        if success:
            await update.message.reply_text(f"🗑️ Tarea {task_id} eliminada.")
        else:
            await update.message.reply_text(f"❌ No se encontró la tarea con ID {task_id}.")
    except ValueError:
        await update.message.reply_text("El ID debe ser un número.")

# --- Bloques de Estudio ---

async def bloque_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Añadir un bloque de estudio: /bloque Matemáticas lunes 15:00 17:00"""
    if len(context.args) < 4:
        await update.message.reply_html(
            "<b>Uso:</b> /bloque [materia] [día] [hora_inicio] [hora_fin]\n"
            "<b>Ejemplo:</b> /bloque Matemáticas lunes 15:00 17:00\n\n"
            "<b>Días válidos:</b> lunes, martes, miércoles, jueves, viernes, sábado, domingo"
        )
        return

    # El último arg es hora_fin, penúltimo hora_inicio, antepenúltimo es el día
    end_time_str = context.args[-1]
    start_time_str = context.args[-2]
    day_str = context.args[-3].lower()
    subject = " ".join(context.args[:-3])

    if not subject:
        await update.message.reply_text("❌ Falta el nombre de la materia.")
        return

    day_num = normalize_day(day_str)
    if day_num is None:
        await update.message.reply_text(
            f"❌ No pude reconocer el día: '{day_str}'.\n"
            "Puedes escribirlo como quieras: lunes, lun, miercoles, mie, sab, etc."
        )
        return

    start_time = parse_time(start_time_str)
    end_time = parse_time(end_time_str)
    if not start_time or not end_time:
        await update.message.reply_text("❌ Formato de hora no válido. Usa HH:MM (ej: 15:00).")
        return

    if start_time >= end_time:
        await update.message.reply_text("❌ La hora de inicio debe ser anterior a la hora de fin.")
        return

    block_id = database.add_study_block(update.effective_user.id, subject, day_num, start_time, end_time)

    day_name = DAY_NAMES[day_num]
    await update.message.reply_html(
        f"📚 <b>Bloque de estudio creado</b> (ID: {block_id})\n"
        f"• Materia: <b>{subject}</b>\n"
        f"• Día: {day_name}\n"
        f"• Horario: {start_time} - {end_time}\n\n"
        f"Te recordaré 10 minutos antes ⏰"
    )

async def bloques_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Listar todos los bloques de estudio del usuario."""
    blocks = database.get_study_blocks(update.effective_user.id)

    if not blocks:
        await update.message.reply_text("No tienes bloques de estudio programados. Usa /bloque para crear uno.")
        return

    response = "<b>📚 Tus Bloques de Estudio:</b>\n\n"
    current_day = -1
    for block_id, subject, day, start, end in blocks:
        if day != current_day:
            current_day = day
            response += f"<b>📅 {DAY_NAMES[day]}</b>\n"
        response += f"  • [{block_id}] <b>{subject}</b>  ⏰ {start} - {end}\n"
    
    response += "\nUsa /bloque_del [ID] para eliminar un bloque."
    await update.message.reply_html(response)

async def bloque_del_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Eliminar un bloque de estudio."""
    if not context.args:
        await update.message.reply_text("Uso: /bloque_del [ID]")
        return

    try:
        block_id = int(context.args[0])
        success = database.delete_study_block(block_id, update.effective_user.id)
        if success:
            await update.message.reply_text(f"🗑️ Bloque de estudio {block_id} eliminado.")
        else:
            await update.message.reply_text(f"❌ No se encontró el bloque con ID {block_id}.")
    except ValueError:
        await update.message.reply_text("El ID debe ser un número.")

# --- Recordatorios ---

async def check_study_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job que se ejecuta cada minuto para verificar bloques próximos."""
    now = datetime.now()
    reminder_time = now + timedelta(minutes=10)
    
    day_of_week = reminder_time.weekday()
    time_str = reminder_time.strftime("%H:%M")
    
    blocks = database.get_blocks_for_reminder(day_of_week, time_str)
    
    for block_id, user_id, subject, start, end in blocks:
        day_name = DAY_NAMES[day_of_week]
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"⏰ <b>¡Recordatorio!</b>\n\n"
                     f"📚 <b>{subject}</b> comienza en 10 minutos\n"
                     f"🕐 {start} - {end} ({day_name})\n\n"
                     f"¡Prepárate para estudiar! 💪",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Error enviando recordatorio a {user_id}: {e}")

# Esquema JSON para detección autónoma de tareas
TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "is_task": {"type": "boolean", "description": "¿El mensaje contiene una nueva tarea o pendiente?"},
        "task_description": {"type": "string", "description": "Descripción clara y concisa de la tarea (si is_task es true)"},
        "response_text": {"type": "string", "description": "Respuesta amigable para el usuario"}
    },
    "required": ["is_task", "response_text"]
}

# --- Manejo de Mensajes e IA ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    user_id = update.effective_user.id
    text_content = message.text or message.caption or ""
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
    
    contents = []
    
    try:
        # 1. Multimedia: Fotos
        if message.photo:
            photo_file = await context.bot.get_file(message.photo[-1].file_id)
            photo_bytes = await photo_file.download_as_bytearray()
            contents.append(types.Part.from_bytes(data=bytes(photo_bytes), mime_type='image/jpeg'))
            
        # 2. Multimedia: Voz
        elif message.voice:
            voice_file = await context.bot.get_file(message.voice.file_id)
            voice_bytes = await voice_file.download_as_bytearray()
            contents.append(types.Part.from_bytes(data=bytes(voice_bytes), mime_type='audio/ogg'))
            
        # 3. Texto
        if text_content.strip():
            contents.append(text_content)
            
        if not contents:
            return

        # Consultar a Gemini con esquema JSON para detección de tareas
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_json_schema=TASK_SCHEMA
        )

        response = await genai_client.aio.models.generate_content(
            model='gemini-flash-latest',
            contents=contents,
            config=config
        )
        
        # Parsear la respuesta JSON
        import json
        result = json.loads(response.text)
        is_task = result.get("is_task", False)
        task_desc = result.get("task_description", "")
        reply_text = result.get("response_text", "")

        # Si se detectó una tarea, guardarla automáticamente
        if is_task and task_desc:
            task_id = database.add_task(user_id, task_desc)
            reply_text += f"\n\n✨ <b>Tarea guardada:</b> {task_desc} (ID: {task_id})"

        await update.message.reply_html(reply_text)

    except Exception as e:
        logger.error(f"Error procesando mensaje: {e}")
        # Error específico para cuota o saturación
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            error_msg = "⚠️ SIO OPTIMA ha alcanzado su límite de peticiones (Cuota excedida). Por favor, espera unos segundos e intenta de nuevo."
        elif "503" in str(e) or "UNAVAILABLE" in str(e):
            error_msg = "🚀 El servidor de IA está saturado en este momento. Inténtalo de nuevo en un momento."
        else:
            error_msg = "Lo siento, SIO OPTIMA tuvo un problema al procesar tu solicitud."
        
        await update.message.reply_text(error_msg)

def main() -> None:
    # Inicializar Base de Datos
    database.init_db()
    
    print("Iniciando SIO OPTIMA...")
    application = Application.builder().token(TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add", add_task_command))
    application.add_handler(CommandHandler("list", list_tasks_command))
    application.add_handler(CommandHandler("done", done_task_command))
    application.add_handler(CommandHandler("delete", delete_task_command))

    # Handlers de bloques de estudio
    application.add_handler(CommandHandler("bloque", bloque_command))
    application.add_handler(CommandHandler("bloques", bloques_command))
    application.add_handler(CommandHandler("bloque_del", bloque_del_command))

    # Filtro para mensajes (texto, fotos, voz)
    msg_filter = (filters.TEXT | filters.PHOTO | filters.VOICE) & ~filters.COMMAND
    application.add_handler(MessageHandler(msg_filter, handle_message))

    # Programar verificación de recordatorios cada 60 segundos
    application.job_queue.run_repeating(check_study_reminders, interval=60, first=10)

    print("SIO OPTIMA en ejecución. Presiona Ctrl+C para detenerlo.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
