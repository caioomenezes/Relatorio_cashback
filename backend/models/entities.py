"""
models/entities.py
Dataclasses para experimento A/B com dados agregados por dia.
Sem total_users, sem conversion_rate — só o que o CSV fornece.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class GroupStats:
    """Métricas consolidadas de um grupo A/B (soma do período)."""

    group_name: str

    # --- contagens ---
    buyers: int = 0                   # compradores únicos (soma dos dias)
    days: int = 0                     # dias de observação

    # --- valores monetários ---
    gmv: float = 0.0
    commission: float = 0.0
    cashback: float = 0.0
    net_revenue: float = 0.0          # comissão − cashback

    # --- médias ---
    avg_ticket: float = 0.0           # gmv / buyers
    avg_cashback: float = 0.0         # cashback / buyers
    commission_per_buyer: float = 0.0 # commission / buyers

    # --- rentabilidade ---
    roi: float = 0.0                  # net_revenue / cashback
    margin: float = 0.0               # net_revenue / gmv

    # --- break-even ---
    break_even_cashback: float = 0.0
    break_even_per_buyer: float = 0.0
    break_even_pct_of_gmv: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "group_name":             self.group_name,
            "buyers":                 self.buyers,
            "days":                   self.days,
            "gmv":                    round(self.gmv, 2),
            "commission":             round(self.commission, 2),
            "cashback":               round(self.cashback, 2),
            "net_revenue":            round(self.net_revenue, 2),
            "avg_ticket":             round(self.avg_ticket, 2),
            "avg_cashback":           round(self.avg_cashback, 2),
            "commission_per_buyer":   round(self.commission_per_buyer, 2),
            "roi":                    round(self.roi, 4),
            "margin":                 round(self.margin, 4),
            "break_even_cashback":    round(self.break_even_cashback, 2),
            "break_even_per_buyer":   round(self.break_even_per_buyer, 2),
            "break_even_pct_of_gmv":  round(self.break_even_pct_of_gmv, 4),
        }


@dataclass
class MetricsResult:
    groups: Dict[str, GroupStats] = field(default_factory=dict)
    control_group: Optional[str] = None
    lifts: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Série temporal: {group: [{date, buyers, gmv, commission, cashback, net_revenue, roi, margin}]}
    time_series: Dict[str, List[Dict]] = field(default_factory=dict)

    # Breakdown por parceiro: {group: {partner: GroupStats}}
    partner_breakdown: Dict[str, Dict[str, GroupStats]] = field(default_factory=dict)

    # Recomendação de escala
    recommended_group: Optional[str] = None
    recommendation_reason: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "control_group":         self.control_group,
            "groups":                {n: g.to_dict() for n, g in self.groups.items()},
            "lifts":                 {k: {m: round(v, 4) for m, v in lv.items()} for k, lv in self.lifts.items()},
            "time_series":           self.time_series,
            "partner_breakdown":     {g: {p: ps.to_dict() for p, ps in pb.items()} for g, pb in self.partner_breakdown.items()},
            "recommended_group":     self.recommended_group,
            "recommendation_reason": self.recommendation_reason,
        }


@dataclass
class ValidationIssue:
    level: str
    code: str
    message: str

    def to_dict(self) -> Dict:
        return {"level": self.level, "code": self.code, "message": self.message}


@dataclass
class ValidationReport:
    is_valid: bool = True
    issues: List[ValidationIssue] = field(default_factory=list)

    def add_error(self, code: str, message: str) -> None:
        self.is_valid = False
        self.issues.append(ValidationIssue("error", code, message))

    def add_warning(self, code: str, message: str) -> None:
        self.issues.append(ValidationIssue("warning", code, message))

    def to_dict(self) -> Dict:
        return {
            "is_valid": self.is_valid,
            "issues":   [i.to_dict() for i in self.issues],
        }