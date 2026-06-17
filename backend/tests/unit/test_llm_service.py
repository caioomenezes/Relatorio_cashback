"""
tests/unit/test_llm_service.py

Testes unitários da camada de IA.
NÃO chamam a API do Gemini — usam mocks para isolar a lógica.

Execute com:
    cd backend && python -m pytest tests/unit/test_llm_service.py -v
"""

from __future__ import annotations

import textwrap
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from core.metrics import calculate_metrics
from models.entities import MetricsResult
from services.llm_service import (
    LLMService,
    ReportSections,
    _GeminiClient,
    _parse_markdown_sections,
)
from services.prompt_builder import (
    PromptBuilder,
    _build_groups_table,
    _build_lifts_table,
    _build_experiment_context,
)
from services.report_service import ReportResponse, ReportService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_metrics() -> MetricsResult:
    df = pd.DataFrame({
        "user_id":    [f"u{i}" for i in range(12)],
        "group":      ["A"] * 6 + ["B"] * 6,
        "gmv":        [100., 200., 150., 0., 120., 180.,
                       130., 260., 200., 0., 150., 220.],
        "commission": [10.,  20.,  15.,  0., 12.,  18.,
                       16.,  32.,  25.,  0., 18.,  27.],
        "cashback":   [5.,   8.,   6.,   0., 5.,   7.,
                       20.,  40.,  30.,  0., 22.,  35.],
        "converted":  [1, 1, 1, 0, 1, 1, 1, 1, 1, 0, 1, 1],
    })
    return calculate_metrics(df, control_group="A")


SAMPLE_MARKDOWN = textwrap.dedent("""\
    ### 1. Resumo Executivo
    O experimento comparou grupos A e B em política de cashback.
    O grupo B apresentou lift positivo em conversão.

    ### 2. Principais Insights
    - Conversão do grupo B foi 10% maior
    - ROI ficou abaixo do esperado

    ### 3. Oportunidades
    Aumentar cashback para segmento mobile pode ampliar o lift.

    ### 4. Riscos
    Custo de cashback cresceu 3x em relação ao controle.

    ### 5. Decisão
    **ITERAR** — o lift é positivo mas o ROI ainda não justifica escala total.

    ### 6. Próximos Passos
    1. [Growth] Rodar experimento segmentado por canal
    2. [Financeiro] Revisar teto de cashback
""")


# ---------------------------------------------------------------------------
# PromptBuilder
# ---------------------------------------------------------------------------

class TestPromptBuilder:

    def test_build_returns_two_strings(self, make_metrics=make_metrics):
        result = make_metrics()
        system, user = PromptBuilder().build(result, experiment_name="Teste Cashback")
        assert isinstance(system, str) and len(system) > 100
        assert isinstance(user, str) and len(user) > 100

    def test_system_prompt_contains_meliuz(self):
        result = make_metrics()
        system, _ = PromptBuilder().build(result)
        assert "Méliuz" in system

    def test_user_prompt_contains_all_sections(self):
        result = make_metrics()
        _, user = PromptBuilder().build(result)
        for section in ["Resumo Executivo", "Principais Insights",
                        "Oportunidades", "Riscos", "Decisão", "Próximos Passos"]:
            assert section in user, f"Seção '{section}' ausente no prompt"

    def test_groups_table_has_all_groups(self):
        result = make_metrics()
        table = _build_groups_table(result)
        assert "Grupo **A**" in table
        assert "Grupo **B**" in table

    def test_groups_table_has_all_metrics(self):
        result = make_metrics()
        table = _build_groups_table(result)
        for metric in ["Compradores", "GMV", "Receita Líquida", "ROI", "Margem"]:
            assert metric in table, f"Métrica '{metric}' ausente na tabela"

    def test_lifts_table_excludes_control(self):
        result = make_metrics()
        table = _build_lifts_table(result)
        # Grupo A é o controle — não deve aparecer como coluna de tratamento
        assert "Grupo **A** vs Controle" not in table
        assert "Grupo **B** vs Controle" in table

    def test_experiment_context_totals(self):
        result = make_metrics()
        context = _build_experiment_context(result, experiment_name="Teste X")
        assert "Teste X" in context
        assert "12" in context   # total_users = 12

    def test_extra_context_included(self):
        result = make_metrics()
        _, user = PromptBuilder().build(result, extra_context="Somente mobile")
        assert "Somente mobile" in user

    def test_three_groups(self):
        df = pd.DataFrame({
            "user_id":   [f"u{i}" for i in range(9)],
            "group":     ["A"] * 3 + ["B"] * 3 + ["C"] * 3,
            "gmv":       [100.] * 9,
            "commission":[10.] * 9,
            "cashback":  [5.] * 9,
            "converted": [1] * 9,
        })
        result = calculate_metrics(df, control_group="A")
        _, user = PromptBuilder().build(result)
        assert "Grupo **C**" in user


# ---------------------------------------------------------------------------
# _parse_markdown_sections
# ---------------------------------------------------------------------------

class TestMarkdownParser:

    def test_all_sections_parsed(self):
        sections = _parse_markdown_sections(SAMPLE_MARKDOWN)
        assert "executive_summary" in sections
        assert "insights" in sections
        assert "opportunities" in sections
        assert "risks" in sections
        assert "decision" in sections
        assert "next_steps" in sections

    def test_decision_content(self):
        sections = _parse_markdown_sections(SAMPLE_MARKDOWN)
        assert "ITERAR" in sections["decision"]

    def test_empty_markdown(self):
        sections = _parse_markdown_sections("")
        assert sections == {}

    def test_partial_markdown(self):
        md = "### 1. Resumo Executivo\nSó o resumo aqui."
        sections = _parse_markdown_sections(md)
        assert "executive_summary" in sections
        assert "insights" not in sections


# ---------------------------------------------------------------------------
# LLMService (com mock do _GeminiClient)
# ---------------------------------------------------------------------------

class TestLLMService:

    def _make_service(self, response_text: str = SAMPLE_MARKDOWN) -> LLMService:
        mock_client = MagicMock(spec=_GeminiClient)
        mock_client.generate.return_value = (
            response_text,
            {"input_tokens": 500, "output_tokens": 800},
        )
        return LLMService(client=mock_client)

    def test_generate_insight_returns_report_sections(self):
        service = self._make_service()
        result = make_metrics()
        report = service.generate_insight(result, experiment_name="Teste")
        assert isinstance(report, ReportSections)
        assert report.raw_markdown == SAMPLE_MARKDOWN

    def test_all_sections_populated(self):
        service = self._make_service()
        result = make_metrics()
        report = service.generate_insight(result)
        assert report.executive_summary != ""
        assert report.insights != ""
        assert report.opportunities != ""
        assert report.risks != ""
        assert report.decision != ""
        assert report.next_steps != ""

    def test_token_counts_captured(self):
        service = self._make_service()
        report = service.generate_insight(make_metrics())
        assert report.input_tokens == 500
        assert report.output_tokens == 800

    def test_latency_recorded(self):
        service = self._make_service()
        report = service.generate_insight(make_metrics())
        assert report.latency_ms >= 0

    def test_retry_on_failure(self):
        mock_client = MagicMock(spec=_GeminiClient)
        # Falha 2× e succeeds na 3ª
        mock_client.generate.side_effect = [
            RuntimeError("timeout"),
            RuntimeError("timeout"),
            (SAMPLE_MARKDOWN, {"input_tokens": 100, "output_tokens": 200}),
        ]
        service = LLMService(client=mock_client, max_retries=3, retry_delay=0)
        report = service.generate_insight(make_metrics())
        assert report.raw_markdown == SAMPLE_MARKDOWN
        assert mock_client.generate.call_count == 3

    def test_exhausted_retries_raises(self):
        mock_client = MagicMock(spec=_GeminiClient)
        mock_client.generate.side_effect = RuntimeError("always fails")
        service = LLMService(client=mock_client, max_retries=2, retry_delay=0)
        with pytest.raises(RuntimeError, match="falhou após"):
            service.generate_insight(make_metrics())

    def test_to_dict_serializable(self):
        service = self._make_service()
        report = service.generate_insight(make_metrics())
        d = report.to_dict()
        assert "raw_markdown" in d
        assert "sections" in d
        assert "meta" in d
        assert set(d["sections"].keys()) == {
            "executive_summary", "insights", "opportunities",
            "risks", "decision", "next_steps",
        }

    def test_from_env_raises_without_key(self):
        with patch.dict("os.environ", {}, clear=True):
            # Remove GEMINI_API_KEY se existir
            import os
            os.environ.pop("GEMINI_API_KEY", None)
            with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                LLMService.from_env()


# ---------------------------------------------------------------------------
# ReportService (integrado, com LLM mockado)
# ---------------------------------------------------------------------------

VALID_CSV = b"""user_id,grupo,gmv,comissao,cashback
u001,A,100.00,10.00,5.00
u002,A,200.00,20.00,8.00
u003,A,150.00,15.00,6.00
u004,B,130.00,16.00,20.00
u005,B,260.00,32.00,40.00
u006,B,200.00,25.00,30.00
"""


class TestReportService:

    def _make_service(self, response_text: str = SAMPLE_MARKDOWN) -> ReportService:
        mock_client = MagicMock(spec=_GeminiClient)
        mock_client.generate.return_value = (
            response_text,
            {"input_tokens": 400, "output_tokens": 700},
        )
        llm = LLMService(client=mock_client, retry_delay=0)
        return ReportService(llm=llm, min_sample_per_group=1)

    def test_full_pipeline_success(self):
        service = self._make_service()
        response = service.run(VALID_CSV, experiment_name="Cashback 15% vs 20%")
        assert response.success
        assert response.metrics is not None
        assert response.report is not None
        assert response.error is None

    def test_response_has_report_id(self):
        service = self._make_service()
        response = service.run(VALID_CSV)
        assert response.report_id != ""

    def test_elapsed_ms_recorded(self):
        service = self._make_service()
        response = service.run(VALID_CSV)
        assert response.elapsed_ms >= 0

    def test_invalid_csv_fails_gracefully(self):
        service = self._make_service()
        response = service.run(b"not,a,valid,csv\n1,2,3,4")
        assert not response.success
        assert response.error is not None

    def test_skip_llm_returns_metrics_only(self):
        mock_client = MagicMock(spec=_GeminiClient)
        llm = LLMService(client=mock_client, retry_delay=0)
        service = ReportService(llm=llm, min_sample_per_group=1, skip_llm=True)
        response = service.run(VALID_CSV)
        assert response.success
        assert response.metrics is not None
        assert response.report is None
        mock_client.generate.assert_not_called()

    def test_to_dict_fully_serializable(self):
        service = self._make_service()
        response = service.run(VALID_CSV)
        d = response.to_dict()
        assert d["success"] is True
        assert d["metrics"] is not None
        assert d["report"] is not None
        assert "groups" in d["metrics"]
