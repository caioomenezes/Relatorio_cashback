
# Analisador A/B de Cashback

Aplicação web para analisar experimentos A/B de campanhas de cashback. O usuário faz upload de um CSV com os dados do experimento, o sistema calcula as métricas de cada grupo, aponta qual variante teve melhor desempenho, gera um resumo em linguagem natural e permite exportar tudo em um PDF ou registrar o resultado em uma planilha.

Este README cobre a versão web do projeto: backend em **FastAPI** (`backend/`) e frontend em **React** (raiz do repositório, rodado com `npm run dev`).

## Por que este projeto existe

Times de growth e marketing rodam testes A/B de cashback com frequência, mas normalmente dependem de alguém com conhecimento técnico (ou de planilhas manuais) para transformar um CSV de exportação em uma decisão clara: qual variante venceu e por quê. Este projeto automatiza essa ponte — da planilha bruta até a recomendação final — e foi pensado desde o início para que **pessoas sem conhecimento técnico também consigam gerar e interpretar o relatório**, sem depender de outra pessoa para traduzir os números.

Isso aparece em duas decisões concretas do projeto, detalhadas mais abaixo: o glossário de métricas embutido no relatório, e a exportação em PDF pronta para repasse.

## Como as métricas são calculadas

O sistema não pede que o usuário informe métricas prontas — ele deriva tudo a partir de colunas brutas que já existem no CSV do experimento (grupo, vendas/GMV, comissão e cashback). A partir dessas quatro colunas, o backend calcula por grupo:

- **GMV**: soma do volume de vendas do grupo.
- **Comissão**: soma da comissão recebida sobre as vendas do grupo.
- **Cashback**: soma do valor de cashback pago aos usuários do grupo (o custo do incentivo).
- **Receita líquida**: `comissão − cashback`.
- **ROI**: `receita líquida ÷ cashback`.
- **Margem**: `receita líquida ÷ GMV`.
- **Ticket médio**: `GMV ÷ número de compradores`.
- **Cashback médio**: `cashback ÷ número de compradores`.
- **Comissão por comprador**: `comissão ÷ número de compradores`.

Todas essas métricas derivadas vivem em `models/entities.py` (classe `GroupStats`) e são populadas pelo pipeline de análise a partir do CSV recebido em `/analyze`.

## Por que ROI é a métrica principal de decisão

Entre as métricas calculadas, o **ROI** foi escolhido como critério principal para apontar o grupo vencedor, em vez de métricas absolutas como GMV ou receita líquida em reais. A razão é que ROI mede **eficiência do investimento**: quanto retorno em receita líquida cada real gasto em cashback gerou, e não o tamanho do grupo.

Isso é importante porque GMV e receita líquida absoluta tendem a favorecer naturalmente o grupo com mais usuários ou mais tráfego, mesmo que esse grupo seja menos eficiente por usuário. O ROI normaliza essa diferença e permite comparar grupos de tamanhos distintos pela mesma régua, respondendo à pergunta que realmente importa para quem vai decidir o orçamento: "se eu escalar este grupo, cada real adicional de cashback vai continuar valendo a pena?"

## Identificação de possíveis erros nos dados

Antes de qualquer decisão ser tomada com base nos números, o sistema roda uma verificação automática de anomalias nos dados recebidos (função `detectAnomalies`, no componente `ReportSection`). Ela cobre, entre outros, os seguintes casos:

- Avisos repassados pelo próprio backend durante a validação do CSV (ex: coluna de cashback ausente).
- Cashback de um grupo idêntico à sua comissão — sinal comum de erro de origem, como uma coluna duplicada por engano, que zeraria a receita líquida e o ROI daquele grupo.
- Receita líquida negativa, indicando que o cashback pago superou a comissão gerada.
- ROI igual a zero mesmo com comissão positiva, o que pode indicar um problema no cálculo ou nos dados de cashback daquele grupo.
- Grupos com usuários cadastrados mas nenhum comprador, indicando conversão zerada.
- Lifts (variações percentuais) extremos entre grupos, acima de 200%, que costumam apontar para amostras desproporcionais ou erro de dado, não para um resultado real.

Esses avisos aparecem em um card próprio do relatório ("Avisos da Análise") e não bloqueiam a análise — servem para que quem for tomar a decisão saiba investigar a origem dos dados antes de agir sobre eles.

## Glossário de métricas no relatório

Cada métrica que aparece no relatório também é explicada dentro do próprio relatório, em um card de "Glossário de Métricas": para cada uma, o sistema mostra o que ela é (a fórmula, em linguagem simples) e para que ela serve (como interpretá-la na prática). Essa decisão existe justamente para que alguém sem bagagem técnica em growth ou estatística consiga abrir o relatório e entender, sozinho, o que está sendo medido e por que o sistema recomendou um grupo em vez de outro — sem precisar perguntar para outra pessoa o que "ROI" ou "margem" significam ali.

## Exportação em PDF

O botão "Exportar PDF" do relatório gera um PDF a partir da própria tela do relatório (incluindo o resumo dos resultados, os avisos de anomalias e o glossário de métricas). Isso é parte da mesma decisão de projeto: como o PDF é uma cópia fiel do que aparece na tela — explicações incluídas — ele pode ser repassado para qualquer pessoa (um gestor, um parceiro, alguém de outra área) sem que essa pessoa precise ter acesso ao sistema ou conhecimento técnico prévio para entender o conteúdo. O relatório se explica por si só.

## Estrutura do projeto

```
ab-cashback/
├── backend/
│   ├── api_server.py      # API FastAPI — endpoints /analyze, /report, /append
│   └── sheets.py          # Escrita de resultados no Google Sheets
├── core/                  # Pipeline de análise (validação, cálculo de métricas)
├── models/
│   └── entities.py        # Estruturas de dados (GroupStats, MetricsResult, etc.)
├── components/
│   ├── report/
│   │   └── ReportSection.jsx   # Relatório, glossário de métricas e exportação em PDF
│   └── dashboard/
│       └── MetricsDashboard.jsx
├── App.jsx                # Componente raiz do frontend
├── requirements.txt       # Dependências Python (backend)
└── package.json           # Dependências e scripts do frontend (React)
```

## Como rodar o projeto localmente

### Pré-requisitos

- Python 3.10+ instalado
- Node.js e npm instalados

### 1. Backend (FastAPI)

Crie e ative um ambiente virtual Python na raiz do projeto:

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python -m venv venv
source venv/bin/activate
```

Instale as dependências (com o venv ativado):

```bash
pip install -r requirements.txt
```

Entre na pasta `backend/` e suba a API com Uvicorn:

```bash
cd backend
uvicorn api_server:app --reload --port 8000
```

A API ficará disponível em `http://localhost:8000`.

### 2. Frontend (React)

Em outro terminal, na raiz do projeto (`ab-cashback/`):

```bash
npm install
npm run dev
```

O frontend abre normalmente em `http://localhost:5173` (verifique a saída do comando para confirmar a porta). Por padrão, o frontend espera o backend rodando em `http://localhost:8000`.

> Backend e frontend são processos independentes — rode os dois em terminais separados, com o backend de pé antes de usar a interface.

## Fluxo de uso

1. O usuário sobe um arquivo CSV pela interface.
2. O frontend envia o arquivo para `/analyze`, que valida os dados e calcula as métricas por grupo.
3. O relatório é montado na tela: resumo dos resultados, avisos de possíveis erros nos dados e o glossário de métricas.
4. O usuário pode exportar esse relatório como PDF ou registrar o resultado (grupo vencedor, ROI e receita líquida) em uma planilha, pelo botão "Inserir na Planilha".
>>>>>>> af7be23deb136dea55a04ce02a522d4d4aec9ec9
