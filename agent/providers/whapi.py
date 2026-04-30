import os
import logging
import httpx
from fastapi import Request
from agent.providers.base import ProveedorWhatsApp, MensajeEntrante

logger = logging.getLogger("agentkit")


class ProveedorWhapi(ProveedorWhatsApp):
    """Proveedor de WhatsApp usando Whapi.cloud."""

    def __init__(self):
        self.url_envio = "https://gate.whapi.cloud/messages/text"

    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        """Parsea el payload de Whapi.cloud."""
        body = await request.json()
        mensajes = []
        for msg in body.get("messages", []):
            mensajes.append(MensajeEntrante(
                telefono=msg.get("chat_id", ""),
                texto=msg.get("text", {}).get("body", ""),
                mensaje_id=msg.get("id", ""),
                es_propio=msg.get("from_me", False),
            ))
        return mensajes

    async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
        """Envía mensaje via Whapi.cloud."""
        token = os.getenv("WHAPI_TOKEN")
        if not token:
            logger.warning("WHAPI_TOKEN no configurado — mensaje no enviado")
            return False
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(
                self.url_envio,
                json={"to": telefono.replace("@s.whatsapp.net", ""), "body": mensaje},
                headers=headers,
            )
            exitoso = r.status_code in (200, 201)
            if not exitoso:
                logger.error(f"Error Whapi: {r.status_code} — {r.text}")
            else:
                logger.debug(f"Whapi OK {r.status_code}: {r.text[:100]}")
            return exitoso
