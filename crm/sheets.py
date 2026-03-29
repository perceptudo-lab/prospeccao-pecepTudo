"""Interface com Google Sheets (CRM e historico de termos)."""

import json
import os
import tempfile
from datetime import datetime

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

from scraper.utils import setup_logger

load_dotenv()
logger = setup_logger(__name__)

# --- Cores para formatacao (RGB 0-1) ---
_DARK_GRAPHITE = {"red": 0.102, "green": 0.102, "blue": 0.180}
_WHITE = {"red": 1, "green": 1, "blue": 1}
_CLOUD_WARM = {"red": 0.961, "green": 0.949, "blue": 0.929}
_BORDER_GREY = {"red": 0.8, "green": 0.8, "blue": 0.8}

# --- Constantes de colunas (aba Leads) ---
COL_NOME = 1
COL_TELEFONE = 2
COL_CIDADE = 3
COL_SECTOR = 4
COL_RATING = 5
COL_REVIEWS = 6
COL_INSTAGRAM = 7
COL_WEBSITE = 8
COL_SCORE = 9
COL_ESTADO = 10
COL_DATA_CONTACTO = 11
COL_LINK_PDF = 12
COL_FOLLOWUP_1 = 13
COL_FOLLOWUP_2 = 14
COL_NOTAS = 15
COL_FOLLOWUP_3 = 16
COL_PROXIMO_FOLLOWUP = 17
COL_TOUCH_ACTUAL = 18

# --- Constantes de colunas (aba Termos) ---
COL_TERMO = 1
COL_TERMO_CIDADE = 2
COL_TERMO_DATA = 3
COL_TERMO_BRUTOS = 4
COL_TERMO_VALIDOS = 5

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS_LEADS = [
    "Nome", "Telefone", "Cidade", "Sector", "Rating", "Reviews",
    "Instagram", "Website", "Score", "Estado", "Data Contacto",
    "Link PDF", "Follow-up 1", "Follow-up 2", "Notas",
    "Follow-up 3", "Proximo Follow-up", "Touch Actual",
]

# --- Estados validos de leads ---
VALID_STATES = {
    "novo", "pronto_para_envio", "contactado",
    "followup_1", "followup_2", "followup_3",
    "respondeu", "frio", "removido", "agendado",
}

HEADERS_TERMOS = [
    "Termo", "Cidade", "Data", "Resultados Brutos", "Leads Validos",
]


def _get_client() -> gspread.Client:
    """Cria e retorna cliente gspread autenticado.

    Suporta dois modos:
    - GOOGLE_SERVICE_ACCOUNT_JSON aponta para ficheiro .json (local)
    - GOOGLE_SERVICE_ACCOUNT_DATA contem o JSON inline (Docker/VPS)
    """
    # Modo 1: JSON inline (para Docker/Easypanel)
    json_data = os.getenv("GOOGLE_SERVICE_ACCOUNT_DATA")
    if json_data:
        info = json.loads(json_data)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        return gspread.authorize(creds)

    # Modo 2: Ficheiro local
    creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_spreadsheet() -> gspread.Spreadsheet:
    """Retorna o spreadsheet configurado no .env."""
    client = _get_client()
    sheet_id = os.getenv("GOOGLE_SHEETS_ID")
    return client.open_by_key(sheet_id)


def _get_worksheet_leads() -> gspread.Worksheet:
    """Retorna a aba 'Leads'."""
    spreadsheet = _get_spreadsheet()
    try:
        return spreadsheet.worksheet("Leads")
    except gspread.exceptions.WorksheetNotFound:
        logger.info("Aba 'Leads' nao encontrada — a criar com headers")
        ws = spreadsheet.add_worksheet(title="Leads", rows=1000, cols=19)
        ws.append_row(HEADERS_LEADS, value_input_option="USER_ENTERED")
        return ws


def _get_worksheet_termos() -> gspread.Worksheet:
    """Retorna a aba 'Termos'."""
    spreadsheet = _get_spreadsheet()
    try:
        return spreadsheet.worksheet("Termos")
    except gspread.exceptions.WorksheetNotFound:
        logger.info("Aba 'Termos' nao encontrada — a criar com headers")
        ws = spreadsheet.add_worksheet(title="Termos", rows=500, cols=5)
        ws.append_row(HEADERS_TERMOS, value_input_option="USER_ENTERED")
        return ws


# =============================================
# Formatacao visual
# =============================================


def _thin_borders() -> dict:
    b = {"style": "SOLID", "colorStyle": {"rgbColor": _BORDER_GREY}}
    return {"top": b, "bottom": b, "left": b, "right": b}


def _repeat_cell(sheet_id: int, r1: int, r2: int, c1: int, c2: int, cell_fmt: dict) -> dict:
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": r1,
                "endRowIndex": r2,
                "startColumnIndex": c1,
                "endColumnIndex": c2,
            },
            "cell": {"userEnteredFormat": cell_fmt},
            "fields": "userEnteredFormat(" + ",".join(cell_fmt.keys()) + ")",
        }
    }


def _ensure_banding(sp: gspread.Spreadsheet, ws: gspread.Worksheet,
                     num_rows: int, num_cols: int) -> None:
    """Garante que o banding cobre todas as linhas de dados.

    Se ja existe banding, actualiza o range. Se nao, cria novo.
    """
    sheet_meta = sp.fetch_sheet_metadata()
    for s in sheet_meta["sheets"]:
        if s["properties"]["sheetId"] == ws.id:
            banded = s.get("bandedRanges", [])
            target_range = {
                "sheetId": ws.id,
                "startRowIndex": 1,
                "endRowIndex": num_rows,
                "startColumnIndex": 0,
                "endColumnIndex": num_cols,
            }
            if banded:
                # Actualizar range do banding existente
                sp.batch_update({"requests": [{
                    "updateBanding": {
                        "bandedRange": {
                            "bandedRangeId": banded[0]["bandedRangeId"],
                            "range": target_range,
                            "rowProperties": {
                                "firstBandColorStyle": {"rgbColor": _WHITE},
                                "secondBandColorStyle": {"rgbColor": _CLOUD_WARM},
                            },
                        },
                        "fields": "range,rowProperties",
                    }
                }]})
            else:
                # Criar novo banding
                sp.batch_update({"requests": [{
                    "addBanding": {
                        "bandedRange": {
                            "range": target_range,
                            "rowProperties": {
                                "firstBandColorStyle": {"rgbColor": _WHITE},
                                "secondBandColorStyle": {"rgbColor": _CLOUD_WARM},
                            },
                        }
                    }
                }]})
            break


def _format_new_lead_rows(ws: gspread.Worksheet, start_row: int, end_row: int) -> None:
    """Aplica formatacao as novas linhas de leads (borders, bold, alinhamento).

    start_row e end_row sao 0-indexed (row indices do Sheets API).
    """
    try:
        sp = _get_spreadsheet()
        sid = ws.id
        requests = [
            # Base: font size, borders, vertical align
            _repeat_cell(sid, start_row, end_row, 0, 19, {
                "textFormat": {"fontSize": 9},
                "verticalAlignment": "MIDDLE",
                "borders": _thin_borders(),
                "wrapStrategy": "CLIP",
            }),
            # Nome bold
            _repeat_cell(sid, start_row, end_row, 0, 1, {
                "textFormat": {"bold": True, "fontSize": 9},
            }),
            # Rating, Reviews, Score centrados
            _repeat_cell(sid, start_row, end_row, 4, 6, {
                "horizontalAlignment": "CENTER",
            }),
            _repeat_cell(sid, start_row, end_row, 8, 9, {
                "horizontalAlignment": "CENTER",
            }),
            # Estado centrado + bold
            _repeat_cell(sid, start_row, end_row, 9, 10, {
                "horizontalAlignment": "CENTER",
                "textFormat": {"bold": True, "fontSize": 9},
            }),
        ]
        sp.batch_update({"requests": requests})

        # Actualizar banding para cobrir todas as linhas
        _ensure_banding(sp, ws, end_row, 19)

    except Exception as e:
        logger.warning("Erro ao formatar novas linhas: %s", e)


def _format_new_termo_rows(ws: gspread.Worksheet, start_row: int, end_row: int) -> None:
    """Aplica formatacao as novas linhas de termos."""
    try:
        sp = _get_spreadsheet()
        sid = ws.id
        requests = [
            # Base
            _repeat_cell(sid, start_row, end_row, 0, 5, {
                "textFormat": {"fontSize": 9},
                "verticalAlignment": "MIDDLE",
                "borders": _thin_borders(),
                "wrapStrategy": "CLIP",
            }),
            # Termo bold
            _repeat_cell(sid, start_row, end_row, 0, 1, {
                "textFormat": {"bold": True, "fontSize": 9},
            }),
            # Colunas D, E centradas
            _repeat_cell(sid, start_row, end_row, 3, 5, {
                "horizontalAlignment": "CENTER",
            }),
        ]
        sp.batch_update({"requests": requests})

        # Actualizar banding
        _ensure_banding(sp, ws, end_row, 5)

    except Exception as e:
        logger.warning("Erro ao formatar novas linhas de termos: %s", e)


# =============================================
# Funcoes da aba LEADS
# =============================================


def get_contacted_phones() -> set[str]:
    """Retorna set de telefones ja registados no Sheets.

    Em caso de erro, retorna set vazio para nao bloquear o pipeline.
    """
    try:
        ws = _get_worksheet_leads()
        phones = ws.col_values(COL_TELEFONE)
        # Remover header
        phones = phones[1:] if phones else []
        # Normalizar: converter para string, adicionar + se comecar por 351
        normalized = set()
        for p in phones:
            p = str(p).strip()
            if not p:
                continue
            # Se veio como numero sem +, adicionar
            if p.startswith("351") and len(p) == 12:
                p = f"+{p}"
            elif not p.startswith("+") and len(p) == 9 and p.startswith("9"):
                p = f"+351{p}"
            normalized.add(p)
        result = normalized
        logger.info("Encontrados %d telefones ja registados no Sheets", len(result))
        return result
    except Exception as e:
        logger.warning("Erro ao ler telefones do Sheets: %s", e)
        return set()


def add_leads(leads: list[dict]) -> int:
    """Adiciona leads a aba 'Leads' em batch.

    Cada lead deve ter as keys: nome, telefone, cidade, sector,
    rating, reviews, instagram_url, website.
    Estado e definido como 'novo'.
    Retorna o numero de leads adicionados.
    """
    if not leads:
        logger.info("Nenhum lead para adicionar")
        return 0

    try:
        ws = _get_worksheet_leads()
        rows = []
        for lead in leads:
            row = [
                lead.get("nome", ""),
                lead.get("telefone", ""),
                lead.get("cidade", ""),
                lead.get("sector", ""),
                lead.get("rating", ""),
                lead.get("reviews", ""),
                lead.get("instagram_url", ""),
                lead.get("website", ""),
                "",  # Score (preenchido pela AI na Fase 2)
                "novo",  # Estado
                "",  # Data Contacto
                "",  # Link PDF
                "",  # Follow-up 1
                "",  # Follow-up 2
                "",  # Notas
                "",  # Follow-up 3
                "",  # Proximo Follow-up
                "",  # Touch Actual
            ]
            rows.append(row)

        # Descobrir onde vao ficar as novas linhas
        existing_rows = len(ws.get_all_values())
        ws.append_rows(rows, value_input_option="RAW")
        logger.info("Adicionados %d leads ao Sheets", len(rows))

        # Formatar as novas linhas (0-indexed)
        _format_new_lead_rows(ws, existing_rows, existing_rows + len(rows))

        return len(rows)
    except Exception as e:
        logger.error("Erro ao adicionar leads ao Sheets: %s", e)
        return 0


def update_lead_status(
    phone: str, status: str, extra_data: dict | None = None
) -> bool:
    """Actualiza o estado de um lead pelo telefone.

    extra_data permite actualizar campos adicionais.
    Keys aceites: score, data_contacto, link_pdf, followup_1, followup_2, notas, followup_3.
    """
    col_map = {
        "score": COL_SCORE,
        "data_contacto": COL_DATA_CONTACTO,
        "link_pdf": COL_LINK_PDF,
        "followup_1": COL_FOLLOWUP_1,
        "followup_2": COL_FOLLOWUP_2,
        "notas": COL_NOTAS,
        "followup_3": COL_FOLLOWUP_3,
        "data_followup_proximo": COL_PROXIMO_FOLLOWUP,
        "touch_actual": COL_TOUCH_ACTUAL,
    }

    try:
        ws = _get_worksheet_leads()
        phone = str(phone).strip()

        # Tentar encontrar pelo telefone exacto, sem +, e so digitos
        cell = ws.find(phone, in_column=COL_TELEFONE)
        if not cell and phone.startswith("+"):
            cell = ws.find(phone[1:], in_column=COL_TELEFONE)
        if not cell:
            # Procurar pelos ultimos 9 digitos nos valores da coluna
            digits = phone.replace("+", "").replace(" ", "")[-9:]
            all_phones = ws.col_values(COL_TELEFONE)
            for row_idx, p in enumerate(all_phones, 1):
                if digits in p.replace(" ", "").replace("+", ""):
                    cell = type("Cell", (), {"row": row_idx})()
                    break
        if not cell:
            logger.warning("Telefone %s nao encontrado no Sheets", phone)
            return False

        ws.update_cell(cell.row, COL_ESTADO, status)
        logger.info("Lead %s actualizado para estado '%s'", phone, status)

        if extra_data:
            for key, value in extra_data.items():
                col = col_map.get(key)
                if col:
                    ws.update_cell(cell.row, col, value)

        return True
    except Exception as e:
        logger.error("Erro ao actualizar lead %s: %s", phone, e)
        return False


def get_leads_by_sector_city(sector: str, cidade: str, status: str = "novo") -> list[dict]:
    """Retorna leads filtrados por sector, cidade e estado.

    Args:
        sector: Sector/nicho (ex: 'contabilistas').
        cidade: Cidade (ex: 'Leiria').
        status: Estado dos leads a buscar (default: 'novo').

    Returns:
        Lista de dicts com dados do lead.
    """
    try:
        ws = _get_worksheet_leads()
        records = ws.get_all_records()
        sector_lower = sector.strip().lower()
        cidade_lower = cidade.strip().lower()

        filtered = [
            r for r in records
            if r.get("Sector", "").strip().lower() == sector_lower
            and r.get("Cidade", "").strip().lower() == cidade_lower
            and r.get("Estado", "").strip().lower() == status.lower()
        ]
        logger.info(
            "Encontrados %d leads '%s' em '%s' com estado '%s'",
            len(filtered), sector, cidade, status,
        )
        return filtered
    except Exception as e:
        logger.error("Erro ao buscar leads: %s", e)
        return []


def get_leads_by_statuses(statuses: list[str]) -> list[dict]:
    """Retorna leads que estejam em qualquer um dos estados indicados.

    Args:
        statuses: Lista de estados (ex: ['contactado', 'followup_1']).

    Returns:
        Lista de dicts com dados do lead.
    """
    try:
        ws = _get_worksheet_leads()
        records = ws.get_all_records()
        statuses_lower = {s.strip().lower() for s in statuses}
        filtered = [
            r for r in records
            if r.get("Estado", "").strip().lower() in statuses_lower
        ]
        logger.info(
            "Encontrados %d leads com estados %s", len(filtered), statuses,
        )
        return filtered
    except Exception as e:
        logger.error("Erro ao buscar leads por estados %s: %s", statuses, e)
        return []


def get_leads_needing_followup(today_str: str) -> list[dict]:
    """Retorna leads que precisam de follow-up hoje ou antes.

    Filtra leads com estado em {contactado, followup_1, followup_2, followup_3}
    e com 'Proximo Follow-up' <= today_str (formato ISO: YYYY-MM-DD).

    Args:
        today_str: Data de hoje em formato ISO (ex: '2026-03-29').

    Returns:
        Lista de dicts com dados do lead.
    """
    try:
        ws = _get_worksheet_leads()
        records = ws.get_all_records()
        followup_states = {"contactado", "followup_1", "followup_2", "followup_3"}
        filtered = []
        for r in records:
            estado = r.get("Estado", "").strip().lower()
            proximo = str(r.get("Proximo Follow-up", "")).strip()
            if estado in followup_states and proximo and proximo <= today_str:
                filtered.append(r)
        logger.info(
            "Encontrados %d leads a precisar de follow-up (ate %s)",
            len(filtered), today_str,
        )
        return filtered
    except Exception as e:
        logger.error("Erro ao buscar leads para follow-up: %s", e)
        return []


def get_leads_by_status(status: str) -> list[dict]:
    """Retorna leads filtrados por estado.

    Retorna lista de dicts com keys correspondentes aos headers.
    """
    try:
        ws = _get_worksheet_leads()
        records = ws.get_all_records()
        filtered = [r for r in records if r.get("Estado") == status]
        logger.info("Encontrados %d leads com estado '%s'", len(filtered), status)
        return filtered
    except Exception as e:
        logger.error("Erro ao buscar leads por estado '%s': %s", status, e)
        return []


# =============================================
# Funcoes da aba TERMOS
# =============================================


def is_term_used(query: str, cidade: str) -> bool:
    """Verifica se o combo query+cidade ja foi pesquisado.

    Comparacao case-insensitive. Usa col_values para evitar
    problemas com headers duplicados.
    """
    try:
        ws = _get_worksheet_termos()
        termos = ws.col_values(COL_TERMO)[1:]  # Skip header
        cidades = ws.col_values(COL_TERMO_CIDADE)[1:]  # Skip header

        query_lower = query.strip().lower()
        cidade_lower = cidade.strip().lower()

        for t, c in zip(termos, cidades):
            if t.strip().lower() == query_lower and c.strip().lower() == cidade_lower:
                logger.warning(
                    "Termo '%s' em '%s' ja foi utilizado anteriormente", query, cidade
                )
                return True
        return False
    except Exception as e:
        logger.warning("Erro ao verificar termo: %s", e)
        return False  # Em caso de erro, permite pesquisar


def register_term(query: str, cidade: str, brutos: int, validos: int) -> None:
    """Regista um termo de pesquisa na aba 'Termos'."""
    try:
        ws = _get_worksheet_termos()
        row = [
            query.strip(),
            cidade.strip(),
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            brutos,
            validos,
        ]
        existing_rows = len(ws.get_all_values())
        ws.append_row(row, value_input_option="USER_ENTERED")
        logger.info(
            "Termo registado: '%s' em '%s' — %d brutos, %d validos",
            query, cidade, brutos, validos,
        )

        # Formatar a nova linha
        _format_new_termo_rows(ws, existing_rows, existing_rows + 1)

    except Exception as e:
        logger.error("Erro ao registar termo: %s", e)
