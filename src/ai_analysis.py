import os
import json
from typing import Dict

try:
    import openai
except Exception:
    openai = None


def _build_prompt(summary: Dict, ranking, partner: str, period: str) -> str:
    parts = []
    parts.append(f"Você é um analista sênior de Growth da Méliuz. Analise o experimento do parceiro {partner} no período {period}.")
    parts.append("Resumo das métricas por grupo:")
    for _, row in ranking.iterrows():
        parts.append(f"Grupo {row['group']}: score {row['score']:.4f}")
    parts.append("Forneça: resumo executivo, principais insights, oportunidades, riscos, decisão (qual variante escalar) e próximos passos.")
    return "\n".join(parts)


def analyze_with_ai(summary: Dict, ranking, partner: str, period: str) -> str:
    """Chama o provider de IA (OpenAI) para gerar análise textual.

    Se a chave não estiver disponível, retorna um resumo simples local.
    """
    api_key = os.getenv('OPENAI_API_KEY')
    model = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
    prompt = _build_prompt(summary, ranking, partner, period)

    if not api_key or openai is None:
        # fallback: simple template
        winner = ranking.iloc[0]['group'] if len(ranking) else 'N/A'
        return f"Decisão: escalar {winner}.\nMotivo: baseado na pontuação automática. (OpenAI não configurado)"

    try:
        openai.api_key = api_key
        resp = openai.ChatCompletion.create(
            model=model,
            messages=[{'role':'system','content':'Você é um analista sênior de Growth da Méliuz.'},{'role':'user','content':prompt}],
            temperature=0.2,
            max_tokens=700,
        )
        text = resp['choices'][0]['message']['content']
        return text
    except Exception as e:
        return f"Falha ao chamar IA: {e}"
