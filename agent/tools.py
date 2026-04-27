import os
import yaml
import logging
from datetime import datetime

logger = logging.getLogger("agentkit")


def cargar_info_negocio() -> dict:
    """Carga la información del negocio desde business.yaml."""
    try:
        with open("config/business.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("config/business.yaml no encontrado")
        return {}


def obtener_horario() -> dict:
    """Retorna el horario de atención y si el consultorio está abierto ahora."""
    info = cargar_info_negocio()
    ahora = datetime.now()
    dia_semana = ahora.weekday()  # 0=lunes, 6=domingo
    hora = ahora.hour + ahora.minute / 60

    # Lunes a Viernes (0-4): 9am-7pm, Sábado (5): 9am-2pm
    if dia_semana <= 4:
        esta_abierto = 9.0 <= hora < 19.0
    elif dia_semana == 5:
        esta_abierto = 9.0 <= hora < 14.0
    else:
        esta_abierto = False

    return {
        "horario": info.get("negocio", {}).get("horario", "Lunes a Viernes 9am-7pm, Sábados 9am-2pm"),
        "esta_abierto": esta_abierto,
    }


def clasificar_prioridad(texto: str) -> str:
    """
    Clasifica la prioridad de un mensaje según su contenido.
    Retorna: 'NORMAL', 'PRIORITARIO' o 'URGENTE'
    """
    texto_lower = texto.lower()

    # Palabras clave de urgencia postoperatoria
    palabras_urgentes = [
        "dificultad para respirar", "no puedo respirar", "sangrado excesivo",
        "sangra mucho", "perdí el conocimiento", "sin respuesta", "inconsciente",
        "urgencia", "urgente", "emergencia", "muy grave",
        # IMPORTANTE (también se tratan como urgente para notificar)
        "fiebre", "temperatura", "desmayo", "desmayé", "desmayos",
        "dolor excesivo", "dolor insoportable", "no cede el dolor",
        "drenaje aumentó", "mucho drenaje", "inflamación repentina",
        "inflamación súbita", "asimetría", "quemadura", "alergia",
        "dolor en la pierna", "dolor en las piernas", "hematoma",
        "herida abierta", "se abrió", "pus", "infección"
    ]

    # Palabras clave de solicitud de cita o control
    palabras_prioritarias = [
        "consulta", "cita", "agendar", "quiero venir", "quiero ir",
        "control", "postoperatorio", "postquirúrgico", "seguimiento",
        "primera vez", "cuándo puedo", "disponibilidad", "horario para",
        "me operé", "me operaron", "me hicieron", "ya me hicieron"
    ]

    for palabra in palabras_urgentes:
        if palabra in texto_lower:
            return "URGENTE"

    for palabra in palabras_prioritarias:
        if palabra in texto_lower:
            return "PRIORITARIO"

    return "NORMAL"


def buscar_en_knowledge(consulta: str) -> str:
    """Busca información relevante en los archivos de /knowledge."""
    resultados = []
    knowledge_dir = "knowledge"

    if not os.path.exists(knowledge_dir):
        return "No hay archivos de conocimiento disponibles."

    for archivo in os.listdir(knowledge_dir):
        ruta = os.path.join(knowledge_dir, archivo)
        if archivo.startswith(".") or not os.path.isfile(ruta):
            continue
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read()
                if consulta.lower() in contenido.lower():
                    resultados.append(f"[{archivo}]: {contenido[:500]}")
        except (UnicodeDecodeError, IOError):
            continue

    if resultados:
        return "\n---\n".join(resultados)
    return "No encontré información específica sobre eso en mis archivos."


def registrar_solicitud_consulta(telefono: str, tipo: str, procedimiento: str = "", nombre: str = "") -> dict:
    """
    Registra una solicitud de consulta para seguimiento del equipo.
    En producción esto podría guardar en DB o notificar por otro canal.
    """
    solicitud = {
        "telefono": telefono,
        "tipo": tipo,  # "primera_vez" o "control"
        "procedimiento": procedimiento,
        "nombre": nombre,
        "timestamp": datetime.now().isoformat(),
        "prioridad": "PRIORITARIO"
    }
    logger.info(f"[SOLICITUD DE CONSULTA] {solicitud}")
    return solicitud
