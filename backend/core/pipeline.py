"""
core/pipeline.py
Orquestrador leve do pipeline core (sem dependências externas).

Sequência:
    1. ABParser.parse()       → DataFrame limpo
    2. Validator.validate()   → ValidationReport
    3. MetricsCalculator.calculate() → MetricsResult

Retorna um PipelineResult com todos os artefatos intermediários,
permitindo que o report_service (camada de serviços) decida o que
fazer com erros de validação antes de continuar para LLM/Sheets.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from core.metrics import MetricsCalculator
from core.parser import ABParser, build_preview
from core.validator import Validator
from models.entities import MetricsResult, ValidationReport

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Todos os artefatos produzidos pelo pipeline core."""

    df: Optional[pd.DataFrame] = None
    validation: Optional[ValidationReport] = None
    metrics: Optional[MetricsResult] = None
    preview: Optional[dict] = None

    # Erros fatais que impediram a conclusão
    fatal_error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.fatal_error is None and (
            self.validation is None or self.validation.is_valid
        )


class CorePipeline:
    """
    Executa o pipeline core completo.

    Uso:
        result = CorePipeline().run(csv_bytes)
        if result.success:
            print(result.metrics.to_dict())
    """

    def __init__(
        self,
        control_group: Optional[str] = None,
        min_sample_per_group: int = 30,
        max_imbalance_ratio: float = 3.0,
        min_period_days: int = 7,
        abort_on_validation_error: bool = True,
    ) -> None:
        self.parser = ABParser()
        self.validator = Validator(
            min_sample_per_group=min_sample_per_group,
            max_imbalance_ratio=max_imbalance_ratio,
            min_period_days=min_period_days,
        )
        self.calculator = MetricsCalculator(control_group=control_group)
        self.abort_on_validation_error = abort_on_validation_error

    # ------------------------------------------------------------------
    def run(
        self,
        source: Union[str, Path, bytes, io.IOBase],
    ) -> PipelineResult:
        result = PipelineResult()

        # ---- 1. Parsing ----
        try:
            logger.info("[Pipeline] Etapa 1/3 — Parsing")
            result.df = self.parser.parse(source)
            result.preview = build_preview(result.df)
        except Exception as exc:
            logger.error("[Pipeline] Erro no parsing: %s", exc)
            result.fatal_error = f"Erro de parsing: {exc}"
            return result

        # ---- 2. Validação ----
        try:
            logger.info("[Pipeline] Etapa 2/3 — Validação")
            result.validation = self.validator.validate(result.df)
            if not result.validation.is_valid and self.abort_on_validation_error:
                errors = [i.message for i in result.validation.issues if i.level == "error"]
                result.fatal_error = "Validação falhou: " + " | ".join(errors)
                return result
        except Exception as exc:
            logger.error("[Pipeline] Erro na validação: %s", exc)
            result.fatal_error = f"Erro de validação: {exc}"
            return result

        # ---- 3. Métricas ----
        try:
            logger.info("[Pipeline] Etapa 3/3 — Cálculo de métricas")
            result.metrics = self.calculator.calculate(result.df)
        except Exception as exc:
            logger.error("[Pipeline] Erro no cálculo de métricas: %s", exc)
            result.fatal_error = f"Erro no cálculo de métricas: {exc}"
            return result

        logger.info("[Pipeline] Concluído com sucesso.")
        return result
