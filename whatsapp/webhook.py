"""Webhook server para receber mensagens WhatsApp via Evolution API.

Recebe webhooks do Evolution API quando chegam mensagens,
e encaminha para o agente atendente.

Uso:
    python -m whatsapp.webhook --port 5001
    ou via main.py: python main.py agente --port 5001
"""

import os

from dotenv import load_dotenv
from flask import Flask, request, jsonify

from agentes.atendente import handle_incoming_message
from scraper.utils import setup_logger

load_dotenv()
logger = setup_logger(__name__)

app = Flask(__name__)

# Instancia do Evolution API para filtrar webhooks
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "perceptudo-01")


@app.route("/webhook/messages", methods=["POST"])
def receive_message():
    """Recebe mensagens do Evolution API.

    Payload tipico do Evolution API:
    {
        "event": "messages.upsert",
        "instance": "PercepTudo",
        "data": {
            "key": {
                "remoteJid": "351912345678@s.whatsapp.net",
                "fromMe": false
            },
            "message": {
                "conversation": "Ola, vi o diagnostico..."
            },
            "messageTimestamp": "1234567890"
        }
    }
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
            # Ignorar mensagens de grupo
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
            # Ignorar mensagens sem texto (imagens, audio, stickers, etc.)
            logger.info("Mensagem sem texto de %s — ignorando", phone)
            return jsonify({"status": "ignored", "reason": "no text"}), 200

        logger.info("Webhook: mensagem de %s: %s", phone, text[:100])

        # Processar com o agente atendente
        response = handle_incoming_message(phone=phone, message=text)

        if response:
            return jsonify({"status": "ok", "responded": True}), 200
        else:
            return jsonify({"status": "ok", "responded": False}), 200

    except Exception as e:
        logger.error("Erro no webhook: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Endpoint de health check."""
    return jsonify({"status": "ok", "service": "perceptudo-agente"}), 200


def start_server(port: int = 5001, debug: bool = False) -> None:
    """Inicia o servidor webhook.

    Args:
        port: Porta do servidor (default: 5001).
        debug: Modo debug com hot reload (default: False).
    """
    logger.info("A iniciar servidor webhook na porta %d (debug=%s)...", port, debug)
    print(f"\n{'='*60}")
    print(f"  PERCEPTUDO — AGENTE ATENDENTE")
    print(f"  Webhook: http://0.0.0.0:{port}/webhook/messages")
    print(f"  Health:  http://0.0.0.0:{port}/health")
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
