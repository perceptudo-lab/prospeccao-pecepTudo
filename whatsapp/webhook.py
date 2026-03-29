"""Webhook server para receber mensagens WhatsApp via Evolution API.

Recebe webhooks do Evolution API quando chegam mensagens,
e encaminha para o agente atendente.

Buffer de mensagens: quando um lead envia varias mensagens seguidas,
o sistema espera 8 segundos de silencio antes de processar tudo junto.

Uso:
    python -m whatsapp.webhook --port 5001
    ou via main.py: python main.py agente --port 5001
"""

import os
import threading

from dotenv import load_dotenv
from flask import Flask, request, jsonify

from agentes.atendente import handle_incoming_message
from scraper.utils import setup_logger

load_dotenv()
logger = setup_logger(__name__)

app = Flask(__name__)

# Tempo de espera por mais mensagens antes de processar (segundos)
BUFFER_WAIT = float(os.getenv("BUFFER_WAIT_SEG", "15"))

# Buffer de mensagens por telefone
# {phone: {"messages": ["msg1", "msg2"], "timer": threading.Timer}}
_message_buffers: dict[str, dict] = {}
_buffer_lock = threading.Lock()


def _flush_buffer(phone: str) -> None:
    """Junta mensagens do buffer e processa com o agente."""
    with _buffer_lock:
        buffer = _message_buffers.pop(phone, None)

    if not buffer or not buffer["messages"]:
        return

    # Juntar todas as mensagens numa so (separadas por newline)
    combined = "\n".join(buffer["messages"])
    msg_count = len(buffer["messages"])

    logger.info(
        "Buffer flush para %s: %d mensagem(ns) combinadas",
        phone, msg_count,
    )

    # Processar em background
    thread = threading.Thread(
        target=handle_incoming_message,
        args=(phone, combined),
        daemon=True,
    )
    thread.start()


def _buffer_message(phone: str, text: str) -> None:
    """Adiciona mensagem ao buffer e reinicia o timer."""
    with _buffer_lock:
        if phone not in _message_buffers:
            _message_buffers[phone] = {"messages": [], "timer": None}

        buf = _message_buffers[phone]

        # Cancelar timer anterior
        if buf["timer"] is not None:
            buf["timer"].cancel()

        # Adicionar mensagem
        buf["messages"].append(text)

        # Novo timer
        timer = threading.Timer(BUFFER_WAIT, _flush_buffer, args=(phone,))
        timer.daemon = True
        timer.start()
        buf["timer"] = timer

    logger.info(
        "Buffer: %s tem %d msg(s), a esperar %.0fs por mais...",
        phone, len(buf["messages"]), BUFFER_WAIT,
    )


@app.route("/webhook/messages", methods=["POST"])
def receive_message():
    """Recebe mensagens do Evolution API.

    Em vez de processar imediatamente, adiciona ao buffer.
    Se o lead enviar varias mensagens seguidas, espera 8s de
    silencio antes de juntar tudo e processar uma unica vez.
    """
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"status": "ignored", "reason": "no payload"}), 200

        event = payload.get("event", "")

        # Apenas processar mensagens recebidas
        if event != "messages.upsert":
            return jsonify({"status": "ignored", "reason": f"event: {event}"}), 200

        data = payload.get("data", {})
        key = data.get("key", {})

        # Ignorar mensagens enviadas por nos
        if key.get("fromMe", True):
            return jsonify({"status": "ignored", "reason": "fromMe"}), 200

        # Extrair telefone (remover @s.whatsapp.net)
        remote_jid = key.get("remoteJid", "")
        if not remote_jid or "@g.us" in remote_jid:
            return jsonify({"status": "ignored", "reason": "group or empty"}), 200

        phone = remote_jid.split("@")[0]

        # Extrair texto da mensagem
        message_obj = data.get("message", {})
        text = (
            message_obj.get("conversation")
            or message_obj.get("extendedTextMessage", {}).get("text")
            or ""
        )

        if not text.strip():
            logger.info("Mensagem sem texto de %s — ignorando", phone)
            return jsonify({"status": "ignored", "reason": "no text"}), 200

        logger.info("Webhook: mensagem de %s: %s", phone, text[:100])

        # Adicionar ao buffer (processa apos 8s de silencio)
        _buffer_message(phone, text.strip())

        return jsonify({"status": "ok", "buffered": True}), 200

    except Exception as e:
        logger.error("Erro no webhook: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Endpoint de health check."""
    return jsonify({"status": "ok", "service": "perceptudo-agente"}), 200


def start_server(port: int = 5001, debug: bool = False) -> None:
    """Inicia o servidor webhook."""
    logger.info("A iniciar servidor webhook na porta %d (debug=%s)...", port, debug)
    print(f"\n{'='*60}")
    print(f"  PERCEPTUDO — AGENTE ATENDENTE")
    print(f"  Webhook: http://0.0.0.0:{port}/webhook/messages")
    print(f"  Health:  http://0.0.0.0:{port}/health")
    print(f"  Buffer:  {BUFFER_WAIT}s de espera por mais mensagens")
    print(f"  Modo:    {'debug (hot reload)' if debug else 'producao'}")
    print(f"  Horario: 24/7")
    print(f"{'='*60}\n")

    app.run(host="0.0.0.0", port=port, debug=debug)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PercepTudo Webhook Server")
    parser.add_argument("--port", type=int, default=5001, help="Porta (default: 5001)")
    parser.add_argument("--debug", action="store_true", help="Modo debug com hot reload")
    args = parser.parse_args()

    start_server(port=args.port, debug=args.debug)
