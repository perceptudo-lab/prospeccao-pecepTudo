"""Envio de mensagens e PDFs via Evolution API (WhatsApp)."""

import base64
import os
import random
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from scraper.utils import setup_logger

load_dotenv()
logger = setup_logger(__name__)


def _get_config() -> dict:
    """Retorna configuracao da Evolution API."""
    url = os.getenv("EVOLUTION_API_URL", "http://localhost:8080")
    api_key = os.getenv("EVOLUTION_API_KEY", "")
    instance = os.getenv("EVOLUTION_INSTANCE", "perceptudo-01")

    if not api_key:
        raise ValueError("EVOLUTION_API_KEY nao definida no .env")

    return {
        "base_url": url.rstrip("/"),
        "api_key": api_key,
        "instance": instance,
    }


def _format_phone_for_whatsapp(phone: str) -> str:
    """Formata telefone para o formato WhatsApp (sem + nem espacos).

    Exemplo: '+351912345678' -> '351912345678'
    """
    return str(phone).replace("+", "").replace(" ", "").replace("-", "")


def send_text(phone: str, message: str) -> bool:
    """Envia mensagem de texto via WhatsApp.

    Args:
        phone: Telefone no formato +351XXXXXXXXX.
        message: Texto da mensagem.

    Returns:
        True se enviou com sucesso, False caso contrario.
    """
    try:
        config = _get_config()
        wa_phone = _format_phone_for_whatsapp(phone)

        url = f"{config['base_url']}/message/sendText/{config['instance']}"
        headers = {
            "apikey": config["api_key"],
            "Content-Type": "application/json",
        }
        payload = {
            "number": wa_phone,
            "text": message,
        }

        response = requests.post(url, json=payload, headers=headers, timeout=30)

        if response.status_code in (200, 201):
            logger.info("Texto enviado para %s", phone)
            return True
        else:
            logger.error(
                "Erro ao enviar texto para %s: %s %s",
                phone, response.status_code, response.text[:200],
            )
            return False

    except Exception as e:
        logger.error("Erro ao enviar texto para %s: %s", phone, e)
        return False


def send_pdf(phone: str, pdf_path: str, filename: str = "diagnostico.pdf") -> bool:
    """Envia PDF via WhatsApp.

    Args:
        phone: Telefone no formato +351XXXXXXXXX.
        pdf_path: Caminho para o ficheiro PDF.
        filename: Nome do ficheiro que o destinatario ve.

    Returns:
        True se enviou com sucesso, False caso contrario.
    """
    try:
        config = _get_config()
        wa_phone = _format_phone_for_whatsapp(phone)

        # Resolver path absoluto e verificar existencia
        pdf_file = Path(pdf_path).resolve()
        if not pdf_file.exists():
            logger.error("PDF nao encontrado: %s", pdf_file)
            return False

        with open(pdf_file, "rb") as f:
            pdf_base64 = base64.b64encode(f.read()).decode("utf-8")

        url = f"{config['base_url']}/message/sendMedia/{config['instance']}"
        headers = {
            "apikey": config["api_key"],
            "Content-Type": "application/json",
        }
        payload = {
            "number": wa_phone,
            "mediatype": "document",
            "mimetype": "application/pdf",
            "caption": f"Diagnostico PercepTudo",
            "media": pdf_base64,
            "fileName": filename,
        }

        response = requests.post(url, json=payload, headers=headers, timeout=60)

        if response.status_code in (200, 201):
            logger.info("PDF enviado para %s: %s", phone, filename)
            return True
        else:
            logger.error(
                "Erro ao enviar PDF para %s: %s %s",
                phone, response.status_code, response.text[:200],
            )
            return False

    except Exception as e:
        logger.error("Erro ao enviar PDF para %s: %s", phone, e)
        return False


def check_is_whatsapp(phone: str) -> bool:
    """Verifica se o numero existe no WhatsApp via Evolution API.

    Args:
        phone: Telefone no formato +351XXXXXXXXX.

    Returns:
        True se o numero esta no WhatsApp, False caso contrario.
    """
    try:
        config = _get_config()
        wa_phone = _format_phone_for_whatsapp(phone)

        url = f"{config['base_url']}/chat/whatsappNumbers/{config['instance']}"
        headers = {
            "apikey": config["api_key"],
            "Content-Type": "application/json",
        }
        payload = {"numbers": [wa_phone]}

        response = requests.post(url, json=payload, headers=headers, timeout=15)

        if response.status_code in (200, 201):
            data = response.json()
            # Evolution API retorna lista de resultados
            if isinstance(data, list) and data:
                return data[0].get("exists", False)
            elif isinstance(data, dict):
                results = data.get("result", data.get("data", []))
                if isinstance(results, list) and results:
                    return results[0].get("exists", False)
        return False

    except Exception as e:
        logger.warning("Erro ao verificar WhatsApp para %s: %s", phone, e)
        return True  # Em caso de erro, assume que existe (nao bloqueia envio)


def send_lead_message(
    phone: str, message: str, pdf_path: str | None = None
) -> bool:
    """Envia mensagem a um lead: texto + pausa + PDF (opcional).

    Args:
        phone: Telefone do lead.
        message: Mensagem personalizada de WhatsApp.
        pdf_path: Caminho para o PDF. Se None, envia so texto (follow-ups).

    Returns:
        True se enviou com sucesso.
    """
    logger.info("A enviar mensagem para %s...", phone)

    # 1. Enviar texto
    text_ok = send_text(phone, message)
    if not text_ok:
        logger.error("Falha ao enviar texto para %s", phone)
        return False

    # 2. Enviar PDF se fornecido (touch 1 apenas)
    if pdf_path:
        delay = random.randint(2, 5)
        logger.info("A aguardar %ds antes de enviar PDF...", delay)
        time.sleep(delay)

        pdf_ok = send_pdf(phone, pdf_path)
        if not pdf_ok:
            logger.error("Falha ao enviar PDF para %s", phone)
            return False

    logger.info("Mensagem enviada para %s", phone)
    return True
