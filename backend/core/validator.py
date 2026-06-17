"""
core/validator.py
Aplica regras de negócio sobre o DataFrame *após* a limpeza do parser.
Não calcula métricas — apenas valida precondições do experimento.

Regras implementadas:
  1. MIN_SAMPLE      — tamanho mínimo de amostra por grupo
  2. GROUP_BALANCE   — desequilíbrio excessivo entre grupos
  3. MIN_GROUPS      — precisa de ao menos 2 grupos
  4. NEGATIVE_VALUES — GMV, comissão ou cashback negativos
  5. GMV_ZERO_BUYERS — compradores com GMV = 0 (dados suspeitos)
  6. COMMISSION_GT_GMV — comissão > GMV (provável erro de dado)
  7. CASHBACK_GT_GMV  — cashback > GMV (provável erro de dado)
  8. MIN_PERIOD       — período mínimo do experimento (se coluna 'date' presente)
  9. DUPLICATE_USERS  — mesmo user_id em mais de um grupo (contaminação)
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from models.entities import ValidationReport

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds (podem ser sobrescritos via config.py)
# ---------------------------------------------------------------------------

DEFAULT_MIN_SAMPLE_PER_GROUP: int = 30
DEFAULT_MAX_IMBALANCE_RATIO: float = 3.0   # grupo maior não pode ser 3× o menor
DEFAULT_MIN_PERIOD_DAYS: int = 7


class Validator:
    """
    Valida o DataFrame limpo antes de passar para MetricsCalculator.

    Uso:
        report = Validator().validate(df)
        if not report.is_valid:
            raise ValueError(report.issues)
    """

    def __init__(
        self,
        min_sample_per_group: int = DEFAULT_MIN_SAMPLE_PER_GROUP,
        max_imbalance_ratio: float = DEFAULT_MAX_IMBALANCE_RATIO,
        min_period_days: int = DEFAULT_MIN_PERIOD_DAYS,
    ) -> None:
        self.min_sample = min_sample_per_group
        self.max_imbalance = max_imbalance_ratio
        self.min_period_days = min_period_days

    # ------------------------------------------------------------------
    def validate(self, df: pd.DataFrame) -> ValidationReport:
        report = ValidationReport()

        self._check_min_groups(df, report)
        self._check_min_sample(df, report)
        self._check_balance(df, report)
        self._check_negative_values(df, report)
        self._check_gmv_zero_buyers(df, report)
        self._check_commission_gt_gmv(df, report)
        self._check_cashback_gt_gmv(df, report)
        self._check_period(df, report)
        self._check_user_contamination(df, report)

        if report.is_valid:
            logger.info("Validação aprovada sem erros.")
        else:
            errors = [i for i in report.issues if i.level == "error"]
            warnings = [i for i in report.issues if i.level == "warning"]
            logger.warning(
                "Validação: %d erro(s), %d aviso(s).", len(errors), len(warnings)
            )

        return report

    # ------------------------------------------------------------------
    # Regras individuais
    # ------------------------------------------------------------------

    def _check_min_groups(self, df: pd.DataFrame, report: ValidationReport) -> None:
        n_groups = df["group"].nunique()
        if n_groups < 2:
            report.add_error(
                "MIN_GROUPS",
                f"Experimento precisa de ao menos 2 grupos; encontrado: {n_groups}.",
            )
        else:
            logger.debug("Grupos encontrados: %s", sorted(df["group"].unique()))

    def _check_min_sample(self, df: pd.DataFrame, report: ValidationReport) -> None:
        counts = df["group"].value_counts()
        small = counts[counts < self.min_sample]
        for group, count in small.items():
            report.add_error(
                "MIN_SAMPLE",
                f"Grupo '{group}' tem apenas {count} usuário(s) "
                f"(mínimo recomendado: {self.min_sample}).",
            )

    def _check_balance(self, df: pd.DataFrame, report: ValidationReport) -> None:
        counts = df["group"].value_counts()
        if len(counts) < 2:
            return
        ratio = counts.max() / counts.min()
        if ratio > self.max_imbalance:
            report.add_warning(
                "GROUP_BALANCE",
                f"Desequilíbrio entre grupos: maior/menor = {ratio:.1f}× "
                f"(threshold: {self.max_imbalance}×). Resultados podem ser enviesados.",
            )

    def _check_negative_values(self, df: pd.DataFrame, report: ValidationReport) -> None:
        for col in ["gmv", "commission", "cashback"]:
            if col not in df.columns:
                continue
            neg_count = int((df[col] < 0).sum())
            if neg_count:
                report.add_warning(
                    "NEGATIVE_VALUES",
                    f"Coluna '{col}' contém {neg_count} valor(es) negativo(s). "
                    "Verifique se há estornos ou erros de dado.",
                )

    def _check_gmv_zero_buyers(self, df: pd.DataFrame, report: ValidationReport) -> None:
        """Compradores marcados como convertidos mas com GMV = 0."""
        if "converted" not in df.columns:
            return
        suspect = df[(df["converted"] == 1) & (df["gmv"] == 0)]
        if len(suspect):
            report.add_warning(
                "GMV_ZERO_BUYERS",
                f"{len(suspect)} usuário(s) marcados como compradores mas com GMV = 0. "
                "Possível inconsistência nos dados.",
            )

    def _check_commission_gt_gmv(self, df: pd.DataFrame, report: ValidationReport) -> None:
        if "commission" not in df.columns or "gmv" not in df.columns:
            return
        # Permite pequena tolerância de floating-point
        over = df[df["commission"] > df["gmv"] * 1.001]
        if len(over):
            report.add_warning(
                "COMMISSION_GT_GMV",
                f"{len(over)} linha(s) com comissão maior que o GMV. "
                "Verifique a lógica de comissionamento.",
            )

    def _check_cashback_gt_gmv(self, df: pd.DataFrame, report: ValidationReport) -> None:
        if "cashback" not in df.columns or "gmv" not in df.columns:
            return
        over = df[df["cashback"] > df["gmv"] * 1.001]
        if len(over):
            report.add_warning(
                "CASHBACK_GT_GMV",
                f"{len(over)} linha(s) com cashback maior que o GMV. "
                "Verifique a política de cashback.",
            )

    def _check_period(self, df: pd.DataFrame, report: ValidationReport) -> None:
        if "date" not in df.columns:
            return
        valid_dates = df["date"].dropna()
        if valid_dates.empty:
            return
        period_days = (valid_dates.max() - valid_dates.min()).days
        if period_days < self.min_period_days:
            report.add_warning(
                "MIN_PERIOD",
                f"Período do experimento é de apenas {period_days} dia(s) "
                f"(recomendado: ≥ {self.min_period_days} dias). "
                "Efeitos sazonais podem distorcer os resultados.",
            )

    def _check_user_contamination(self, df: pd.DataFrame, report: ValidationReport) -> None:
        """Detecta usuários que aparecem em mais de um grupo (contaminação)."""
        if "user_id" not in df.columns:
            report.add_warning(
                "NO_USER_ID_VALIDATION",
                "Coluna 'user_id' ausente — não é possível checar contaminação entre grupos nem calcular retenção/LTV com precisão.",
            )
            return

        user_groups = df.groupby("user_id")["group"].nunique()
        contaminated = user_groups[user_groups > 1]
        if len(contaminated):
            report.add_error(
                "USER_CONTAMINATION",
                f"{len(contaminated)} usuário(s) aparecem em mais de um grupo. "
                "Contaminação de grupos invalida o experimento.",
            )
