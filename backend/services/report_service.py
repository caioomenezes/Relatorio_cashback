import logging
import math
import traceback
import datetime as _dt

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.pipeline import CorePipeline

# ── Logger ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ab_cashback")


def to_jsonable(obj):
    """Converte recursivamente tipos do pandas/numpy (Timestamp, int64, NaN, NaT etc.)
    em tipos nativos do Python, para que json.dumps não quebre."""
    if obj is None:
        return None
    if isinstance(obj, (pd.Timestamp, _dt.datetime, _dt.date)):
        return obj.isoformat()
    if isinstance(obj, pd.Timedelta):
        return str(obj)
    if obj is pd.NaT:
        return None
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        val = float(obj)
        return None if math.isnan(val) or math.isinf(val) else val
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return [to_jsonable(x) for x in obj.tolist()]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(x) for x in obj]
    return obj


app = FastAPI(title="AB Cashback API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    try:
        content = await file.read()
        logger.info("/analyze: arquivo recebido — %s (%d bytes)", file.filename, len(content))

        pipeline = CorePipeline(abort_on_validation_error=False)
        result = pipeline.run(content)

        logger.info(
            "/analyze: pipeline ok — rows=%s groups=%s fatal_error=%s",
            result.preview.get("total_rows") if result.preview else "?",
            list(result.metrics.groups.keys()) if result.metrics else [],
            result.fatal_error,
        )

        payload = {
            "success": result.fatal_error is None,
            "fatal_error": result.fatal_error,
            "preview": result.preview,
            "validation": result.validation.to_dict() if result.validation else None,
            "metrics": result.metrics.to_dict() if result.metrics else None,
        }
        payload = to_jsonable(payload)

        return JSONResponse(content=payload)

    except Exception as exc:
        # Loga o traceback COMPLETO no terminal para debug
        tb = traceback.format_exc()
        logger.error("/analyze ERRO:\n%s", tb)
        return JSONResponse(
            status_code=500,
            content={"error": str(exc), "traceback": tb},
        )


@app.post("/append")
async def append_analysis(payload: dict):
    # Log assim que a requisição chega, ANTES de qualquer outra coisa.
    # Se essa linha nunca aparecer no terminal, o front-end não está
    # chamando esse endpoint — o problema está fora do backend.
    logger.info("/append: requisição recebida — chaves recebidas: %s", list(payload.keys()))
    logger.debug("/append: payload completo: %s", payload)

    try:
        from src.sheets import append_summary_row
        append_summary_row(payload)
        logger.info("/append: append_summary_row executado com sucesso.")
        return JSONResponse(content={"success": True})
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("/append ERRO:\n%s", tb)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(exc), "traceback": tb},
        )