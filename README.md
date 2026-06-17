# Analisador AI-Native de Testes A/B de Cashback

Este projeto fornece uma ferramenta local simples (Streamlit) para analisar experimentos A/B de cashback.

Como executar:

1. Criar ambiente virtual e instalar dependências:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Copie `.env.example` para `.env` e preencha as chaves (opcional: OpenAI, Google Sheets).

3. Executar a aplicação:

```bash
streamlit run app.py
```

Arquivos principais:

- `app.py`: UI e orquestração
- `src/loader.py`: leitura tolerante de CSV
- `src/validator.py`: limpeza/validação
- `src/metrics.py`: cálculo de métricas
- `src/decision_engine.py`: ranking de variantes
- `src/ai_analysis.py`: integração com IA (OpenAI)
- `src/report_generator.py`: gera Markdown de relatório
- `src/sheets.py`: integração com Google Sheets / fallback CSV
