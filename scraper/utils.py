"""Utilitarios partilhados pelo pipeline de scraping."""

import logging
import re
import unicodedata


def setup_logger(name: str) -> logging.Logger:
    """Configura e retorna um logger com formato padrao."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def normalize_phone(phone: str) -> str:
    """Normaliza telefone portugues para formato +351XXXXXXXXX.

    Aceita formatos como:
    - 912345678
    - +351912345678
    - 351 912 345 678
    - +351 912 345 678
    - 00351912345678
    """
    digits = re.sub(r"\D", "", phone)

    # Remover prefixo 00 (formato internacional)
    if digits.startswith("00"):
        digits = digits[2:]

    # Remover prefixo 351 se presente
    if digits.startswith("351") and len(digits) == 12:
        digits = digits[3:]

    # Neste ponto devemos ter 9 digitos
    if len(digits) == 9 and digits.startswith("9"):
        return f"+351{digits}"

    return phone  # Retorna original se nao conseguir normalizar


def is_portuguese_mobile(phone: str) -> bool:
    """Verifica se o telefone e um telemovel portugues (9xx).

    Normaliza antes de validar.
    """
    normalized = normalize_phone(phone)
    return bool(re.match(r"^\+3519\d{8}$", normalized))


def generate_slug(name: str) -> str:
    """Gera slug a partir do nome do negocio.

    Exemplo: 'Restaurante O Velho' -> 'restaurante-o-velho'
    """
    # Remover acentos
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_text = nfkd.encode("ASCII", "ignore").decode("ASCII")

    # Lowercase e substituir espacos/caracteres especiais por hifens
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower())

    # Remover hifens no inicio e fim
    slug = slug.strip("-")

    return slug
