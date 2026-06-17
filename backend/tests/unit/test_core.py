"""
tests/unit/test_core.py
Testes unitários para parser, validator e metrics.
Não dependem de APIs externas — usam dados sintéticos.

Execute com:
    cd backend && python -m pytest tests/unit/test_core.py -v
"""

from __future__ import annotations

import io
import textwrap

import numpy as np
import pandas as pd
import pytest

from core.metrics import MetricsCalculator, calculate_metrics
from core.parser import ABParser, _clean_monetary, _normalize_name
from core.pipeline import CorePipeline
from core.validator import Validator
from models.entities import GroupStats, MetricsResult


# ---------------------------------------------------------------------------
# Fixtures e helpers
# ---------------------------------------------------------------------------

def make_csv(rows: str) -> bytes:
    """Cria bytes de CSV a partir de uma string multi-linha."""
    return textwrap.dedent(rows).strip().encode("utf-8")


VALID_CSV = make_csv("""
    user_id,grupo,gmv,comissao,cashback
    u001,A,100.00,10.00,5.00
    u002,A,200.00,20.00,8.00
    u003,A,0.00,0.00,0.00
    u004,B,150.00,15.00,20.00
    u005,B,300.00,30.00,25.00
    u006,B,0.00,0.00,0.00
""")

VALID_CSV_BR = make_csv("""
    user_id;grupo;gmv;comissao;cashback
    u001;A;"1.000,00";"100,00";"50,00"
    u002;A;"2.000,00";"200,00";"80,00"
    u003;B;"1.500,00";"150,00";"200,00"
    u004;B;"3.000,00";"300,00";"250,00"
""")


def make_df(**kwargs) -> pd.DataFrame:
    """Cria DataFrame diretamente sem passar pelo CSV."""
    defaults = {
        "user_id":   ["u1", "u2", "u3", "u4"],
        "group":     ["A",  "A",  "B",  "B"],
        "gmv":       [100., 200., 150., 300.],
        "commission":[10.,  20.,  15.,  30.],
        "cashback":  [5.,   8.,   20.,  25.],
        "converted": [1,    1,    1,    1],
    }
    defaults.update(kwargs)
    return pd.DataFrame(defaults)


# ===========================================================================
# PARSER
# ===========================================================================

class TestParser:

    def test_parse_valid_csv(self):
        df = ABParser().parse(VALID_CSV)
        assert len(df) == 6
        assert set(df.columns) >= {"user_id", "group", "gmv", "commission", "cashback"}

    def test_parse_semicolon_br_format(self):
        df = ABParser().parse(VALID_CSV_BR)
        assert len(df) == 4
        # Verifica que valores BR foram convertidos corretamente
        assert df["gmv"].max() == pytest.approx(3000.0)

    def test_groups_uppercased(self):
        csv = make_csv("""
            user_id,grupo,gmv,comissao,cashback
            u1,control,100,10,5
            u2,treatment,200,20,8
        """)
        df = ABParser().parse(csv)
        assert set(df["group"].unique()) == {"CONTROL", "TREATMENT"}

    def test_missing_required_column_raises(self):
        csv = make_csv("""
            user_id,gmv,comissao
            u1,100,10
        """)
        with pytest.raises(ValueError, match="Colunas obrigatórias ausentes"):
            ABParser().parse(csv)

    def test_converted_inferred_from_gmv(self):
        df = ABParser().parse(VALID_CSV)
        # u003 (gmv=0) → converted=0; u001 (gmv=100) → converted=1
        row_u003 = df[df["user_id"] == "u003"].iloc[0]
        row_u001 = df[df["user_id"] == "u001"].iloc[0]
        assert row_u003["converted"] == 0
        assert row_u001["converted"] == 1

    def test_clean_monetary_br(self):
        s = pd.Series(["R$ 1.234,56", "R$ 10.000,00", "0"])
        result = _clean_monetary(s)
        assert result[0] == pytest.approx(1234.56)
        assert result[1] == pytest.approx(10000.0)
        assert result[2] == pytest.approx(0.0)

    def test_clean_monetary_us(self):
        s = pd.Series(["1,234.56", "10,000.00", "0.5"])
        result = _clean_monetary(s)
        assert result[0] == pytest.approx(1234.56)
        assert result[1] == pytest.approx(10000.0)

    def test_normalize_name(self):
        assert _normalize_name("Valor Pedido (R$)") == "valor_pedido_r"
        assert _normalize_name("  user_id  ") == "user_id"


# ===========================================================================
# VALIDATOR
# ===========================================================================

class TestValidator:

    def test_valid_df_passes(self):
        df = make_df()
        report = Validator(min_sample_per_group=1).validate(df)
        assert report.is_valid

    def test_single_group_fails(self):
        df = make_df(group=["A", "A", "A", "A"])
        report = Validator(min_sample_per_group=1).validate(df)
        assert not report.is_valid
        codes = [i.code for i in report.issues]
        assert "MIN_GROUPS" in codes

    def test_min_sample_error(self):
        df = make_df()
        report = Validator(min_sample_per_group=10).validate(df)
        assert not report.is_valid
        codes = [i.code for i in report.issues]
        assert "MIN_SAMPLE" in codes

    def test_imbalance_warning(self):
        # Grupo A tem 3 usuários, grupo B tem 1 → ratio = 3
        df = make_df(
            user_id=["u1", "u2", "u3", "u4"],
            group=["A", "A", "A", "B"],
        )
        report = Validator(min_sample_per_group=1, max_imbalance_ratio=2.0).validate(df)
        codes = [i.code for i in report.issues]
        assert "GROUP_BALANCE" in codes

    def test_user_contamination_error(self):
        df = make_df(
            user_id=["u1", "u1", "u3", "u4"],  # u1 em A e B
            group=["A", "B", "A", "B"],
        )
        report = Validator(min_sample_per_group=1).validate(df)
        assert not report.is_valid
        codes = [i.code for i in report.issues]
        assert "USER_CONTAMINATION" in codes

    def test_cashback_gt_gmv_warning(self):
        df = make_df(
            gmv=[100., 200., 150., 300.],
            cashback=[200., 8., 20., 25.],  # u1: cashback > gmv
        )
        report = Validator(min_sample_per_group=1).validate(df)
        codes = [i.code for i in report.issues]
        assert "CASHBACK_GT_GMV" in codes

    def test_negative_values_warning(self):
        df = make_df(gmv=[-10., 200., 150., 300.])
        report = Validator(min_sample_per_group=1).validate(df)
        codes = [i.code for i in report.issues]
        assert "NEGATIVE_VALUES" in codes


# ===========================================================================
# METRICS
# ===========================================================================

class TestMetrics:

    def test_basic_calculation(self):
        df = make_df()
        result = calculate_metrics(df, control_group="A")

        assert "A" in result.groups
        assert "B" in result.groups
        assert result.control_group == "A"

    def test_buyers_count(self):
        df = make_df(
            user_id=["u1", "u2", "u3", "u4"],
            group=["A", "A", "B", "B"],
            converted=[1, 0, 1, 1],
        )
        result = calculate_metrics(df, control_group="A")
        assert result.groups["A"].conversion_rate == pytest.approx(0.5)
        assert result.groups["B"].conversion_rate == pytest.approx(1.0)

    def test_gmv_sum(self):
        df = make_df()
        result = calculate_metrics(df, control_group="A")
        # u1=100, u2=200 → grupo A gmv = 300
        assert result.groups["A"].gmv == pytest.approx(300.0)

    def test_net_revenue(self):
        df = make_df(
            commission=[10., 20., 15., 30.],
            cashback=[5.,   8.,  20., 25.],
        )
        result = calculate_metrics(df, control_group="A")
        # Grupo A: commission=30, cashback=13 → net=17
        assert result.groups["A"].net_revenue == pytest.approx(17.0)
        # Grupo B: commission=45, cashback=45 → net=0
        assert result.groups["B"].net_revenue == pytest.approx(0.0)

    def test_roi_zero_cashback(self):
        """ROI deve ser 0 quando cashback = 0 e receita líquida = 0."""
        df = make_df(cashback=[0., 0., 0., 0.])
        result = calculate_metrics(df, control_group="A")
        assert result.groups["A"].roi == pytest.approx(0.0)

    def test_margin(self):
        df = make_df(
            gmv=[100., 200., 150., 300.],
            commission=[30.,  30.,  45.,  45.],
            cashback=[10.,   10.,  20.,  25.],
        )
        result = calculate_metrics(df, control_group="A")
        # Grupo A: net=40, gmv=300 → margin ≈ 0.1333
        expected_margin = (60 - 20) / 300
        assert result.groups["A"].margin == pytest.approx(expected_margin, rel=1e-3)

    def test_avg_ticket(self):
        df = make_df(
            gmv=[100., 200., 300., 600.],
            converted=[1, 1, 1, 1],
        )
        result = calculate_metrics(df, control_group="A")
        # Grupo A: gmv=300, buyers=2 → avg_ticket=150
        assert result.groups["A"].avg_ticket == pytest.approx(150.0)

    def test_lift_calculated(self):
        """Lift de GMV do grupo B vs A deve ser positivo quando B tem mais GMV."""
        df = make_df(
            gmv=[100., 100., 200., 200.],
        )
        result = calculate_metrics(df, control_group="A")
        assert "B" in result.lifts
        assert result.lifts["B"]["gmv"] == pytest.approx(1.0)  # +100%

    def test_multiple_groups(self):
        """Pipeline deve funcionar com 3+ grupos."""
        df = pd.DataFrame({
            "user_id":   [f"u{i}" for i in range(9)],
            "group":     ["A", "A", "A", "B", "B", "B", "C", "C", "C"],
            "gmv":       [100., 200., 150., 120., 180., 160., 90., 110., 130.],
            "commission":[10.,  20.,  15.,  12.,  18.,  16.,  9.,  11.,  13.],
            "cashback":  [5.,   8.,   6.,   20.,  25.,  22.,  3.,  4.,   5.],
            "converted": [1,    1,    1,    1,    1,    1,    1,   1,    1],
        })
        result = calculate_metrics(df, control_group="A")
        assert set(result.groups.keys()) == {"A", "B", "C"}
        assert "B" in result.lifts
        assert "C" in result.lifts
        assert "A" not in result.lifts  # controle não tem lift

    def test_conversion_rate(self):
        df = make_df(
            user_id=["u1", "u2", "u3", "u4"],
            group=["A", "A", "B", "B"],
            converted=[1, 0, 1, 1],
            gmv=[100., 0., 150., 300.],
        )
        result = calculate_metrics(df, control_group="A")
        assert result.groups["A"].conversion_rate == pytest.approx(0.5)
        assert result.groups["B"].conversion_rate == pytest.approx(1.0)


# ===========================================================================
# PIPELINE INTEGRADO
# ===========================================================================

class TestCorePipeline:

    def test_full_pipeline_success(self):
        result = CorePipeline(
            min_sample_per_group=1,
            abort_on_validation_error=True,
        ).run(VALID_CSV)

        assert result.success
        assert result.df is not None
        assert result.validation is not None
        assert result.metrics is not None
        assert result.preview is not None

    def test_pipeline_invalid_csv_fails(self):
        bad_csv = b"not,a,valid,ab,experiment\n1,2,3,4,5"
        result = CorePipeline(min_sample_per_group=1).run(bad_csv)
        assert not result.success
        assert result.fatal_error is not None

    def test_pipeline_metrics_dict_serializable(self):
        result = CorePipeline(min_sample_per_group=1).run(VALID_CSV)
        d = result.metrics.to_dict()
        assert isinstance(d, dict)
        assert "groups" in d
        assert "lifts" in d
