"""
services/llm_service.py

Integração com o Google Gemini para geração de relatórios A/B.

Design:
  - LLMService é a classe principal e única interface pública.
  - _GeminiClient encapsula todos os detalhes da API do Gemini.
  - Trocar de Gemini para outro provider exige apenas trocar o _client,
    mantendo LLMService intacto.

Dependência:
    pip install google-generativeai
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from models.entities import MetricsResult
from services.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurações padrão
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "gemini-2.0-flash"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.3      # baixo para análise factual, não criativa
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 2.0      # segundos entre tentativas


# ---------------------------------------------------------------------------
# Dataclasses de saída
# ---------------------------------------------------------------------------

@dataclass
class ReportSections:
    """
    Saída estruturada do LLM.
    O campo `raw_markdown` contém o texto completo.
    Os campos individuais são extraídos para facilitar persistência/frontend.
    """
    raw_markdown: str = ""
    executive_summary: str = ""
    insights: str = ""
    opportunities: str = ""
    risks: str = ""
    decision: str = ""
    next_steps: str = ""

    # Metadados da geração
    model_used: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "raw_markdown": self.raw_markdown,
            "sections": {
                "executive_summary": self.executive_summary,
                "insights":          self.insights,
                "opportunities":     self.opportunities,
                "risks":             self.risks,
                "decision":          self.decision,
                "next_steps":        self.next_steps,
            },
            "meta": {
                "model":         self.model_used,
                "input_tokens":  self.input_tokens,
                "output_tokens": self.output_tokens,
                "latency_ms":    self.latency_ms,
            },
        }


# ---------------------------------------------------------------------------
# Parser de Markdown → seções
# ---------------------------------------------------------------------------

# Mapeamento: título da seção (lowercase) → atributo no ReportSections
_SECTION_MAP = {
    "resumo executivo":   "executive_summary",
    "principais insights":"insights",
    "oportunidades":      "opportunities",
    "riscos":             "risks",
    "decisão":            "decision",
    "decisao":            "decision",
    "próximos passos":    "next_steps",
    "proximos passos":    "next_steps",
}


def _parse_markdown_sections(markdown: str) -> dict[str, str]:
    """
    Extrai seções de um Markdown com headers ### N. Título
    Retorna dict {atributo: conteúdo}.

    Estratégia: finditer para capturar posições exatas de cada header,
    incluindo o primeiro (que pode não ter \n precedente).
    """
    import re

    sections: dict[str, str] = {}
    pattern = re.compile(r"^#{1,3}\s+(?:\d+\.?\s*)?(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(markdown))

    for i, match in enumerate(matches):
        header_text = re.sub(r"\*+", "", match.group(1)).strip()
        key = header_text.lower()
        attr = _SECTION_MAP.get(key)
        if not attr:
            continue
        content_start = match.end()
        content_end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        sections[attr] = markdown[content_start:content_end].strip()

    return sections


# ---------------------------------------------------------------------------
# Cliente Gemini
# ---------------------------------------------------------------------------

class _GeminiClient:
    """Encapsula a comunicação com a API do Google Gemini."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        max_output_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise ImportError(
                "Pacote 'google-generativeai' não instalado. "
                "Execute: pip install google-generativeai"
            ) from exc

        genai.configure(api_key=api_key)

        self._generation_config = {
            "max_output_tokens": max_output_tokens,
            "temperature": temperature,
        }
        self._model_name = model
        self._timeout = timeout
        self._genai = genai

        logger.info("GeminiClient inicializado com modelo '%s'.", model)

    def generate(self, system_prompt: str, user_prompt: str) -> tuple[str, dict]:
        """
        Envia o prompt e retorna (texto_gerado, metadados).
        metadados: {"input_tokens": int, "output_tokens": int}
        """
        model = self._genai.GenerativeModel(
            model_name=self._model_name,
            generation_config=self._generation_config,
            system_instruction=system_prompt,
        )

        response = model.generate_content(
            user_prompt,
            request_options={"timeout": self._timeout},
        )

        text = response.text

        # Extrai contagem de tokens se disponível
        meta: dict = {"input_tokens": 0, "output_tokens": 0}
        try:
            usage = response.usage_metadata
            meta["input_tokens"]  = getattr(usage, "prompt_token_count", 0) or 0
            meta["output_tokens"] = getattr(usage, "candidates_token_count", 0) or 0
        except Exception:
            pass

        return text, meta


# ---------------------------------------------------------------------------
# Serviço principal
# ---------------------------------------------------------------------------

class LLMService:
    """
    Gera relatórios executivos de experimentos A/B via LLM.

    Uso:
        service = LLMService.from_env()
        report = service.generate_insight(metrics_result)
        print(report.raw_markdown)
    """

    def __init__(
        self,
        client: _GeminiClient,
        prompt_builder: Optional[PromptBuilder] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ) -> None:
        self._client = client
        self._builder = prompt_builder or PromptBuilder()
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    # ------------------------------------------------------------------
    @classmethod
    def from_env(
        cls,
        model: str = DEFAULT_MODEL,
        max_output_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> "LLMService":
        """
        Cria o serviço lendo GEMINI_API_KEY do ambiente.
        Levanta ValueError se a chave não estiver definida.
        """
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise ValueError(
                "Variável de ambiente GEMINI_API_KEY não definida. "
                "Defina-a antes de instanciar o LLMService."
            )
        client = _GeminiClient(
            api_key=api_key,
            model=model,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )
        return cls(client=client)

    @classmethod
    def from_api_key(
        cls,
        api_key: str,
        model: str = DEFAULT_MODEL,
        max_output_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> "LLMService":
        """Cria o serviço com a chave fornecida diretamente."""
        client = _GeminiClient(
            api_key=api_key,
            model=model,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )
        return cls(client=client)

    # ------------------------------------------------------------------
    def generate_insight(
        self,
        result: MetricsResult,
        experiment_name: Optional[str] = None,
        extra_context: Optional[str] = None,
    ) -> ReportSections:
        """
        Pipeline completo:
          1. Constrói o prompt a partir do MetricsResult
          2. Envia ao Gemini com retry automático
          3. Parseia o Markdown de volta em seções estruturadas
          4. Retorna ReportSections

        Args:
            result:          Saída do MetricsCalculator.
            experiment_name: Nome legível do experimento (opcional).
            extra_context:   Texto livre com contexto adicional do time
                             (ex.: "Experimento rodou apenas para mobile").

        Returns:
            ReportSections com raw_markdown + seções individuais.
        """
        logger.info(
            "Gerando insight para experimento '%s' (%d grupos)…",
            experiment_name or "sem nome",
            len(result.groups),
        )

        # 1. Construir prompt
        system_prompt, user_prompt = self._builder.build(
            result,
            experiment_name=experiment_name,
            extra_context=extra_context,
        )

        # 2. Chamar LLM com retry
        markdown, meta, latency_ms = self._call_with_retry(system_prompt, user_prompt)

        # 3. Parsear seções
        sections_dict = _parse_markdown_sections(markdown)

        report = ReportSections(
            raw_markdown=markdown,
            executive_summary=sections_dict.get("executive_summary", ""),
            insights=sections_dict.get("insights", ""),
            opportunities=sections_dict.get("opportunities", ""),
            risks=sections_dict.get("risks", ""),
            decision=sections_dict.get("decision", ""),
            next_steps=sections_dict.get("next_steps", ""),
            model_used=DEFAULT_MODEL,
            input_tokens=meta.get("input_tokens", 0),
            output_tokens=meta.get("output_tokens", 0),
            latency_ms=latency_ms,
        )

        logger.info(
            "Relatório gerado em %dms | tokens: %d in / %d out",
            latency_ms,
            report.input_tokens,
            report.output_tokens,
        )
        return report

    # ------------------------------------------------------------------
    def _call_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[str, dict, int]:
        """
        Chama o LLM com até `max_retries` tentativas em caso de erro.
        Retorna (texto, metadados, latencia_ms).
        """
        last_error: Optional[Exception] = None

        for attempt in range(1, self._max_retries + 1):
            try:
                t0 = time.monotonic()
                text, meta = self._client.generate(system_prompt, user_prompt)
                latency_ms = int((time.monotonic() - t0) * 1000)
                logger.debug("LLM respondeu em %dms (tentativa %d).", latency_ms, attempt)
                return text, meta, latency_ms

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Tentativa %d/%d falhou: %s", attempt, self._max_retries, exc
                )
                if attempt < self._max_retries:
                    delay = self._retry_delay * attempt  # backoff linear
                    logger.info("Aguardando %.1fs antes de tentar novamente…", delay)
                    time.sleep(delay)

        raise RuntimeError(
            f"LLM falhou após {self._max_retries} tentativa(s). "
            f"Último erro: {last_error}"
        )
