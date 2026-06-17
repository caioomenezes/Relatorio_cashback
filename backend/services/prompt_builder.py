"""
services/prompt_builder.py

Responsável por transformar um MetricsResult (dados quantitativos) em um
prompt textual rico e estruturado, pronto para ser enviado ao LLM.

Separação de responsabilidades:
  - Este módulo sabe TUDO sobre formatação de contexto.
  - O LLMService sabe TUDO sobre comunicação com a API.
  - Trocar o modelo (Gemini → Claude → GPT) não exige mudar nada aqui.
"""

from __future__ import annotations

import logging
from typing import Optional

from models.entities import GroupStats, MetricsResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt — persona e instruções de saída
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
Você é um Analista Sênior de Growth da Méliuz, especialista em experimentos \
A/B de cashback e monetização de plataformas de fidelidade.

Sua função é interpretar resultados de testes A/B e produzir relatórios \
executivos claros, orientados a decisão, que serão lidos pelo time de \
Produto e pela liderança de Growth.

Diretrizes de análise:
- Priorize impacto econômico real: receita líquida, margem e ROI sobre \
cashback são mais importantes do que GMV bruto.
- Cashback é um custo de aquisição/retenção — avalie sempre o trade-off \
custo × receita gerada.
- Seja direto: termine SEMPRE com uma Decisão clara (escalar / não escalar / \
iterar).
- Use linguagem de negócio, não estatística. Evite jargões técnicos sem \
explicação.
- Quando houver múltiplos grupos de tratamento, compare cada um contra o \
controle E entre si.

Formato de saída: Markdown estruturado, com as seções exatas listadas \
abaixo, na mesma ordem. Não adicione seções extras.
"""

# ---------------------------------------------------------------------------
# Template de prompt de usuário
# ---------------------------------------------------------------------------

USER_PROMPT_TEMPLATE = """\
## Contexto do Experimento

{experiment_context}

---

## Dados Quantitativos por Grupo

{groups_table}

---

## Lifts vs. Grupo de Controle ({control_group})

{lifts_table}

---

## Instruções para o Relatório

Analise os dados acima e produza um relatório executivo completo com \
**exatamente** as seguintes seções, nesta ordem:

### 1. Resumo Executivo
Um parágrafo de até 5 linhas resumindo o que foi testado e o resultado \
principal.

### 2. Principais Insights
Bullet points (máx. 6) com os achados mais relevantes, sempre associando \
a métrica ao impacto de negócio.

### 3. Oportunidades
O que este experimento revela de oportunidade de crescimento ou otimização? \
Seja específico sobre alavancas (ex.: aumentar cashback em X% para o segmento Y).

### 4. Riscos
Quais riscos econômicos, de experiência do usuário ou operacionais existem \
se escalarmos o grupo vencedor? Inclua riscos de dados se houver sinais de \
inconsistência.

### 5. Decisão
Uma linha clara: **[ESCALAR / NÃO ESCALAR / ITERAR]** — seguida de \
1-2 frases justificando.

### 6. Próximos Passos
Lista ordenada de ações concretas (máx. 5), com responsável sugerido \
(ex.: "Growth", "Produto", "Data", "Financeiro").

---

Responda apenas com o relatório em Markdown. Não inclua introdução, \
saudação ou texto fora das seções.
"""

# ---------------------------------------------------------------------------
# Formatadores auxiliares
# ---------------------------------------------------------------------------

_METRIC_LABELS = {
    "total_users":            "Usuários Totais",
    "conversion_rate":        "Taxa de Conversão",
    "gmv":                    "GMV (R$)",
    "commission":             "Comissão (R$)",
    "cashback":               "Cashback (R$)",
    "net_revenue":            "Receita Líquida (R$)",
    "avg_ticket":             "Ticket Médio (R$)",
    "avg_cashback":           "Cashback Médio (R$)",
    "commission_per_buyer":   "Comissão / Comprador (R$)",
    "roi":                    "ROI (receita líq. / cashback)",
    "margin":                 "Margem (%)",
}

_LIFT_LABELS = {
    "conversion_rate": "Conversão",
    "gmv":             "GMV",
    "net_revenue":     "Receita Líquida",
    "roi":             "ROI",
    "margin":          "Margem",
}


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _fmt_currency(value: float) -> str:
    return f"R$ {value:,.2f}"


def _fmt_roi(value: float) -> str:
    if value == float("inf"):
        return "∞"
    return f"{value:.2f}x"


def _group_stats_to_rows(gs: GroupStats) -> dict:
    """Converte GroupStats em dict de strings formatadas para a tabela."""
    return {
        "Usuários Totais":          str(gs.total_users),
        "Taxa de Conversão":        _fmt_pct(gs.conversion_rate),
        "GMV (R$)":                 _fmt_currency(gs.gmv),
        "Comissão (R$)":            _fmt_currency(gs.commission),
        "Cashback (R$)":            _fmt_currency(gs.cashback),
        "Receita Líquida (R$)":     _fmt_currency(gs.net_revenue),
        "Ticket Médio (R$)":        _fmt_currency(gs.avg_ticket),
        "Cashback Médio (R$)":      _fmt_currency(gs.avg_cashback),
        "Comissão / Comprador (R$)":_fmt_currency(gs.commission_per_buyer),
        "ROI":                      _fmt_roi(gs.roi),
        "Margem (%)":               _fmt_pct(gs.margin),
    }


def _build_groups_table(result: MetricsResult) -> str:
    """
    Monta tabela Markdown comparando todos os grupos lado a lado.

    | Métrica            | Grupo A | Grupo B | Grupo C |
    |--------------------|---------|---------|---------|
    | Compradores        |  1.200  |  1.350  |  1.180  |
    ...
    """
    group_names = list(result.groups.keys())
    rows_per_group = {name: _group_stats_to_rows(gs) for name, gs in result.groups.items()}

    # Cabeçalho
    header = "| Métrica | " + " | ".join(f"Grupo **{n}**" for n in group_names) + " |"
    separator = "|---|" + "---|" * len(group_names)

    # Uma linha por métrica
    metric_keys = list(next(iter(rows_per_group.values())).keys())
    data_rows = []
    for key in metric_keys:
        cells = " | ".join(rows_per_group[name].get(key, "—") for name in group_names)
        data_rows.append(f"| {key} | {cells} |")

    return "\n".join([header, separator] + data_rows)


def _build_lifts_table(result: MetricsResult) -> str:
    """
    Monta tabela de lifts vs. grupo de controle.

    | Métrica      | Grupo B  | Grupo C  |
    |--------------|----------|----------|
    | Conversão    | +12,00%  | +3,00%   |
    ...
    """
    treatment_groups = [n for n in result.groups if n != result.control_group]
    if not treatment_groups:
        return "_Sem grupos de tratamento para comparar._"

    header = "| Métrica | " + " | ".join(f"Grupo **{n}** vs Controle" for n in treatment_groups) + " |"
    separator = "|---|" + "---|" * len(treatment_groups)

    data_rows = []
    for metric_key, label in _LIFT_LABELS.items():
        cells = []
        for name in treatment_groups:
            group_lifts = result.lifts.get(name, {})
            val = group_lifts.get(metric_key)
            if val is None:
                cells.append("—")
            else:
                sign = "+" if val >= 0 else ""
                cells.append(f"{sign}{val * 100:.2f}%")
        data_rows.append(f"| {label} | " + " | ".join(cells) + " |")

    return "\n".join([header, separator] + data_rows)


def _build_experiment_context(
    result: MetricsResult,
    experiment_name: Optional[str] = None,
    extra_context: Optional[str] = None,
) -> str:
    """Constrói o bloco de contexto narrativo do experimento."""
    groups = list(result.groups.keys())
    control = result.control_group
    treatments = [g for g in groups if g != control]

    total_users = sum(gs.total_users for gs in result.groups.values())
    total_cashback = sum(gs.cashback for gs in result.groups.values())

    lines = [
        f"**Experimento:** {experiment_name or 'Teste A/B de Cashback'}",
        f"**Grupos:** {', '.join(groups)} "
        f"(controle: **{control}** | tratamento(s): **{', '.join(treatments)}**)",
        f"**Total de usuários:** {total_users:,}",
        f"**Investimento total em cashback:** {_fmt_currency(total_cashback)}",
    ]

    if extra_context:
        lines += ["", "**Contexto adicional fornecido pelo time:**", extra_context]

    return "\n".join(line for line in lines if line)


# ---------------------------------------------------------------------------
# Classe pública
# ---------------------------------------------------------------------------

class PromptBuilder:
    """
    Constrói o par (system_prompt, user_prompt) a partir de um MetricsResult.

    Uso:
        builder = PromptBuilder()
        system, user = builder.build(metrics_result)
    """

    def build(
        self,
        result: MetricsResult,
        experiment_name: Optional[str] = None,
        extra_context: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Retorna (system_prompt, user_prompt) prontos para envio ao LLM.
        """
        experiment_context = _build_experiment_context(
            result, experiment_name, extra_context
        )
        groups_table = _build_groups_table(result)
        lifts_table = _build_lifts_table(result)

        user_prompt = USER_PROMPT_TEMPLATE.format(
            experiment_context=experiment_context,
            groups_table=groups_table,
            lifts_table=lifts_table,
            control_group=result.control_group or "A",
        )

        logger.debug(
            "Prompt construído — system: %d chars | user: %d chars",
            len(SYSTEM_PROMPT),
            len(user_prompt),
        )

        return SYSTEM_PROMPT, user_prompt
