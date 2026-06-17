"""
sheets.py — grava uma linha de resultado A/B na planilha do Google Sheets
usando conta de serviço (credentials.json). Sem OAuth, sem browser.
"""

import datetime
import logging
import os

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger("ab_cashback")

# ── CONFIGURAÇÃO ──────────────────────────────────────────────────────────
SPREADSHEET_ID = "1Fjjbyox2p89cU-8F0T2IA3CqakdmRbQ5aq8hGpKKL-o"
SHEET_NAME     = "Página1"
SCOPES         = ["https://www.googleapis.com/auth/spreadsheets"]

# Caminho do credentials.json relativo a este arquivo (ambos em backend/)
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")

# ── ORDEM DAS COLUNAS NA PLANILHA ─────────────────────────────────────────
FIELD_ORDER = [
    "timestamp",
    "test_name",
    "decision",
    "winner_roi",
    "winner_net_revenue",
    "description",
]

HEADERS = [
    "Data de Teste",
    "Nome do Teste",
    "Decisão Tomada",
    "Resultado ROI",
    "Resultado Receita",
    "Descrição",
]


def _get_service():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def _ensure_headers(sheet):
    """Insere a linha de cabeçalho se a planilha estiver vazia."""
    range_ = f"{SHEET_NAME}!A1:A1"
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=range_).execute()
    if not result.get("values"):
        sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [HEADERS]},
        ).execute()
        logger.info("sheets: cabeçalho inserido.")


def append_summary_row(payload: dict):
    """
    Recebe o dict do /append (com as chaves de FIELD_ORDER) e
    grava uma linha na planilha.
    """
    service = _get_service()
    sheet   = service.spreadsheets()

    _ensure_headers(sheet)

    # Adiciona timestamp se não vier no payload
    payload.setdefault("timestamp", datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

    row = [str(payload.get(field, "")) if payload.get(field) is not None else "" for field in FIELD_ORDER]

    sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()

    logger.info("sheets: linha gravada — %s", row)