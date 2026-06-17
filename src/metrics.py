from typing import Tuple, Dict, Optional
import pandas as pd


def _find_column(df: pd.DataFrame, keywords, prefer_numeric: bool = True) -> Optional[str]:
    # first try exact keyword match in column names
    cols = [c for c in df.columns if any(k in c for k in keywords)]
    if not cols:
        return None
    if prefer_numeric:
        for c in cols:
            if pd.api.types.is_numeric_dtype(df[c]):
                return c
        # try coerced numeric
        for c in cols:
            coerced = pd.to_numeric(df[c], errors='coerce')
            if coerced.notna().any():
                df[c] = coerced
                return c
    return cols[0]


def compute_group_metrics(df: pd.DataFrame, group_col: str) -> Tuple[pd.DataFrame, Dict]:
    """Computa métricas agregadas por grupo e métricas derivadas de forma robusta.

    Retorna (metrics_df, summary_dict)
    """
    # detect candidate columns
    buyers_col = _find_column(df, ['comprador', 'buyer', 'compradores'])
    commission_col = _find_column(df, ['comissao', 'comissão', 'commission'])
    cashback_col = _find_column(df, ['cashback'])
    gmv_col = _find_column(df, ['vendas', 'venda', 'gmv'])

    # prepare a working copy
    df2 = df.copy()

    # coerce identified numeric columns
    for col in [buyers_col, commission_col, cashback_col, gmv_col]:
        if col and not pd.api.types.is_numeric_dtype(df2[col]):
            df2[col] = pd.to_numeric(df2[col], errors='coerce').fillna(0)

    # group and aggregate safely
    g = df2.groupby(group_col)

    agg_dict = {}
    # buyers: prefer sum if buyers column exists, else use count
    if buyers_col:
        agg_dict['buyers'] = (buyers_col, 'sum')
    else:
        # still aggregate a count internally so we can compute rates, but
        # we will not expose 'buyers' in the returned table.
        agg_dict['buyers'] = (group_col, 'count')

    if commission_col:
        agg_dict['commission'] = (commission_col, 'sum')
    else:
        agg_dict['commission'] = (group_col, lambda s: 0.0)

    if cashback_col:
        agg_dict['cashback'] = (cashback_col, 'sum')
    else:
        agg_dict['cashback'] = (group_col, lambda s: 0.0)

    if gmv_col:
        agg_dict['gmv'] = (gmv_col, 'sum')
    else:
        agg_dict['gmv'] = (group_col, lambda s: 0.0)

    agg = g.agg(**agg_dict)
    # If buyers was a count on group_col, rename the resulting column
    agg = agg.reset_index()
    agg = agg.rename(columns={group_col: 'group'})

    # ensure numeric dtype
    for c in ['buyers', 'commission', 'cashback', 'gmv']:
        if c not in agg.columns:
            agg[c] = 0
        agg[c] = pd.to_numeric(agg[c], errors='coerce').fillna(0)

    # Derived metrics
    agg['net_revenue'] = agg['commission'] - agg['cashback']
    # denom: use buyers when available/positive, else fall back to total_users (row count)
    if 'user_id' in df2.columns:
        total_users_series = df2.groupby(group_col)['user_id'].nunique()
    else:
        total_users_series = df2.groupby(group_col).size()
    total_users_series = total_users_series.rename('total_users')
    # merge total_users into agg
    agg = agg.merge(total_users_series.reset_index(), how='left', left_on=group_col if group_col in agg.columns else 'group', right_on=group_col, suffixes=('', '_t'))
    if 'total_users' not in agg.columns:
        agg['total_users'] = agg[group_col] if group_col in agg.columns else agg['group']

    denom = agg['buyers'].where(agg['buyers'] > 0, agg['total_users'])
    agg['ticket_avg'] = agg['gmv'] / denom.replace({0: 1})
    agg['cashback_avg'] = agg['cashback'] / denom.replace({0: 1})
    agg['commission_per_buyer'] = agg['commission'] / denom.replace({0: 1})
    agg['roi'] = agg.apply(lambda r: r['commission'] / r['cashback'] if r['cashback'] and r['cashback'] > 0 else 0.0, axis=1)
    agg['margin_over_commission'] = agg.apply(lambda r: (r['commission'] - r['cashback']) / r['commission'] if r['commission'] and r['commission'] > 0 else 0.0, axis=1)

    # Do not expose the 'buyers' column (user requested its removal)
    if 'buyers' in agg.columns:
        agg = agg.drop(columns=['buyers'])

    summary = {
        'total_groups': len(agg),
        'total_users': int(agg['total_users'].sum()) if 'total_users' in agg.columns else 0,
        'total_commission': float(agg['commission'].sum()),
        'total_cashback': float(agg['cashback'].sum()),
        'total_gmv': float(agg['gmv'].sum())
    }

    return agg, summary
