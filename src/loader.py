from typing import Tuple
import pandas as pd
import io
import re


def _normalize_columns(cols: pd.Index) -> pd.Index:
    def norm(c: str) -> str:
        c = c.strip().lower()
        c = re.sub(r'[^a-z0-9]+', '_', c)
        c = re.sub(r'_+', '_', c).strip('_')
        return c

    return pd.Index([norm(str(c)) for c in cols])


def load_dataframe(source: io.BytesIO) -> pd.DataFrame:
    """Tenta carregar um CSV com heurísticas tolerantes.

    Arguments:
        source: bytes-like stream contendo o CSV

    Returns:
        pd.DataFrame com colunas normalizadas
    """
    # try common encodings/separators
    text = source.getvalue()
    for decimal, thousands in [('.', ','), (',', '.')]:
        try:
            df = pd.read_csv(io.BytesIO(text), sep=None, engine='python', decimal=decimal)
            df.columns = _normalize_columns(df.columns)
            # try convert date-like columns
            return df
        except Exception:
            continue

    # fallback strict
    df = pd.read_csv(io.BytesIO(text))
    df.columns = _normalize_columns(df.columns)
    return df
