from typing import Tuple
import pandas as pd


def rank_variants(metrics_df: pd.DataFrame) -> pd.DataFrame:
    """Gera ranking das variantes usando pontuação ponderada.

    Prioridades (default): receita líquida, ROI, crescimento de compradores, GMV
    """
    df = metrics_df.copy()
    # normalize columns to 0-1
    for col in ['net_revenue', 'roi', 'gmv']:
        if col in df:
            minv = df[col].min()
            maxv = df[col].max()
            if maxv - minv == 0:
                df[col + '_n'] = 0.0
            else:
                df[col + '_n'] = (df[col] - minv) / (maxv - minv)
        else:
            df[col + '_n'] = 0.0

    # weights
    w_net = 0.6
    w_roi = 0.3
    w_gmv = 0.1

    df['score'] = df['net_revenue_n'] * w_net + df['roi_n'] * w_roi + df['gmv_n'] * w_gmv
    df = df.sort_values('score', ascending=False).reset_index(drop=True)
    df['rank'] = df.index + 1
    return df[['rank','group','score'] + [c for c in df.columns if c.endswith('_n')]]
