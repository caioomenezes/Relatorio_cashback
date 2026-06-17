# Analisador A/B de Cashback

Este repositório é referente a uma aplicação web desenvolvida para analisar experimentos A/B de campanhas de cashback. O usuário faz upload de um CSV com os dados do experimento, o sistema calcula as métricas de cada grupo, aponta qual variante teve melhor desempenho, gera um resumo em linguagem natural e permite exportar tudo em um PDF ou registrar o resultado em uma planilha.

Este README cobre a versão web do projeto: backend em **FastAPI** (`backend/`) e frontend em **React** (raiz do repositório, rodado com `npm run dev`).

## Por que este projeto existe

Assim como foi repassado no teste, times de growth e marketing rodam testes A/B de cashback com frequência, mas normalmente dependem de alguém com conhecimento técnico (ou de planilhas manuais) para transformar um CSV de exportação em uma decisão clara: qual variante venceu e por quê. Este projeto automatiza essa ponte ( da planilha bruta até a recomendação final ) e foi pensado desde o início para que **pessoas sem conhecimento técnico também consigam gerar e interpretar o relatório**, sem depender de outra pessoa para traduzir os números.

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

Essa é uma importante decisão tomada para esse projeto. Entre as métricas calculadas, o **ROI** foi escolhido como critério principal para apontar o grupo vencedor, em vez de métricas absolutas como GMV ou receita líquida em reais. A razão é que ROI mede **eficiência do investimento**: quanto retorno em receita líquida cada real gasto em cashback gerou, e não o tamanho do grupo.

Isso é importante porque GMV e receita líquida absoluta tendem a favorecer naturalmente o grupo com mais usuários ou mais tráfego, mesmo que esse grupo seja menos eficiente por usuário. O ROI normaliza essa diferença e permite comparar grupos de tamanhos distintos pela mesma régua, respondendo à pergunta que realmente importa para quem vai decidir o orçamento: "se eu escalar este grupo, cada real adicional de cashback vai continuar valendo a pena?"

## Identificação de possíveis erros nos dados

Antes de qualquer decisão ser tomada com base nos números, o sistema roda uma verificação automática de anomalias nos dados recebidos. Essa verificação acontece em duas camadas: uma no backend, durante a validação do CSV, e outra no frontend, após as métricas serem calculadas.

### Camada 1 — Validação no backend

Quando o CSV é enviado ao endpoint `/analyze`, o pipeline valida a estrutura do arquivo antes de calcular qualquer métrica. Se algum problema for detectado nessa etapa — como a ausência da coluna de cashback — o backend devolve um aviso junto com o resultado. Esses avisos são repassados diretamente para o card de "Avisos da Análise" no relatório.

### Camada 2 — Detecção de anomalias no frontend

É importante destacar que com o objetivo de tentar mitigar o impacto de dados ruidosos e ruins, a aplicação, após receber as métricas calculadas, o componente `ReportSection` roda a função `detectAnomalies`, que verifica os seguintes casos por grupo:

**Cashback idêntico à comissão** - quando o cashback de um grupo é numericamente igual à comissão (diferença menor que R$ 0,01), o sistema emite um alerta de nível crítico. Esse padrão costuma indicar que a coluna de cashback foi preenchida com os valores da coluna de comissão por engano, o que zeraria a receita líquida e o ROI daquele grupo e tornaria qualquer comparação inválida.

**Receita líquida negativa** - quando o cashback pago supera a comissão gerada, a receita líquida fica negativa. O sistema sinaliza isso como crítico, pois significa que o grupo custou mais do que gerou no período analisado.

**ROI zero com comissão positiva** - quando um grupo tem comissão maior que zero mas ROI igual a zero (e o cashback não é idêntico à comissão), o sistema emite um aviso de investigação. Esse estado pode indicar um erro no cálculo do denominador no backend ou um problema na origem dos dados de cashback daquele grupo.

**Conversão zerada com usuários cadastrados** - quando um grupo tem usuários registrados mas nenhum comprador, a taxa de conversão é zero. O sistema sinaliza isso como aviso, pois pode indicar um erro de segmentação, um problema no join entre as tabelas de usuários e pedidos, ou simplesmente um grupo que não foi exposto à campanha.

**Lifts extremos entre grupos** - quando a variação percentual de qualquer métrica entre um grupo e o controle ultrapassa 200%, o sistema emite um aviso. Lifts desse tamanho raramente refletem um resultado real, na maioria dos casos apontam para amostras de tamanhos muito desproporcionais ou para um erro nos dados de um dos grupos.

### Como os avisos aparecem

Todos os avisos são exibidos em um card dedicado ("Avisos da Análise") dentro do relatório, separado dos resultados principais. Os avisos de nível crítico (cashback idêntico à comissão e receita negativa) aparecem em vermelho; os de nível investigativo aparecem em amarelo. Nenhum aviso bloqueia a análise, eles existem para que quem for tomar a decisão saiba o que investigar na origem dos dados antes de agir sobre os números.

## Glossário de métricas no relatório

Cada métrica que aparece no relatório também é explicada dentro do próprio relatório, em um card de "Glossário de Métricas": para cada uma, o sistema mostra o que ela é (a fórmula, em linguagem simples) e para que ela serve (como interpretá-la na prática). Essa decisão existe justamente para que alguém sem bagagem técnica em growth ou estatística consiga abrir o relatório e entender, sozinho, o que está sendo medido e por que o sistema recomendou um grupo em vez de outro, sem precisar perguntar para outra pessoa o que "ROI" ou "margem" significam ali.

## Exportação em PDF

O botão "Exportar PDF" do relatório gera um PDF a partir da própria tela do relatório (incluindo o resumo dos resultados, os avisos de anomalias e o glossário de métricas). Isso é parte da mesma decisão de projeto: como o PDF é uma cópia fiel do que aparece na tela — explicações incluídas — ele pode ser repassado para qualquer pessoa (um gestor, um parceiro, alguém de outra área) sem que essa pessoa precise ter acesso ao sistema ou conhecimento técnico prévio para entender o conteúdo. O relatório se explica por si só.

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

Em outro terminal, na raiz do projeto:

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
   
## Arquivos complementares

A seguir, estão os links referentes a planilha de resultados alimentada pela aplicação e um vídeo de demonstração do funcionamento da aplicação:

https://docs.google.com/spreadsheets/d/1Fjjbyox2p89cU-8F0T2IA3CqakdmRbQ5aq8hGpKKL-o/edit?usp=sharing

https://drive.google.com/file/d/1f25lRUgAIcpNRCOALqJkaMsbxmGFfvJG/view?usp=sharing



 
