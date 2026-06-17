import os
import csv
import logging
from typing import Dict

logger = logging.getLogger("sheets_writer")
logging.basicConfig(level=logging.INFO)

try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except Exception as e:
    gspread = None
    logger.warning("gspread/oauth2client indisponíveis: %s", e)


# Caminho absoluto, baseado na localização deste arquivo — evita depender
# do diretório de trabalho (cwd) de onde o processo foi iniciado (uvicorn,
# Docker, systemd etc. podem ter cwd diferente do esperado).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.getenv('SUMMARY_OUTPUT_DIR', os.path.join(BASE_DIR, 'outputs'))
CSV_PATH = os.path.join(OUTPUTS_DIR, 'summary.csv')
FIELD_ORDER = [
    "timestamp",
    "source",          # de onde veio a linha: "streamlit" ou "api"
    "test_name",
    "description",
    "file_name",
    "partner",
    "num_groups",
    "result",
    "decision",
    "winner_group",
    "winner_net_revenue",
    "winner_roi",
    "report_id",
    "report_path",
    "elapsed_ms",
]


def append_summary_row(row: Dict) -> None:
    """Anexa uma linha à Google Sheet configurada ou grava em CSV como fallback.

    A planilha espera colunas na ordem `FIELD_ORDER`. Se a planilha estiver
    vazia ou sem cabeçalho, o cabeçalho será inserido automaticamente.
    """
    creds_path = os.getenv('GOOGLE_SHEETS_CREDENTIALS_JSON')
    sheet_id = os.getenv('GOOGLE_SHEET_ID')

    values = [row.get(k, "") for k in FIELD_ORDER]

    # Diagnóstico: avisa cedo se as variáveis de ambiente não estão configuradas
    if not creds_path:
        logger.warning("GOOGLE_SHEETS_CREDENTIALS_JSON não definida no ambiente.")
    if not sheet_id:
        logger.warning("GOOGLE_SHEET_ID não definida no ambiente.")
    if gspread is None:
        logger.warning("gspread não importado — verifique se está instalado (pip install gspread oauth2client).")

    if creds_path and sheet_id and gspread is not None:
        if not os.path.exists(creds_path):
            logger.error("Arquivo de credenciais não encontrado em: %s", creds_path)
        else:
            try:
                scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
                creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
                client = gspread.authorize(creds)
                sheet = client.open_by_key(sheet_id).sheet1

                # Ensure header
                try:
                    header = sheet.row_values(1)
                except Exception as e:
                    logger.warning("Falha ao ler cabeçalho da planilha: %s", e)
                    header = []

                if not header or [c.strip() for c in header] != FIELD_ORDER:
                    try:
                        sheet.insert_row(FIELD_ORDER, index=1)
                    except Exception as e:
                        logger.warning("Falha ao inserir cabeçalho: %s", e)

                sheet.append_row(values, value_input_option='USER_ENTERED')
                logger.info("Linha gravada com sucesso na planilha %s.", sheet_id)
                return
            except Exception as e:
                # Aqui está o ponto crítico: antes esse erro era engolido
                # silenciosamente (except: pass). Agora ele aparece no log.
                logger.error(
                    "Falha ao gravar na Google Sheet (%s). Caindo para CSV. Detalhe: %s",
                    sheet_id, e, exc_info=True,
                )

    # fallback CSV (keeps stable column order)
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    file_exists = os.path.exists(CSV_PATH)
    with open(CSV_PATH, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELD_ORDER)
        if not file_exists:
            writer.writeheader()
        out = {k: row.get(k, "") for k in FIELD_ORDER}
        writer.writerow(out)
    logger.info("Linha gravada no CSV de fallback: %s", CSV_PATH)