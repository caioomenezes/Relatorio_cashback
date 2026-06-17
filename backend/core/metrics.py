"""
core/metrics.py
Calcula métricas para experimento A/B com dados agregados por dia.

Métricas por grupo (consolidado do período):
    buyers, days, gmv, commission, cashback, net_revenue,
    avg_ticket, avg_cashback, commission_per_buyer, roi, margin,
    break_even_cashback, break_even_per_buyer, break_even_pct_of_gmv

Lifts vs controle: gmv, net_revenue, roi, margin, avg_ticket
Série temporal: evolução diária por grupo
Recomendação: qual grupo escalar (maior ROI + maior receita líquida)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from models.entities import GroupStats, MetricsResult

logger = logging.getLogger(__name__)

_LIFT_METRICS = ["gmv", "net_revenue", "roi", "margin", "avg_ticket", "avg_cashback"]


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    return default if den == 0 else num / den


class MetricsCalculator:
    def __init__(self, control_group: Optional[str] = None) -> None:
        self.control_group = control_group

    def calculate(self, df: pd.DataFrame) -> MetricsResult:
        groups_in_data = sorted(df["group"].unique().tolist())
        logger.info("Calculando métricas para grupos: %s", groups_in_data)

        control = self.control_group or groups_in_data[0]
        if control not in groups_in_data:
            control = groups_in_data[0]

        # Métricas por grupo
        group_stats: Dict[str, GroupStats] = {}
        for name in groups_in_data:
            group_stats[name] = self._calculate_group(name, df[df["group"] == name])

        # Lifts
        lifts = self._calculate_lifts(group_stats, control)

        # Série temporal
        time_series = self._compute_time_series(df) if "date" in df.columns else {}

        # Breakdown por parceiro
        partner_breakdown = self._compute_partner_breakdown(df, groups_in_data) if "partner" in df.columns else {}

        # Recomendação
        recommended, reason = self._recommend(group_stats, control)

        result = MetricsResult(
            groups=group_stats,
            control_group=control,
            lifts=lifts,
            time_series=time_series,
            partner_breakdown=partner_breakdown,
            recommended_group=recommended,
            recommendation_reason=reason,
        )
        self._log_summary(result)
        return result

    def _calculate_group(self, group_name: str, df: pd.DataFrame) -> GroupStats:
        buyers     = int(df["buyers"].sum())
        days       = int(len(df))
        gmv        = float(df["gmv"].sum())
        commission = float(df["commission"].sum())
        cashback   = float(df["cashback"].sum())
        net_revenue = commission - cashback

        avg_ticket           = _safe_div(gmv, buyers)
        avg_cashback         = _safe_div(cashback, buyers)
        commission_per_buyer = _safe_div(commission, buyers)
        roi                  = _safe_div(net_revenue, cashback)
        margin               = _safe_div(net_revenue, gmv)

        break_even_cashback   = float(commission)
        break_even_per_buyer  = _safe_div(commission, buyers)
        break_even_pct_of_gmv = _safe_div(commission, gmv)

        return GroupStats(
            group_name=group_name,
            buyers=buyers,
            days=days,
            gmv=gmv,
            commission=commission,
            cashback=cashback,
            net_revenue=net_revenue,
            avg_ticket=avg_ticket,
            avg_cashback=avg_cashback,
            commission_per_buyer=commission_per_buyer,
            roi=roi,
            margin=margin,
            break_even_cashback=break_even_cashback,
            break_even_per_buyer=break_even_per_buyer,
            break_even_pct_of_gmv=break_even_pct_of_gmv,
        )

    def _calculate_lifts(self, group_stats: Dict[str, GroupStats], control: str) -> Dict[str, Dict[str, float]]:
        lifts: Dict[str, Dict[str, float]] = {}
        ctrl = group_stats.get(control)
        if ctrl is None:
            return lifts

        ctrl_values = {
            "gmv":         ctrl.gmv,
            "net_revenue": ctrl.net_revenue,
            "roi":         ctrl.roi,
            "margin":      ctrl.margin,
            "avg_ticket":  ctrl.avg_ticket,
            "avg_cashback": ctrl.avg_cashback,
        }

        EPSILON = 1e-9
        for name, stats in group_stats.items():
            if name == control:
                continue
            test_values = {
                "gmv":         stats.gmv,
                "net_revenue": stats.net_revenue,
                "roi":         stats.roi,
                "margin":      stats.margin,
                "avg_ticket":  stats.avg_ticket,
                "avg_cashback": stats.avg_cashback,
            }
            group_lifts = {}
            for metric in _LIFT_METRICS:
                ctrl_val = ctrl_values[metric]
                test_val = test_values[metric]
                if not np.isfinite(ctrl_val) or abs(ctrl_val) < EPSILON:
                    group_lifts[metric] = 0.0
                    continue
                lift = (test_val - ctrl_val) / abs(ctrl_val)
                group_lifts[metric] = float(lift) if np.isfinite(lift) else 0.0
            lifts[name] = group_lifts

        return lifts

    def _compute_time_series(self, df: pd.DataFrame) -> Dict[str, List[Dict]]:
        ts: Dict[str, List[Dict]] = {}
        df_local = df.copy()
        df_local["date"] = pd.to_datetime(df_local["date"], errors="coerce").dt.date

        for group in sorted(df_local["group"].unique()):
            sub = df_local[df_local["group"] == group].sort_values("date")
            series = []
            for _, row in sub.iterrows():
                buyers     = int(row["buyers"])
                gmv        = float(row["gmv"])
                commission = float(row["commission"])
                cashback   = float(row["cashback"])
                net_revenue = commission - cashback
                series.append({
                    "date":        str(row["date"]),
                    "buyers":      buyers,
                    "gmv":         round(gmv, 2),
                    "commission":  round(commission, 2),
                    "cashback":    round(cashback, 2),
                    "net_revenue": round(net_revenue, 2),
                    "roi":         round(_safe_div(net_revenue, cashback), 4),
                    "margin":      round(_safe_div(net_revenue, gmv), 4),
                    "avg_ticket":  round(_safe_div(gmv, buyers), 2),
                })
            ts[group] = series

        return ts

    def _compute_partner_breakdown(self, df: pd.DataFrame, groups: List[str]) -> Dict[str, Dict[str, GroupStats]]:
        breakdown: Dict[str, Dict[str, GroupStats]] = {}
        partners = sorted(df["partner"].fillna("<UNKNOWN>").unique())
        for group in groups:
            breakdown[group] = {}
            for partner in partners:
                sub = df[(df["group"] == group) & (df["partner"].fillna("<UNKNOWN>") == partner)]
                if len(sub) == 0:
                    continue
                breakdown[group][partner] = self._calculate_group(partner, sub)
        return breakdown

    def _recommend(self, group_stats: Dict[str, GroupStats], control: str):
        """Escolhe o grupo com melhor ROI entre os que têm receita líquida positiva."""
        candidates = {n: s for n, s in group_stats.items() if s.net_revenue > 0}
        if not candidates:
            return None, "Nenhum grupo com receita líquida positiva."

        best = max(candidates.items(), key=lambda x: (x[1].roi, x[1].net_revenue))
        name, stats = best

        reason = (
            f"Grupo {name} apresenta o maior ROI ({stats.roi:.2f}) "
            f"com receita líquida de R$ {stats.net_revenue:,.2f}. "
            f"Cada R$ 1,00 de cashback gera R$ {stats.roi:.2f} de receita líquida."
        )
        return name, reason

    def _log_summary(self, result: MetricsResult) -> None:
        logger.info("=== Resumo de Métricas ===")
        for name, gs in result.groups.items():
            marker = " [CONTROLE]" if name == result.control_group else ""
            logger.info(
                "Grupo %s%s | Compradores: %d | GMV: %.2f | Receita Líq.: %.2f | ROI: %.2f | Margem: %.1f%%",
                name, marker, gs.buyers, gs.gmv, gs.net_revenue, gs.roi, gs.margin * 100,
            )
        if result.recommended_group:
            logger.info("Recomendação: escalar %s — %s", result.recommended_group, result.recommendation_reason)