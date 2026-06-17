"""
core/parser.py
Lê CSVs agregados por dia no formato:
    data | grupo | parceiro | compradores | comissão | cashback | vendas totais
"""

from __future__ import annotations

import io
import logging
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)

COLUMN_ALIASES: Dict[str, List[str]] = {
    "date":       ["date", "data", "order_date", "data_pedido", "created_at", "dt"],
    "group":      ["group", "grupo", "variant", "variante", "ab_group", "test_group",
                   "segmento", "grupos", "grupos_de_usuarios", "grupos_de_usuários"],
    "partner":    ["partner", "merchant", "loja", "parceiro", "seller", "store"],
    "buyers":     ["buyers", "compradores", "comprador", "converted", "convertido",
                   "purchased", "is_buyer", "has_order"],
    "commission": ["commission", "comissao", "comissão", "fee", "taxa",
                   "commission_value", "valor_comissao"],
    "cashback":   ["cashback", "cashback_value", "valor_cashback", "cb",
                   "cashback_amount", "cashback_brl"],
    "gmv":        ["gmv", "gross_merchandise_value", "valor_pedido", "order_value",
                   "valor_bruto", "gmv_brl", "amount", "vendas", "vendas_totais",
                   "vendas totais", "total_vendas"],
}

REQUIRED_CANONICAL: List[str] = ["group", "gmv", "commission", "cashback", "buyers"]
ENCODINGS_TO_TRY: List[str] = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]


def _normalize_name(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name.strip().lower())
    ascii_name = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return re.sub(r"[^a-z0-9]+", "_", ascii_name).strip("_")


def _build_rename_map(columns: List[str]) -> Dict[str, str]:
    reverse: Dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            reverse[_normalize_name(alias)] = canonical
    return {col: reverse[_normalize_name(col)] for col in columns if _normalize_name(col) in reverse}


def _read_raw(source: Union[str, Path, bytes, io.IOBase]) -> pd.DataFrame:
    if isinstance(source, (str, Path)):
        raw_bytes = Path(source).read_bytes()
    elif isinstance(source, bytes):
        raw_bytes = source
    else:
        raw_bytes = source.read()

    last_error: Optional[Exception] = None
    for enc in ENCODINGS_TO_TRY:
        for sep in [",", ";", "\t", "|"]:
            try:
                df = pd.read_csv(
                    io.BytesIO(raw_bytes), sep=sep, encoding=enc,
                    engine="python", on_bad_lines="warn",
                    dtype=str, skipinitialspace=True,
                )
                if df.shape[1] < 2:
                    continue
                logger.debug("CSV lido: encoding=%s sep=%r linhas=%d", enc, sep, len(df))
                return df
            except Exception as exc:
                last_error = exc

    raise ValueError(f"Não foi possível ler o CSV. Último erro: {last_error}")


def _clean_monetary(series: pd.Series) -> pd.Series:
    """
    Suporta os formatos:
      - R$ 37.908        → ponto como milhar, sem decimal  → 37908.0
      - R$ 37.908,50     → ponto como milhar, vírgula decimal → 37908.5
      - R$ 37,908.50     → vírgula como milhar, ponto decimal → 37908.5
      - 37908.50         → ponto decimal simples → 37908.5
    """
    s = series.astype(str).str.strip()
    # Remove prefixo monetário e espaços
    s = s.str.replace(r"[R$\s]", "", regex=True)

    # Detecta o formato pelo padrão de separadores presentes
    has_dot_comma   = s.str.contains(r"\d\.\d{3},", na=False).any()   # 37.908,50
    has_comma_dot   = s.str.contains(r"\d,\d{3}\.", na=False).any()   # 37,908.50
    # Ponto como milhar SEM decimal (ex: 37.908 — exatamente 3 dígitos após o ponto no fim)
    has_dot_milhar  = s.str.contains(r"\.\d{3}$", na=False).any()

    if has_dot_comma:
        # Formato BR completo: 1.234,56
        s = s.str.replace(".", "", regex=False)
        s = s.str.replace(",", ".", regex=False)
    elif has_comma_dot:
        # Formato EN com vírgula de milhar: 1,234.56
        s = s.str.replace(",", "", regex=False)
    elif has_dot_milhar:
        # Ponto é separador de milhar sem casas decimais: 37.908
        s = s.str.replace(".", "", regex=False)
    else:
        # Vírgula como decimal sem milhar: 37,5 → 37.5
        s = s.str.replace(",", ".", regex=False)

    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def _parse_dates(series: pd.Series) -> pd.Series:
    """
    Tenta múltiplos formatos de data para evitar NaT.
    Prioriza ISO (YYYY-MM-DD) e depois formatos BR (DD/MM/YYYY).
    """
    # Tenta ISO primeiro (mais comum em CSVs gerados por sistemas)
    parsed = pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")
    # Para as que falharam, tenta dayfirst
    mask = parsed.isna()
    if mask.any():
        parsed[mask] = pd.to_datetime(series[mask], dayfirst=True, errors="coerce")
    # Última tentativa: inferência automática
    mask = parsed.isna()
    if mask.any():
        parsed[mask] = pd.to_datetime(series[mask], infer_datetime_format=True, errors="coerce")
    return parsed


class ABParser:
    def __init__(self, min_rows: int = 1) -> None:
        self.min_rows = min_rows

    def parse(self, source: Union[str, Path, bytes, io.IOBase]) -> pd.DataFrame:
        logger.info("Iniciando parsing do CSV…")
        df = _read_raw(source)
        df = df.dropna(how="all").dropna(axis=1, how="all")
        df.columns = df.columns.str.strip()

        rename_map = _build_rename_map(df.columns.tolist())
        df = df.rename(columns=rename_map)
        logger.debug("Colunas após rename: %s", df.columns.tolist())

        missing = [c for c in REQUIRED_CANONICAL if c not in df.columns]
        if missing:
            raise ValueError(
                f"Colunas obrigatórias ausentes: {missing}. "
                f"Colunas encontradas: {df.columns.tolist()}"
            )

        # Monetários
        for col in ["gmv", "commission", "cashback"]:
            df[col] = _clean_monetary(df[col])

        # Compradores — número inteiro
        df["buyers"] = pd.to_numeric(df["buyers"], errors="coerce").fillna(0).astype(int)

        # Data
        if "date" in df.columns:
            df["date"] = _parse_dates(df["date"])

        # Grupo
        df = df.dropna(subset=["group"])
        df["group"] = df["group"].astype(str).str.strip().str.upper()

        if len(df) < self.min_rows:
            raise ValueError(f"Apenas {len(df)} linha(s) após limpeza (mínimo: {self.min_rows}).")

        logger.info("Parsing concluído. Shape: %s | Grupos: %s", df.shape, sorted(df["group"].unique()))
        return df.reset_index(drop=True)


def build_preview(df: pd.DataFrame, n_rows: int = 5) -> Dict:
    return {
        "total_rows":     len(df),
        "columns":        df.columns.tolist(),
        "groups":         sorted(df["group"].unique().tolist()),
        "rows_per_group": df["group"].value_counts().to_dict(),
        "sample":         df.head(n_rows).to_dict(orient="records"),
    }