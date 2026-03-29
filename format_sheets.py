"""Formata visualmente a planilha Google Sheets (Leads + Termos).

Usa batch_update nativo para minimizar chamadas API.
"""

import os
import time
import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# --- Cores (RGB 0-1) ---
DARK_GRAPHITE = {"red": 0.102, "green": 0.102, "blue": 0.180}
WHITE = {"red": 1, "green": 1, "blue": 1}
CLOUD_WARM = {"red": 0.961, "green": 0.949, "blue": 0.929}
BORDER_GREY = {"red": 0.8, "green": 0.8, "blue": 0.8}


def get_spreadsheet() -> gspread.Spreadsheet:
    creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet_id = os.getenv("GOOGLE_SHEETS_ID")
    return client.open_by_key(sheet_id)


def _border(style="SOLID"):
    return {"style": style, "colorStyle": {"rgbColor": BORDER_GREY}}


def _thin_borders():
    b = _border()
    return {"top": b, "bottom": b, "left": b, "right": b}


def _repeat_cell(sheet_id, r1, r2, c1, c2, cell_fmt):
    """Helper para repeatCell request."""
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


def _col_width(sheet_id, col_idx, pixels):
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "startIndex": col_idx,
                "endIndex": col_idx + 1,
            },
            "properties": {"pixelSize": pixels},
            "fields": "pixelSize",
        }
    }


def _row_height(sheet_id, row_idx, pixels):
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "ROWS",
                "startIndex": row_idx,
                "endIndex": row_idx + 1,
            },
            "properties": {"pixelSize": pixels},
            "fields": "pixelSize",
        }
    }


def _banding(sheet_id, num_rows, num_cols):
    """Alternating colors (banded range) — one API call for all rows."""
    return {
        "addBanding": {
            "bandedRange": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "endRowIndex": num_rows,
                    "startColumnIndex": 0,
                    "endColumnIndex": num_cols,
                },
                "rowProperties": {
                    "firstBandColorStyle": {"rgbColor": WHITE},
                    "secondBandColorStyle": {"rgbColor": CLOUD_WARM},
                },
            }
        }
    }


def _conditional_format(sheet_id, state, bg_color, fg_color):
    return {
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "startColumnIndex": 9,
                    "endColumnIndex": 10,
                }],
                "booleanRule": {
                    "condition": {
                        "type": "TEXT_EQ",
                        "values": [{"userEnteredValue": state}],
                    },
                    "format": {
                        "backgroundColor": bg_color,
                        "textFormat": {
                            "foregroundColor": fg_color,
                            "bold": True,
                        },
                    },
                },
            },
            "index": 0,
        }
    }


def _remove_existing_banding(sp: gspread.Spreadsheet, ws: gspread.Worksheet):
    """Remove banded ranges existentes para poder re-aplicar."""
    sheet_meta = sp.fetch_sheet_metadata()
    for s in sheet_meta["sheets"]:
        if s["properties"]["sheetId"] == ws.id:
            banded = s.get("bandedRanges", [])
            if banded:
                reqs = [{"deleteBanding": {"bandedRangeId": b["bandedRangeId"]}} for b in banded]
                sp.batch_update({"requests": reqs})


def format_leads(sp: gspread.Spreadsheet, ws: gspread.Worksheet):
    """Formata a aba Leads com um unico batch_update."""
    print("  Formatando aba Leads...")

    num_rows = len(ws.get_all_values())
    if num_rows < 2:
        print("  Aba Leads vazia, a saltar.")
        return

    _remove_existing_banding(sp, ws)

    sid = ws.id
    requests = []

    # 1. Freeze header row + coluna Nome
    requests.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": sid,
                "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 1},
            },
            "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
        }
    })

    # 2. Header row height
    requests.append(_row_height(sid, 0, 42))

    # 3. Header style: dark background, white bold text, centered
    requests.append(_repeat_cell(sid, 0, 1, 0, 16, {
        "backgroundColor": DARK_GRAPHITE,
        "textFormat": {"bold": True, "fontSize": 10, "foregroundColorStyle": {"rgbColor": WHITE}},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
        "borders": _thin_borders(),
        "wrapStrategy": "WRAP",
    }))

    # 4. Column widths
    widths = [250, 140, 100, 160, 65, 75, 220, 220, 60, 120, 120, 180, 110, 110, 180, 200]
    for i, w in enumerate(widths):
        requests.append(_col_width(sid, i, w))

    # 5. Data rows: base format
    requests.append(_repeat_cell(sid, 1, num_rows, 0, 16, {
        "textFormat": {"fontSize": 9},
        "verticalAlignment": "MIDDLE",
        "borders": _thin_borders(),
        "wrapStrategy": "CLIP",
    }))

    # 6. Banded rows (zebra) — single request
    requests.append(_banding(sid, num_rows, 16))

    # 7. Nome column: bold
    requests.append(_repeat_cell(sid, 1, num_rows, 0, 1, {
        "textFormat": {"bold": True, "fontSize": 9},
    }))

    # 8. Rating, Reviews, Score: centered
    for col in [4, 5, 8]:
        requests.append(_repeat_cell(sid, 1, num_rows, col, col + 1, {
            "horizontalAlignment": "CENTER",
        }))

    # 9. Estado column: centered + bold
    requests.append(_repeat_cell(sid, 1, num_rows, 9, 10, {
        "horizontalAlignment": "CENTER",
        "textFormat": {"bold": True, "fontSize": 9},
    }))

    # 10. Conditional formatting for states
    state_colors = [
        ("novo",
         {"red": 0.886, "green": 0.937, "blue": 0.992},
         {"red": 0.106, "green": 0.369, "blue": 0.667}),
        ("pronto_para_envio",
         {"red": 0.898, "green": 0.957, "blue": 0.906},
         {"red": 0.106, "green": 0.494, "blue": 0.204}),
        ("contactado",
         {"red": 0.925, "green": 0.898, "blue": 0.976},
         {"red": 0.361, "green": 0.122, "blue": 0.710}),
        ("respondeu",
         {"red": 0.820, "green": 0.976, "blue": 0.898},
         {"red": 0.0, "green": 0.502, "blue": 0.314}),
        ("followup_1",
         {"red": 1.0, "green": 0.949, "blue": 0.8},
         {"red": 0.749, "green": 0.561, "blue": 0.0}),
        ("followup_2",
         {"red": 1.0, "green": 0.902, "blue": 0.702},
         {"red": 0.600, "green": 0.400, "blue": 0.0}),
        ("frio",
         {"red": 0.941, "green": 0.941, "blue": 0.941},
         {"red": 0.502, "green": 0.502, "blue": 0.502}),
        ("removido",
         {"red": 0.988, "green": 0.898, "blue": 0.898},
         {"red": 0.710, "green": 0.153, "blue": 0.153}),
    ]
    for state, bg, fg in state_colors:
        requests.append(_conditional_format(sid, state, bg, fg))

    # Execute all in one batch
    sp.batch_update({"requests": requests})
    print(f"  ✓ Aba Leads formatada ({num_rows - 1} leads)")


def format_termos(sp: gspread.Spreadsheet, ws: gspread.Worksheet):
    """Formata a aba Termos com um unico batch_update."""
    print("  Formatando aba Termos...")

    num_rows = len(ws.get_all_values())
    if num_rows < 2:
        print("  Aba Termos vazia, a saltar.")
        return

    _remove_existing_banding(sp, ws)

    sid = ws.id
    requests = []

    # Freeze header
    requests.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": sid,
                "gridProperties": {"frozenRowCount": 1},
            },
            "fields": "gridProperties.frozenRowCount",
        }
    })

    # Header height
    requests.append(_row_height(sid, 0, 42))

    # Header style
    requests.append(_repeat_cell(sid, 0, 1, 0, 5, {
        "backgroundColor": DARK_GRAPHITE,
        "textFormat": {"bold": True, "fontSize": 10, "foregroundColorStyle": {"rgbColor": WHITE}},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
        "borders": _thin_borders(),
        "wrapStrategy": "WRAP",
    }))

    # Column widths
    termos_widths = [220, 120, 160, 130, 120]
    for i, w in enumerate(termos_widths):
        requests.append(_col_width(sid, i, w))

    # Data format
    requests.append(_repeat_cell(sid, 1, num_rows, 0, 5, {
        "textFormat": {"fontSize": 9},
        "verticalAlignment": "MIDDLE",
        "borders": _thin_borders(),
        "wrapStrategy": "CLIP",
    }))

    # Banded rows
    requests.append(_banding(sid, num_rows, 5))

    # Termo column bold
    requests.append(_repeat_cell(sid, 1, num_rows, 0, 1, {
        "textFormat": {"bold": True, "fontSize": 9},
    }))

    # Center numeric columns (D, E)
    requests.append(_repeat_cell(sid, 1, num_rows, 3, 5, {
        "horizontalAlignment": "CENTER",
    }))

    sp.batch_update({"requests": requests})
    print(f"  ✓ Aba Termos formatada ({num_rows - 1} registos)")


def main():
    print("=" * 50)
    print("  FORMATACAO GOOGLE SHEETS")
    print("=" * 50)
    print()

    sp = get_spreadsheet()

    try:
        ws_leads = sp.worksheet("Leads")
        format_leads(sp, ws_leads)
    except Exception as e:
        print(f"  Erro na aba Leads: {e}")

    # Small pause between sheets
    time.sleep(2)

    try:
        ws_termos = sp.worksheet("Termos")
        format_termos(sp, ws_termos)
    except Exception as e:
        print(f"  Erro na aba Termos: {e}")

    print()
    print("=" * 50)
    print("  CONCLUIDO")
    print("=" * 50)


if __name__ == "__main__":
    main()
