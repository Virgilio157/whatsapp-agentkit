import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

from agent.brain import generar_respuesta
from agent.memory import inicializar_db, guardar_mensaje, obtener_historial
from agent.providers import obtener_proveedor
from agent.tools import clasificar_prioridad

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
log_level = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger("agentkit")

proveedor = None
PORT = int(os.getenv("PORT", 8000))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global proveedor
    await inicializar_db()
    proveedor = obtener_proveedor()
    logger.info("Base de datos inicializada")
    logger.info(f"Servidor AgentKit corriendo en puerto {PORT}")
    logger.info(f"Proveedor de WhatsApp: {proveedor.__class__.__name__}")

    # Diagnóstico de variables de entorno al arrancar
    whapi_token = os.getenv("WHAPI_TOKEN", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    logger.info(f"[ENV] WHAPI_TOKEN: {'OK (' + whapi_token[:6] + '...)' if whapi_token else 'FALTA — no configurado'}")
    logger.info(f"[ENV] ANTHROPIC_API_KEY: {'OK (' + anthropic_key[:8] + '...)' if anthropic_key else 'FALTA — no configurado'}")
    logger.info(f"[ENV] WHATSAPP_PROVIDER: {os.getenv('WHATSAPP_PROVIDER', 'no configurado')}")
    logger.info(f"[ENV] ENVIRONMENT: {os.getenv('ENVIRONMENT', 'no configurado')}")
    yield


app = FastAPI(
    title="Asistente Dr. Virgilio — WhatsApp AI",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def health_check():
    return {"status": "ok", "service": "Asistente Dr. Virgilio"}


@app.get("/health")
async def health_detail():
    """Diagnóstico: muestra qué variables de entorno están configuradas."""
    whapi_token = os.getenv("WHAPI_TOKEN", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    return {
        "status": "ok",
        "env": {
            "WHAPI_TOKEN": f"OK ({whapi_token[:6]}...)" if whapi_token else "FALTA",
            "ANTHROPIC_API_KEY": f"OK ({anthropic_key[:8]}...)" if anthropic_key else "FALTA",
            "WHATSAPP_PROVIDER": os.getenv("WHATSAPP_PROVIDER", "FALTA"),
            "ENVIRONMENT": os.getenv("ENVIRONMENT", "FALTA"),
            "PORT": os.getenv("PORT", "FALTA"),
        }
    }


@app.get("/webhook")
async def webhook_verificacion(request: Request):
    resultado = await proveedor.validar_webhook(request)
    if resultado is not None:
        return PlainTextResponse(str(resultado))
    return {"status": "ok"}


@app.post("/webhook")
async def webhook_handler(request: Request):
    """
    Recibe mensajes de WhatsApp, genera respuesta con Claude y la envía.
    Clasifica cada mensaje por prioridad (NORMAL, PRIORITARIO, URGENTE).
    """
    try:
        mensajes = await proveedor.parsear_webhook(request)

        for msg in mensajes:
            if msg.es_propio or not msg.texto:
                continue

            logger.info(f"Mensaje de {msg.telefono}: {msg.texto}")

            # Clasificar prioridad antes de procesar
            prioridad = clasificar_prioridad(msg.texto)
            if prioridad == "URGENTE":
                logger.warning(f"[URGENTE] Mensaje de {msg.telefono}: {msg.texto}")
            elif prioridad == "PRIORITARIO":
                logger.info(f"[PRIORITARIO] Solicitud de {msg.telefono}")

            historial = await obtener_historial(msg.telefono)
            respuesta = await generar_respuesta(msg.texto, historial)

            await guardar_mensaje(msg.telefono, "user", msg.texto)
            await guardar_mensaje(msg.telefono, "assistant", respuesta)

            await proveedor.enviar_mensaje(msg.telefono, respuesta)

            logger.info(f"Respuesta a {msg.telefono} [{prioridad}]: {respuesta[:80]}...")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))
