import logging
import math
import traceback
import datetime as _dt

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.pipeline import CorePipeline
from models.entities import MetricsResult, GroupStats

# ── Logger ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ab_cashback")


def to_jsonable(obj):
    """Converte recursivamente tipos do pandas/numpy em tipos nativos do Python."""
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


# ── /analyze ──────────────────────────────────────────────────────────────
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
        tb = traceback.format_exc()
        logger.error("/analyze ERRO:\n%s", tb)
        return JSONResponse(
            status_code=500,
            content={"error": str(exc), "traceback": tb},
        )


# ── /report ───────────────────────────────────────────────────────────────
class ReportRequest(BaseModel):
    metrics: dict                        # payload metrics já retornado pelo /analyze
    experiment_name: str | None = None
    extra_context: str | None = None


@app.post("/report")
async def generate_report(body: ReportRequest):
    """
    Recebe as métricas já computadas pelo /analyze e devolve o relatório
    gerado pelo Gemini via LLMService, no formato que o ReportSection.jsx
    espera:

    {
      "sections": {
        "executive_summary": { title, content, icon, color },
        "findings":          { title, items, icon, color },
        "recommendations":   { title, items, icon, color },
        "risks":             { title, items, icon, color }
      },
      "model": "gemini-2.0-flash",
      "generated_at": "<ISO>"
    }
    """
    try:
        from services.llm_service import LLMService
        from models.entities import MetricsResult, GroupStats, LiftStats

        # ── Reconstrói MetricsResult a partir do dict enviado pelo front ──
        raw = body.metrics
        groups_raw = raw.get("groups", {})

        groups: dict[str, GroupStats] = {}
        for name, g in groups_raw.items():
            groups[name] = GroupStats(
                total_users=g.get("total_users", 0),
                buyers=g.get("buyers", 0),
                conversion_rate=g.get("conversion_rate", 0.0),
                gmv=g.get("gmv", 0.0),
                commission=g.get("commission", 0.0),
                cashback=g.get("cashback", 0.0),
                net_revenue=g.get("net_revenue", 0.0),
                avg_ticket=g.get("avg_ticket", 0.0),
                avg_cashback=g.get("avg_cashback", 0.0),
                commission_per_buyer=g.get("commission_per_buyer", 0.0),
                roi=g.get("roi", 0.0),
                margin=g.get("margin", 0.0),
            )

        lifts_raw = raw.get("lifts", {})
        lifts: dict[str, dict] = {
            group: vals for group, vals in lifts_raw.items()
        }

        metrics_result = MetricsResult(
            groups=groups,
            control_group=raw.get("control_group", next(iter(groups), "")),
            lifts=lifts,
            is_significant=raw.get("is_significant"),
            p_value=raw.get("p_value"),
        )

        # ── Chama o LLMService (Gemini) ──────────────────────────────────
        service = LLMService.from_env()
        report_sections = service.generate_insight(
            metrics_result,
            experiment_name=body.experiment_name,
            extra_context=body.extra_context,
        )

        # ── Adapta o retorno para o formato do ReportSection.jsx ─────────
        # O Gemini devolve Markdown; transformamos nas 4 seções esperadas
        # pelo front. Usamos os campos já parseados pelo LLMService.
        def md_to_items(text: str) -> list[str]:
            """Extrai bullet points de um bloco Markdown."""
            items = []
            for line in text.splitlines():
                line = line.strip().lstrip("-*•").strip()
                if line:
                    items.append(line)
            return items or [text.strip()]

        payload = {
            "sections": {
                "executive_summary": {
                    "title":   "Resumo Executivo",
                    "content": report_sections.executive_summary or report_sections.raw_markdown[:500],
                    "icon":    "summary",
                    "color":   "accent",
                },
                "findings": {
                    "title": "Achados Principais",
                    "items": md_to_items(report_sections.insights),
                    "icon":  "findings",
                    "color": "success",
                },
                "recommendations": {
                    "title": "Recomendações",
                    "items": md_to_items(
                        report_sections.opportunities + "\n" + report_sections.next_steps
                    ),
                    "icon":  "recommendations",
                    "color": "warning",
                },
                "risks": {
                    "title": "Riscos e Ressalvas",
                    "items": md_to_items(report_sections.risks),
                    "icon":  "risks",
                    "color": "danger",
                },
            },
            "model":        report_sections.model_used,
            "generated_at": _dt.datetime.utcnow().isoformat(),
            "decision":     report_sections.decision,
        }

        logger.info("/report: relatório gerado em %dms", report_sections.latency_ms)
        return JSONResponse(content=to_jsonable(payload))

    except ValueError as exc:
        # GEMINI_API_KEY não configurada
        logger.warning("/report: chave não configurada — %s", exc)
        return JSONResponse(status_code=503, content={"error": str(exc)})

    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("/report ERRO:\n%s", tb)
        return JSONResponse(
            status_code=500,
            content={"error": str(exc), "traceback": tb},
        )


# ── /append ───────────────────────────────────────────────────────────────
@app.post("/append")
async def append_analysis(payload: dict):
    logger.info("/append: requisição recebida — chaves recebidas: %s", list(payload.keys()))
    logger.debug("/append: payload completo: %s", payload)

    try:
        from sheets import append_summary_row
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