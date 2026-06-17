from typing import List, Tuple
import pandas as pd


def validate_dataframe(df: pd.DataFrame) -> Tuple[List[str], pd.DataFrame]:
    """Valida e limpa o DataFrame retornando lista de issues e o df limpo.

    Issues podem incluir colunas nulas, datas inválidas e negativas em métricas.
    """
    issues = []
    df = df.copy()

    # Detect nulls
    null_counts = df.isnull().sum()
    for col, cnt in null_counts.items():
        if cnt > 0:
            issues.append(f'Coluna {col} possui {int(cnt)} valores nulos')

    # Date conversion
    date_cols = [c for c in df.columns if 'date' in c or 'data' in c]
    for c in date_cols:
        try:
            df[c] = pd.to_datetime(df[c], errors='coerce')
            if df[c].isnull().any():
                issues.append(f'Coluna de data {c} tem valores inválidos')
        except Exception:
            issues.append(f'Falha ao converter data na coluna {c}')

    # Numeric columns conversion heuristics
    num_cols = [c for c in df.columns if any(k in c for k in ['cashback','comissao','comissão','vendas','venda','gmv','compradores','buyers'])]
    for c in num_cols:
        try:
            # remove currency symbols and thousands separators
            df[c] = df[c].astype(str).str.replace(r'[R$\s]', '', regex=True)
            df[c] = df[c].str.replace('\.', '', regex=False)
            df[c] = df[c].str.replace(',', '.', regex=False)
            df[c] = pd.to_numeric(df[c], errors='coerce')
            if df[c].isnull().any():
                issues.append(f'Coluna numérica {c} tem valores não conversíveis')
        except Exception:
            issues.append(f'Falha ao normalizar coluna {c}')

    # Negative checks
    for c in df.columns:
        if any(k in c for k in ['cashback','comissao','comissão','vendas','gmv']):
            try:
                if (df[c].dropna() < 0).any():
                    issues.append(f'Coluna {c} possui valores negativos')
            except Exception:
                pass

    # Ensure group column exists
    group_cols = [c for c in df.columns if any(k in c for k in ['grupo','group','variant'])]
    if not group_cols:
        issues.append('Nenhuma coluna de grupos/variantes encontrada')

    return issues, df
