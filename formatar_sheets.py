"""Formata o Google Sheets para ficar visualmente agradavel e organizado."""

import sys
import os

os.chdir('/Users/sirvictoroliveira007/Desktop/Projetos-Gerais/percepTudo/perceptudo-prospector')
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv('.env')

from crm.sheets import _get_spreadsheet

print("A formatar o Sheets...")

spreadsheet = _get_spreadsheet()
ws = spreadsheet.worksheet("Leads")
sheet_id = ws.id

# Cores PercepTudo
PURPLE = {"red": 0.482, "green": 0.184, "blue": 0.949, "alpha": 1}       # #7B2FF2
DARK_BG = {"red": 0.102, "green": 0.102, "blue": 0.180, "alpha": 1}      # #1A1A2E
WHITE = {"red": 1, "green": 1, "blue": 1, "alpha": 1}
LIGHT_BG = {"red": 0.961, "green": 0.949, "blue": 0.929, "alpha": 1}     # #F5F2ED
LIGHT_PURPLE = {"red": 0.918, "green": 0.878, "blue": 0.988, "alpha": 1} # light purple for alternating
LIGHT_GREY = {"red": 0.95, "green": 0.95, "blue": 0.95, "alpha": 1}
GREEN = {"red": 0, "green": 0.898, "blue": 0.627, "alpha": 1}            # #00E5A0
AMBER = {"red": 0.949, "green": 0.663, "blue": 0, "alpha": 1}            # #F2A900

# Larguras das colunas (pixels)
COL_WIDTHS = {
    0: 220,   # A - Nome
    1: 140,   # B - Telefone
    2: 110,   # C - Cidade
    3: 150,   # D - Sector
    4: 60,    # E - Rating
    5: 70,    # F - Reviews
    6: 250,   # G - Instagram
    7: 280,   # H - Website
    8: 60,    # I - Score
    9: 140,   # J - Estado
    10: 120,  # K - Data Contacto
    11: 200,  # L - Link PDF
    12: 120,  # M - Follow-up 1
    13: 120,  # N - Follow-up 2
    14: 180,  # O - Notas
}

total_rows = len(ws.get_all_values())

requests = []

# --- 1. Larguras das colunas ---
for col_idx, width in COL_WIDTHS.items():
    requests.append({
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "startIndex": col_idx,
                "endIndex": col_idx + 1,
            },
            "properties": {"pixelSize": width},
            "fields": "pixelSize",
        }
    })

# --- 2. Altura do header (40px) ---
requests.append({
    "updateDimensionProperties": {
        "range": {
            "sheetId": sheet_id,
            "dimension": "ROWS",
            "startIndex": 0,
            "endIndex": 1,
        },
        "properties": {"pixelSize": 40},
        "fields": "pixelSize",
    }
})

# --- 3. Header: fundo escuro, texto branco, bold, centrado ---
requests.append({
    "repeatCell": {
        "range": {
            "sheetId": sheet_id,
            "startRowIndex": 0,
            "endRowIndex": 1,
            "startColumnIndex": 0,
            "endColumnIndex": 16,
        },
        "cell": {
            "userEnteredFormat": {
                "backgroundColor": DARK_BG,
                "textFormat": {
                    "foregroundColor": WHITE,
                    "bold": True,
                    "fontSize": 10,
                },
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "wrapStrategy": "WRAP",
            }
        },
        "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)",
    }
})

# --- 4. Dados: fonte 9, wrap text, vertical middle ---
if total_rows > 1:
    requests.append({
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 1,
                "endRowIndex": total_rows,
                "startColumnIndex": 0,
                "endColumnIndex": 16,
            },
            "cell": {
                "userEnteredFormat": {
                    "textFormat": {
                        "fontSize": 9,
                        "foregroundColor": {"red": 0.15, "green": 0.15, "blue": 0.15},
                    },
                    "verticalAlignment": "MIDDLE",
                    "wrapStrategy": "CLIP",
                }
            },
            "fields": "userEnteredFormat(textFormat,verticalAlignment,wrapStrategy)",
        }
    })


# --- 6. Coluna Nome (A) — bold ---
if total_rows > 1:
    requests.append({
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 1,
                "endRowIndex": total_rows,
                "startColumnIndex": 0,
                "endColumnIndex": 1,
            },
            "cell": {
                "userEnteredFormat": {
                    "textFormat": {"bold": True, "fontSize": 9},
                }
            },
            "fields": "userEnteredFormat(textFormat)",
        }
    })

# --- 7. Colunas Rating (E) e Reviews (F) e Score (I) — centrado ---
for col in [4, 5, 8]:
    if total_rows > 1:
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "endRowIndex": total_rows,
                    "startColumnIndex": col,
                    "endColumnIndex": col + 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "horizontalAlignment": "CENTER",
                    }
                },
                "fields": "userEnteredFormat(horizontalAlignment)",
            }
        })

# --- 8. Coluna Estado (J) — centrado ---
if total_rows > 1:
    requests.append({
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 1,
                "endRowIndex": total_rows,
                "startColumnIndex": 9,
                "endColumnIndex": 10,
            },
            "cell": {
                "userEnteredFormat": {
                    "horizontalAlignment": "CENTER",
                    "textFormat": {"bold": True, "fontSize": 9},
                }
            },
            "fields": "userEnteredFormat(horizontalAlignment,textFormat)",
        }
    })

# --- 9. Linhas alternadas (zebra) ---
if total_rows > 1:
    requests.append({
        "addBanding": {
            "bandedRange": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": total_rows,
                    "startColumnIndex": 0,
                    "endColumnIndex": 16,
                },
                "rowProperties": {
                    "headerColor": DARK_BG,
                    "firstBandColor": WHITE,
                    "secondBandColor": LIGHT_BG,
                },
            }
        }
    })

# --- 10. Freeze header row ---
requests.append({
    "updateSheetProperties": {
        "properties": {
            "sheetId": sheet_id,
            "gridProperties": {
                "frozenRowCount": 1,
            },
        },
        "fields": "gridProperties.frozenRowCount",
    }
})

# --- 11. Bordas finas no header ---
requests.append({
    "updateBorders": {
        "range": {
            "sheetId": sheet_id,
            "startRowIndex": 0,
            "endRowIndex": 1,
            "startColumnIndex": 0,
            "endColumnIndex": 16,
        },
        "bottom": {
            "style": "SOLID_MEDIUM",
            "color": PURPLE,
        },
    }
})

# --- 12. Altura das linhas de dados (28px) ---
if total_rows > 1:
    requests.append({
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "ROWS",
                "startIndex": 1,
                "endIndex": total_rows,
            },
            "properties": {"pixelSize": 28},
            "fields": "pixelSize",
        }
    })

# --- Executar tudo ---
print(f"A aplicar {len(requests)} formatacoes...")
spreadsheet.batch_update({"requests": requests})
print("Sheets formatado com sucesso!")
