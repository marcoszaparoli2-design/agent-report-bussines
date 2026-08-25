# CLEAN_ROOM_SPEC.md

## Especificação técnica clean-room — "Intelligence Curation Agent"

> **Origem e método.** Este documento foi produzido a partir da leitura integral de um repositório corporativo real (uma implementação de agente de curadoria de anomalias de negócio), com o objetivo explícito de extrair **conceitos, padrões e arquitetura reimplementáveis**, sem copiar código, nomes internos, dados, prompts, queries, credenciais ou qualquer conteúdo proprietário. Toda lógica está descrita em **prosa e pseudocódigo abstrato**. Nenhum trecho de código-fonte real, nome de tabela/dataset/produto real, número de negócio real ou texto de prompt real foi reproduzido. Cada seção termina, quando relevante, com a lista explícita do que foi deliberadamente omitido por ser proprietário.
>
> Este arquivo é autocontido: alguém sem acesso ao repositório original deve conseguir implementar uma versão funcional equivalente em conceito a partir só do que está aqui.

---

## 1. Objetivo do projeto

### 1.1 Problema que resolve

Em organizações onde múltiplas áreas já têm acesso aos próprios dados e dashboards, o problema raramente é *acesso* — é **curadoria**: cada área define métricas à sua maneira, os números não batem entre painéis, e ninguém consolida "o que realmente importa hoje" em uma leitura só. O resultado é fadiga de dashboard: dado abundante, decisão escassa.

Este projeto ataca exatamente essa lacuna: um **agente de curadoria diária** que lê métricas de negócio já existentes, decide algoritmicamente o que é anômalo/relevante hoje, e entrega uma mensagem curta e legível — não mais um painel para explorar, e sim uma leitura pronta.

### 1.2 Fluxo principal de ponta a ponta

```
[Fonte de dados / warehouse]
        │
        ▼
  Coleta       — executa queries versionadas, produz um snapshot do dia
        │
        ▼
  Detecção     — 100% determinístico: baseline estatístico, z-score robusto,
                 gates de qualidade, checagem de movimento sincronizado,
                 atribuição multi-grão, filas de prioridade
        │
        ▼
  Curadoria    — ÚNICA chamada a um LLM por execução: recebe sinais já
                 ranqueados e escreve a narrativa (nunca calcula números)
        │
        ▼
  Entrega      — formata em blocos de mensagem, publica no canal, registra
                 histórico idempotente (nunca duplica no rerun)
```

Execução agendada (ex.: diária, cedo da manhã, antes do expediente).

### 1.3 Entradas e saídas

**Entradas:**
- Uma ou mais métricas de negócio, cada uma definida por (a) uma query versionada que materializa a série histórica por "entidade" (grão) e (b) um contrato declarativo (grãos monitorados, direção de "bom"/"ruim", método de baseline, cortes de severidade, método de cálculo de impacto).
- Um calendário de exceções (feriados, sazonalidades, períodos estruturalmente atípicos).
- Uma camada de conhecimento de negócio em texto (o que é a empresa, o que cada métrica significa, quem lê a mensagem e o que essa audiência prioriza).
- Histórico de execuções anteriores (o que já foi comunicado, o que estava em queda antes).

**Saídas:**
- Uma mensagem diária curta, organizada por unidade de negócio, cada uma com um cabeçalho numérico (sempre presente, mesmo sem anomalia) e uma lista pequena de itens sinalizados.
- Um registro auditável de todo sinal computado (com ou sem severidade) — nunca lido de volta pelo pipeline, existe só para calibração humana posterior.
- Um histórico idempotente do que foi entregue, usado para não repetir mensagens e para fechar o loop narrativo ("sinalizado terça, normalizou hoje").

---

## 2. Arquitetura mapeada

O sistema é organizado em quatro estágios sequenciais, cada um com entrada/saída bem definidas e responsabilidade única. Nenhum estágio faz o trabalho do seguinte.

### 2.1 Fluxo em estágios

```
[Fonte de dados / warehouse]
        │
        ▼
  DATA COLLECTION   — executa queries versionadas, produz um snapshot do dia
        │
        ▼
  DETECTION         — 100% determinístico: baseline estatístico, z-score
                       robusto, gates de qualidade, checagem de movimento
                       sincronizado, atribuição multi-grão, filas de prioridade
        │
        ▼
  CURATION          — ÚNICA chamada a um LLM por execução: recebe sinais já
                       ranqueados e escreve a narrativa (nunca calcula números)
        │
        ▼
  DELIVERY          — formata em blocos de mensagem, publica no canal, registra
                       histórico idempotente (nunca duplica no rerun)
```

### 2.2 Fluxo de dados entre componentes

```
Fonte de dados ──────────────► Data Collection ──► Snapshot diário
                                                          │
Configuração de detecção ─────────────────────────► Detection ──► Conjunto de sinais
Contexto de negócio ───────────────┐                     │         já ranqueados
Histórico de entregas ─────────────┤                     ▼
Esqueleto de prompt ─────────────────►               Curation ──► Saída narrativa
                                                          │         estruturada
                                                          ▼
                                                     Delivery ──► Mensagem publicada
                                                                   + histórico
                                                          │
                                                          ▼
                                              Log de auditoria (write-only,
                                                nunca lido de volta)
```

Princípio central: **cada seta para a direita carrega dados cada vez mais reduzidos e já decididos**. O LLM só entra no estágio de curadoria, e nunca recebe dado bruto — só sinais já filtrados, ranqueados e deduplicados.

---

## 3. Conceitos reutilizáveis (padrões de arquitetura)

Estes são os padrões que valem a pena carregar para qualquer reimplementação, independente do domínio de negócio:

1. **Pipeline determinístico + curador único.** Toda a matemática (coleta, detecção, ranking, dedup) é código puro e testável; o LLM aparece exatamente uma vez, no fim, e só escreve texto a partir de fatos já calculados. Ele nunca recalcula, nunca reordena.
2. **Baseline estatístico robusto por entidade**, não threshold fixo global — "normal" é definido por entidade, dinamicamente, a partir do próprio histórico dela.
3. **Impacto = desvio do baseline, nunca valor bruto** — ranquear por valor absoluto sempre coloca a maior entidade no topo, todo dia, independente de anomalia.
4. **Múltiplas filas de prioridade por tipo de sinal**, em vez de um score único combinado — evita que um evento agudo apague sinais de outro tipo (queda lenta, sinal positivo) no mesmo dia.
5. **Atribuição multi-grão antes do corte top-N** — quando o mesmo evento real dispara sinal em vários níveis de uma hierarquia (loja → região → produto → total), decide qual nível "é a notícia" antes de ranquear, para não preencher o mesmo evento em várias posições da fila.
6. **Checagem de movimento sincronizado** (peer check / hierarchy check) — distingue "esta entidade está anômala sozinha" de "todo o grupo se moveu junto", roteando o segundo caso para contexto, nunca para manchete.
7. **Persistência independente do z-score diário** — dias consecutivos do mesmo lado do baseline captura "sangria lenta" que nunca é aguda o suficiente para cruzar o threshold em um único dia.
8. **Saída estruturada (schema fixo) do LLM**, com vocabulário fechado para estados/categorias — nunca texto livre para campos que viram lógica downstream.
9. **Regra "silêncio é a ausência de mudança, transição é notícia"** — um item só reaparece na mensagem se algo mudou desde a última menção, exceto marcos de persistência (dia 7/15/30) que reaparecem deliberadamente como "ainda em aberto".
10. **Fallback determinístico (rede de segurança)** — se a curadoria por LLM falhar, uma tabela crua e legível é entregue no lugar. O leitor nunca fica sem briefing. Esse caminho é construído e testado **antes** do caminho feliz.
11. **Log de auditoria write-only**, arquitetonicamente separado do histórico "o que já foi comunicado" — o primeiro nunca é lido de volta pelo pipeline (serve só para calibração humana), o segundo é lido de volta e é funcionalmente crítico (idempotência, fila de "recuperados").
12. **Camada de conhecimento compartilhada entre humano e LLM** — o mesmo arquivo de contexto de negócio que documenta o projeto para onboarding humano é injetado no prompt, garantindo que humano e modelo nunca divirjam de entendimento.
13. **Contratos declarativos (YAML) em vez de lógica hardcoded** — grãos monitorados, direção de "bom/ruim", método de baseline e de impacto são configuração, não código; adicionar uma métrica não deveria exigir reescrever o pipeline.
14. **Replay/backtest determinístico** — a mesma pipeline roda contra datas históricas sem efeito de entrega, alimentando só o log de auditoria, permitindo calibrar thresholds com dados reais em vez de achismo.
15. **Golden day** — um dia sintético único, gerado deterministicamente, projetado para disparar deliberadamente um conjunto amplo de cenários (pico agudo, sangria lenta, movimento sincronizado com controle que não se moveu, cold start, recuperação, cenário de limitação conhecida e aceita) e testado por presença/ausência na fila correta, não por valor numérico exato.

### 3.1 Estratégias de processamento

- **Robust statistics** (mediana + MAD) em vez de média/desvio-padrão — resiliente a outliers no próprio histórico usado como referência.
- **Comparação same-weekday** — remove sazonalidade semanal sem precisar de modelo de série temporal complexo.
- **Vintage/cohort matching** — métricas sensíveis a maturidade (ex.: taxa de inadimplência de uma safra) só são comparadas entre safras de maturidade equivalente.
- **Piso relativo na dispersão** — evita explosão de z-score quando a variância histórica é ~0 (entidade pequena/estável).
- **Cold start medido em dias-calendário de existência**, não em tamanho de amostra filtrada — evita classificar uma entidade jovem-mas-real como "sem dados suficientes" para sempre.

### 3.2 Uso de LLM/agentes

- **Um único agente, uma única chamada por execução.** Não é multiagente, não há handoff LLM→LLM (cada handoff degrada precisão numérica sem ganho, já que o agente não conversa com ninguém).
- O papel do LLM é estritamente **redator com fatos pré-computados**, nunca **analista com acesso a dado bruto**.

### 3.3 Camada de contexto

Arquivos de conhecimento de negócio (o que é a empresa, definição de cada métrica, perfil de quem lê, calendário/sazonalidade) servidos ao LLM como texto injetado no prompt — a mesma fonte que documenta o projeto para humanos.

### 3.4 Detecção de anomalias

Ver seção 6 (estatística) abaixo — reproduzida em detalhe porque é o núcleo técnico do sistema.

### 3.5 Priorização de informações

Ver seção 7 (filas de prioridade).

### 3.6 Validação/guardrails contra alucinação

- O LLM nunca recebe dado individual bruto, só sinais agregados.
- Saída em schema fixo, com vocabulário fechado — um valor fora do vocabulário permitido é rejeitado antes de chegar à entrega.
- Todo campo numérico é preenchido por código, nunca "escrito" pelo modelo.
- Quando uma tradução de negócio (ex.: sensibilidade de margem) não existe para uma entidade, o sinal carrega uma flag explícita para o LLM não inventar/fabricar o número traduzido.

### 3.7 Geração de reports

Função pura de renderização (sem lógica de negócio) que transforma a saída estruturada validada em blocos de mensagem — com um segundo teto de itens por seção aplicado no próprio renderer, como segunda linha de defesa além da instrução no prompt.

### 3.8 Integrações externas

- Warehouse/data source (leitura via query versionada).
- Canal de mensageria (webhook, nunca com segredo hardcoded — só nome de variável de ambiente/secret manager).
- Provedor de LLM (uma única chamada, saída estruturada).

### 3.9 Testes e observabilidade

- Fixtures sintéticas determinísticas (roda a pipeline inteira sem credenciais externas).
- Golden day com verificação de presença/ausência em fila correta (não valor exato).
- Replay/backtest contra dados reais sem efeito de entrega.
- Log de auditoria write-only.
- Query de reconciliação contra uma fonte independente já confiável do mesmo número — versionada no repo, com diferenças conhecidas documentadas explicitamente em vez de "corrigidas" à força.

---

## 4. Separação: GENERIC/REIMPLEMENTABLE vs. PROJECT-SPECIFIC/DO NOT COPY

### 4.1 GENERIC / REIMPLEMENTABLE (leve para o novo projeto)

- Arquitetura em 4 estágios (coleta → detecção → curadoria → entrega) com fronteiras de responsabilidade estritas.
- Método estatístico: mediana móvel + MAD, z-score robusto, ajuste same-weekday, piso relativo de dispersão, cold start por idade calendário.
- Gates de qualidade (cold start, imaturidade de cohort, volume mínimo) que suprimem severidade sem apagar a observação.
- Checagem de movimento sincronizado (peer check e hierarchy check) com a mesma função aplicada a duas populações de referência diferentes.
- Atribuição de dominância multi-grão, aplicada bottom-up, antes do corte top-N.
- Impacto normalizado como desvio (não valor bruto), com métodos plugáveis por métrica.
- Filas de prioridade separadas por tipo de sinal e por métrica/unidade de negócio.
- Persistência (dias consecutivos + tendência multi-janela) desacoplada do z-score diário.
- Contrato declarativo de métrica (YAML: grãos, direção, método de baseline, método de impacto, cortes de severidade).
- Prompt de curadoria como esqueleto + injeção de contexto de negócio + sinais + histórico recente.
- Schema de saída estruturada com vocabulário fechado.
- Regra "silêncio vs. transição" com marcos de persistência como exceção.
- Fallback determinístico (rede de segurança) construído antes do caminho com LLM.
- Log de auditoria write-only, separado do histórico funcional de entrega.
- Renderer puro e sem lógica de negócio, com teto de itens como segunda linha de defesa.
- Idempotência de entrega via histórico chaveado por (data, canal).
- Golden day + checker de presença/ausência em fila.
- Fixtures sintéticas + replay/backtest sem efeito de entrega.
- Skills de scaffolding (ex.: assistente para criar um novo contrato de métrica) e de backtest de um dia histórico.
- Padrão "cache local de doc canônico externo, com proveniência e regra de re-verificação".
- Lições registradas em ADRs (o *raciocínio*, não o conteúdo): rejeição de multiagente, rejeição de SQL livre em runtime, rejeição de threshold hardcoded, rejeição de score único blendado, exigência de documentar explicitamente o que uma métrica **não** significa quando a granularidade da tabela-fonte limita sua leitura.

### 4.2 PROJECT-SPECIFIC / DO NOT COPY (não leve para o novo projeto)

- Identidade da empresa original, nome do CEO, nomes de parceiros/emissores reais, estrutura de funding real, posicionamento de marca, números reais de escala (usuários, volume, etc.).
- Números reais de unit economics (razões receita/volume, faixas de perda, coeficientes de sensibilidade de margem, thresholds de break-even).
- Canal real de entrega e fuso horário/agenda reais.
- Tabela real de mapeamento de taxonomia de produto (valores de enum reais, nomes de produto/subproduto reais, regra de precedência específica, valores sentinela substituídos).
- Nomes reais de categoria de segmento/cohort e seus cortes numéricos reais (dias de recência, faixas de score).
- Coeficientes reais de sensibilidade por produto.
- Nome real do projeto de cloud, dataset, e todos os nomes reais de tabela/coluna do warehouse.
- Números reais de reconciliação e datas de medição.
- Código-fonte SQL/Python real (nenhuma linha foi reproduzida neste documento).
- Texto literal do prompt de curadoria e dos arquivos de conhecimento de negócio.
- Exemplos reais de mensagem de saída (nomes de entidade fictícios usados como exemplo no repo original, valores em R$ de exemplo).
- Qualquer caminho de arquivo contendo identificador real de projeto/dataset de nuvem.
- Conteúdo literal de qualquer ADR além do padrão de raciocínio já extraído acima.

---

## 5. Proposta de arquitetura nova e independente

```
intelligence-curation-agent/
├── src/
│   ├── data/
│   │   ├── sources/                # adapters de leitura (warehouse real, fixtures locais)
│   │   └── metric_schema.py        # loader tipado dos contratos de métrica (YAML → objeto)
│   ├── metrics/
│   │   └── <metric_name>/
│   │       ├── query.sql           # query versionada que materializa a série por entidade
│   │       └── contract.yaml       # grãos, direção, baseline, impacto, severidade
│   ├── anomaly_detection/
│   │   ├── deviation_model.py      # mediana+MAD, ajuste same-weekday, piso de dispersão
│   │   ├── gates.py                # cold start, imaturidade de cohort, volume mínimo
│   │   ├── synchronized.py         # peer check + hierarchy check
│   │   ├── attribution.py          # dominância multi-grão, bottom-up
│   │   └── streak_tracker.py       # dias consecutivos + tendência multi-janela
│   ├── prioritization/
│   │   ├── impact_scoring.py       # métodos de impacto plugáveis (valor, taxa ponderada, etc.)
│   │   └── priority_ranking.py     # montagem e corte das filas por tipo/métrica/unidade
│   ├── context/
│   │   └── knowledge_loader.py     # carrega docs de conhecimento p/ injeção no prompt
│   ├── curation/
│   │   ├── curator.py              # orquestra a chamada única ao LLM
│   │   ├── schema.py               # schema de saída estruturada + validação/guardrails
│   │   └── fallback.py             # formatador determinístico de segurança
│   ├── reporting/
│   │   └── render.py               # função pura: saída estruturada → blocos de mensagem
│   ├── observability/
│   │   └── audit_log.py            # log write-only de todo sinal computado, p/ calibração
│   └── integrations/
│       ├── llm_provider.py         # cliente do provedor de LLM
│       └── delivery_channel.py     # publicação + histórico idempotente
├── prompts/
│   └── curator_skeleton.md         # esqueleto de prompt (sem conteúdo de negócio real)
├── config/
│   ├── seasonality_calendar.yaml
│   ├── delivery_channels.yaml
│   └── detection_sensitivity.yaml  # sensibilidade de detecção — nunca baseline de negócio
├── knowledge/
│   ├── what-is-this-business.md
│   ├── metrics-glossary.md
│   ├── audience-profile.md
│   └── seasonal_effects.md
├── tests/
│   ├── fixtures/                   # dados sintéticos determinísticos
│   ├── golden/                     # cenário "golden day" anotado
│   └── check_golden.py
├── docs/
│   ├── architecture-notes/          # registros de decisão arquitetural (padrão ADR)
│   └── roadmap/
└── README.md
```

Ajustes deliberados em relação ao esqueleto sugerido originalmente pelo usuário: `metrics/` virou uma pasta por métrica (query + contrato juntos, mais fácil de escalar via scaffolding); `curation/` foi separado de `reporting/` porque são responsabilidades diferentes (decidir o texto vs. formatar o texto); `context/` ficou enxuto (só o loader — o conteúdo de negócio mora em `knowledge/`, fora de `src/`, porque não é código).

---

## 6. Como reconstruir — módulo a módulo

### 6.1 `data/metric_schema.py`

- **Finalidade:** carregar `metrics/*/contract.yaml` em um objeto tipado. Nunca decide um valor — só schema.
- **Input:** caminho do arquivo YAML.
- **Output:** objeto com lista de grãos (nome, papel `entity`/`denominator`, mapeamento de campo de escopo, grupo de pares opcional, grão-pai opcional, filtro de linha opcional), direção de "bom/ruim", método de baseline, método de impacto, cortes de severidade.
- **Interface:** `load_contract(path) -> MetricContract`.
- **Lógica:** parsing + validação de schema (campos obrigatórios, enums válidos). Sem cálculo.
- **Tecnologias genéricas:** `pydantic`/`dataclasses` + `pyyaml` (Python); qualquer parser YAML tipado em outra linguagem.
- **Implementar do zero:** o schema do contrato em si (quais campos existem) é uma decisão de design nova — comece pequeno (grão, direção, baseline, severidade) e adicione conforme necessário.

### 6.2 `data/sources/`

- **Finalidade:** abstrair "de onde vem a série por entidade" — warehouse real ou fixture local, mesma interface.
- **Input:** contrato de métrica + data-alvo.
- **Output:** série tabular (entidade, data, valor) — mesma forma independente da fonte.
- **Interface:** `fetch_series(contract, as_of_date) -> DataFrame`.
- **Lógica:** executar a query associada (real) ou ler CSV (fixture); nenhuma lógica de negócio aqui.
- **Tecnologias genéricas:** qualquer client de data warehouse (BigQuery, Snowflake, Postgres...) + pandas/polars para fixtures.
- **Implementar do zero:** o adapter real depende 100% da infraestrutura de dados do novo projeto — não há nada reaproveitável do original aqui além da interface.

### 6.3 `anomaly_detection/deviation_model.py`

- **Finalidade:** calcular baseline robusto e z-score por entidade.
- **Input:** série histórica de uma entidade + data-alvo + janela (ex.: 8 semanas) + lista de datas de calendário a excluir do histórico.
- **Output:** `(baseline_median, scaled_mad_with_floor, z_score, calendar_days_of_history)`.
- **Interface:** `compute_baseline(series, as_of_date, window_weeks, calendar_exclusions) -> BaselineResult`.
- **Lógica (pseudocódigo):**
  ```
  history = series filtrado para mesmo dia-da-semana de as_of_date,
            dentro da janela, excluindo datas de calendar_exclusions
  baseline = mediana(history)
  mad = mediana(|history - baseline|)
  scaled_mad = max(1.4826 * mad, floor_fraction * baseline, epsilon)
  z = (valor_hoje - baseline) / scaled_mad
  cold_start_days = hoje - data_mais_antiga_disponível_da_entidade  # não filtrada
  ```
- **Tecnologias genéricas:** numpy/pandas, ou qualquer linguagem com mediana/MAD nativos.
- **Implementar do zero:** os valores de `window_weeks`, `floor_fraction` e `epsilon` são parâmetros de calibração — comece com um valor razoável (ex.: 8 semanas, floor de 5-10% da mediana) e ajuste com backtest real, não adivinhe direto do domínio.

### 6.4 `anomaly_detection/gates.py`

- **Finalidade:** decidir se um z-score "tem permissão" de virar severidade, sem apagar a observação.
- **Input:** `BaselineResult` + metadados da entidade (volume do dia, idade de cohort se aplicável).
- **Output:** severidade final (`none`/`watch`/`high`) + lista de flags de supressão aplicadas (ex.: `cold_start`, `immature_vintage`, `low_volume`).
- **Interface:** `apply_gates(baseline_result, entity_meta, thresholds) -> GatedSignal`.
- **Lógica:** cada gate é uma função independente `(signal) -> bool` que, se disparada, zera a severidade mas mantém o z-score bruto e adiciona uma flag explicando por quê.
- **Tecnologias genéricas:** nenhuma específica — lógica condicional simples.
- **Implementar do zero:** a lista de gates é específica do domínio do novo projeto — pense em quais falsos positivos estruturais existem nos seus dados (entidade nova, período de transição, amostra pequena) e escreva um gate por classe de falso positivo, não um gate genérico "ignora se estranho".

### 6.5 `anomaly_detection/synchronized.py`

- **Finalidade:** distinguir "esta entidade se moveu sozinha" de "o grupo/hierarquia toda se moveu junto".
- **Input:** z-score da entidade + z-score de referência (mediana de pares, ou z do grão-pai) + threshold.
- **Output:** booleano `is_synchronized_move`.
- **Interface:** `is_synchronized_move(entity_z, reference_z, threshold) -> bool`.
- **Lógica (pseudocódigo):**
  ```
  return |entity_z| >= threshold AND |reference_z| >= threshold
         AND sign(entity_z) == sign(reference_z)
  ```
- **Reuso:** a mesma função serve para peer-check (referência = pares) e hierarchy-check (referência = grão-pai) — só muda quem é passado como `reference_z`.
- **Implementar do zero:** a definição de "grupo de pares" e de "grão-pai" é modelagem de domínio nova.

### 6.6 `anomaly_detection/attribution.py`

- **Finalidade:** quando o mesmo evento dispara sinal em vários níveis de uma hierarquia, decidir qual nível vira manchete.
- **Input:** lista de sinais com severidade, organizados por hierarquia (grão-pai → grãos-filhos).
- **Output:** sinais marcados como `headline` (com % de atribuição, se aplicável) ou `suppressed`.
- **Interface:** `attribute_dominance(signals_by_hierarchy, dominance_threshold) -> AttributedSignals`.
- **Lógica (pseudocódigo):**
  ```
  para cada sinal de nível pai com severidade:
      filhos = sinais-filhos deste pai, também com severidade
      se filhos vazio: pai permanece headline
      senão:
          melhor_filho = filho com maior |desvio|
          share = |desvio(melhor_filho)| / |desvio(pai)|
          se share >= dominance_threshold:
              melhor_filho vira headline (com nota de atribuição)
              pai é suprimido
              TODOS os outros filhos também são suprimidos  # não só o vencedor
          senão:
              pai permanece headline (diffuse)
              TODOS os filhos são suprimidos
  aplicar bottom-up para não ressurgir em outro nível
  ```
- **Cuidado comum de implementação:** uma versão ingênua desse mecanismo tende a suprimir só o filho vencedor, deixando os demais vazarem como manchetes duplicadas do mesmo evento — a versão correta suprime todos os filhos do nó atribuído, dominante ou não.
- **Implementar do zero:** roda **antes** do corte top-N das filas (seção 6.8), sempre.

### 6.7 `anomaly_detection/streak_tracker.py`

- **Finalidade:** capturar tendências que nunca são agudas o suficiente para cruzar o threshold de severidade em um único dia.
- **Input:** série histórica da entidade + baseline diário de cada dia do histórico.
- **Output:** `consecutive_days_off` (contagem) + `trend_Nd` (worsening/stable/improving para uma ou mais janelas, ex. 7/15/30 dias).
- **Interface:** `compute_persistence(series, baselines, windows) -> PersistenceResult`.
- **Lógica (pseudocódigo):**
  ```
  consecutive_days_off = 0
  para dia = hoje, ontem, anteontem, ... (andando pra trás):
      se valor(dia) está do lado "ruim" do baseline(dia): consecutive_days_off += 1
      senão: parar
  # qualquer magnitude conta, sem gate de severidade

  para cada N em windows:
      media_recente = média(últimos N dias)
      media_anterior = média(N dias antes desses)
      trend_Nd = comparar médias na direção "ruim" da métrica
  ```
- **Implementar do zero:** os marcos de re-exibição (ex. dia 7/15/30) são parâmetro de config, ajustável por domínio.

### 6.8 `prioritization/impact_scoring.py`

- **Finalidade:** normalizar o "tamanho" de uma anomalia em uma unidade comum, para permitir ranking entre métricas de tipos diferentes.
- **Input:** sinal (com z-score, valor, baseline) + método declarado no contrato + (opcional) tabela de coeficientes de sensibilidade de negócio.
- **Output:** `impact_share` (fração do total do dia da métrica de volume primária).
- **Interface:** `compute_impact(signal, method, sensitivity_table=None) -> float`.
- **Lógica (pseudocódigo):**
  ```
  se method == "direct_delta":
      impact = valor_hoje - baseline
  se method == "exposure_weighted_rate":
      impact = (taxa_hoje - baseline_taxa) * peso_exposição(entidade)
  se method == "business_sensitivity_weighted":
      coef = sensitivity_table.get(chave(entidade), default_com_flag=True)
      impact = exposure_weighted_rate(...) * coef
  impact_share = impact / total_do_dia_da_métrica_de_volume_primária
  ```
- **Implementar do zero:** a tabela de sensibilidade é 100% de domínio novo — e a flag de "usei default, não valor real" é obrigatória para o guardrail de alucinação do curador (seção 6.10).

### 6.9 `prioritization/priority_ranking.py`

- **Finalidade:** montar e cortar as filas finais de sinais que alimentam a curadoria.
- **Input:** todos os sinais pós-gates, pós-atribuição, com impacto calculado + histórico de execuções anteriores.
- **Output:** filas nomeadas: `negative`, `positive`, `slow_bleed`, `context` (sincronizados), `recovered`.
- **Interface:** `build_queues(signals, history, config) -> Queues`.
- **Lógica (pseudocódigo):**
  ```
  negative/positive = sinais com severidade, não-sincronizados,
                       ordenados por |impact_share| desc, cortados em top-N
  slow_bleed = entidades com consecutive_days_off >= mínimo,
               EXCLUINDO quem já está em negative/positive hoje,
               ordenadas por (dias, impacto acumulado)
  context = todos os sinais sincronizados (peer ou hierarchy)
  recovered = entidades presentes no histórico de ontem em fila aguda,
              com dado válido hoje, mas sem qualificar em nenhuma fila aguda hoje
  ```
- **Implementar do zero:** os N de corte por fila devem ser configuráveis por unidade de negócio × métrica × tipo de fila, não um único N global.

### 6.10 `curation/curator.py` + `curation/schema.py`

- **Finalidade:** uma única chamada a um LLM que transforma filas já ranqueadas em narrativa.
- **Input:** filas + contexto de conhecimento (texto) + histórico recente de mensagens (para aplicar a regra silêncio/transição).
- **Output:** objeto estruturado validado contra um schema fixo.
- **Interface:** `curate(queues, knowledge, message_history) -> CuratedOutput`.
- **Schema de saída (forma, não conteúdo):**
  ```
  {
    "all_clear": bool,
    "overall_summary": { números de código, texto do modelo },
    "business_units": [
      {
        "unit": str,
        "headline_numbers": { preenchido por código },
        "items": [
          { "type": enum_fechado, "text": str_do_modelo, "grain": str }
          # máximo N itens, N vindo de config
        ]
      }
    ],
    "transversal_items": [...],   # sinais sem dono único de unidade de negócio
    "context_notes": str          # só para sinais de background/sincronizados
  }
  ```
- **Regras de prompt (obrigatórias, não sugestões):** nunca inventar/recalcular número; nunca reordenar; mesclar sinais correlacionados de filas diferentes em um item narrativo só; sinal sincronizado ganha no máximo uma menção agregada, nunca manchete; se não houver tradução de sensibilidade de negócio para uma entidade, reportar o desvio bruto e não fabricar o valor traduzido.
- **Guardrails:** validação de schema rejeita saída com campo fora do vocabulário fechado ou que exceda o teto de itens por seção, antes de chegar à entrega.
- **Tecnologias genéricas:** qualquer provedor de LLM com suporte a saída estruturada/tool-calling (ex.: JSON Schema forçado); framework de validação (`pydantic`, `zod`, etc.).
- **Implementar do zero:** o texto do prompt de negócio (contexto real da empresa) — nunca copie o prompt original, escreva o seu a partir da lista de regras acima.

### 6.11 `curation/fallback.py`

- **Finalidade:** garantir que o leitor nunca fique sem briefing.
- **Input:** as mesmas filas que iriam para o curador.
- **Output:** uma tabela de texto simples, uma linha por sinal, com entidade/métrica/desvio/fila.
- **Interface:** `render_fallback(queues) -> str`.
- **Prioridade de implementação:** construa e teste este módulo **antes** do `curator.py` — é o que garante que o sistema nunca falha silenciosamente.

### 6.12 `reporting/render.py`

- **Finalidade:** função pura, sem lógica de negócio, que transforma a saída estruturada validada em blocos de mensagem para o canal de entrega.
- **Input:** `CuratedOutput` (do curador ou do fallback) + config de formatação.
- **Output:** payload de blocos prontos para a API do canal (ex.: blocos de Slack, cartão de Teams, mensagem de WhatsApp).
- **Interface:** `render(curated_output, format_config) -> MessagePayload`.
- **Lógica:** só formatação — reforça teto de itens por seção como segunda linha de defesa; converte status (melhorou/piorou/estável), computado por código, em marcador visual (emoji/ícone), nunca texto colorido dependente do modelo; se um link de detalhe não existir, cai graciosamente para texto simples.
- **Implementar do zero:** o mapeamento status→marcador e o layout de blocos dependem do canal de destino escolhido.

### 6.13 `integrations/delivery_channel.py`

- **Finalidade:** publicar a mensagem e manter idempotência.
- **Input:** payload de blocos + data + identificador de canal.
- **Output:** confirmação de envio + registro no histórico.
- **Interface:** `deliver(payload, date, channel) -> DeliveryResult`.
- **Lógica:** antes de postar, checar se já existe registro para (data, canal) no histórico; se sim, no-op (idempotência); segredo do canal vem de variável de ambiente/secret manager, nunca hardcoded.
- **Tecnologias genéricas:** webhook HTTP simples (Slack/Teams/Discord/WhatsApp Business API), tabela de histórico em qualquer banco (mesmo SQLite serve para volume baixo).

### 6.14 `integrations/llm_provider.py`

- **Finalidade:** abstrair o provedor de LLM por trás de uma interface simples de "gerar saída estruturada a partir de um prompt".
- **Interface:** `generate_structured(prompt, schema) -> dict`.
- **Implementar do zero:** escolha de provedor é decisão do novo projeto; a interface deve ser trocável sem tocar em `curator.py`.

### 6.15 Config e conhecimento (`config/*.yaml`, `knowledge/*.md`)

- **Finalidade:** separar "o que é normal para o negócio" (nunca hardcoded em código) de "quão sensível o detector deve ser" (config) de "o que humanos e o LLM precisam saber sobre o negócio" (knowledge, texto).
- **`config/seasonality_calendar.yaml`:** feriados, datas de eventos de varejo/sazonalidade, períodos estruturalmente atípicos que não devem receber veredito de status.
- **`config/detection_sensitivity.yaml`:** tetos de fila por unidade×métrica×tipo, threshold de dominância, mínimo de histórico para veredito de status, marcos de persistência, gate de volume mínimo. **Nunca** baseline de negócio.
- **`knowledge/*.md`:** o que é o negócio (para calibrar tom), definição de cada métrica e por que foi escolhida, quem lê a mensagem e o que essa audiência prioriza, glossário/taxonomia, referência de sazonalidade. Escreva com marcadores `TODO` explícitos para o que ainda não foi decidido — isso documenta a dependência mesmo antes do conteúdo existir.

### 6.16 Testes (`tests/`)

- **Fixtures sintéticas determinísticas:** gerador com seed fixo que produz séries plausíveis por entidade, permitindo rodar o pipeline inteiro sem credenciais externas.
- **Golden day:** um dia sintético único projetado para disparar deliberadamente: pico agudo positivo e negativo, sangria lenta, movimento sincronizado com um controle que não se moveu (prova que o peer-check distingue os dois casos), cold start, entidade recuperada, cohort imaturo, movimento hierárquico com efeito em cascata nos filhos, cenário de limitação conhecida e aceita (documentado, não corrigido), filtro estrutural (um sub-grão que só deveria existir para um ramo da taxonomia).
- **Checker:** reprocessa o golden day e valida **presença/ausência na fila correta + flags corretas** — nunca valores numéricos exatos (dependem do RNG da fixture).
- **Replay/backtest:** roda contra dados reais em modo histórico, sem entrega, só alimentando o log de auditoria — usado para medir taxa real de falso positivo antes de mudar um threshold.

---

## 7. Implementation Order

Ordem recomendada, do MVP até uma versão mais completa — cada etapa deve ser demonstrável isoladamente antes de avançar:

1. **Contrato de métrica + fixtures sintéticas.** Defina o schema YAML de contrato e escreva um gerador de dados sintéticos determinístico para uma métrica só. Sem isso, nada mais pode ser testado de forma reproduzível.
2. **`anomaly_detection/deviation_model.py` isolado**, testado só contra as fixtures. Prove que mediana+MAD+z-score funciona antes de acoplar qualquer outra coisa.
3. **Gates de qualidade** (`gates.py`) — cold start, volume mínimo. Adicione só os gates que sua fixture consegue exercitar.
4. **`prioritization/impact_scoring.py` + `priority_ranking.py`** com um método de impacto só (`direct_delta`). Filas `negative`/`positive` funcionando ponta a ponta contra fixtures.
5. **`curation/fallback.py`** — tabela crua legível a partir das filas. Este é o primeiro "produto entregável" do sistema, mesmo sem LLM.
6. **`reporting/render.py` + `integrations/delivery_channel.py`** contra um canal real (ex.: webhook de Slack de teste) — valide idempotência aqui.
7. **Golden day + checker** — formalize os cenários de teste antes de adicionar complexidade estatística nova, para ter uma rede de segurança de regressão.
8. **Peer check / hierarchy check** (`synchronized.py`) — exige um segundo grão relacionado na fixture; adicione um cenário novo ao golden day para cada checagem.
9. **Persistência** (`streak_tracker.py`) + fila `slow_bleed`.
10. **Atribuição multi-grão** (`attribution.py`) — só faz sentido depois que existe hierarquia de grãos de verdade nas fixtures; adicione o cenário dominante e o diffuse ao golden day.
11. **Camada de conhecimento** (`knowledge/*.md`) + esqueleto de prompt — escreva o conteúdo real do seu domínio aqui, nunca antes.
12. **`curation/curator.py` com LLM real** — só depois que o fallback e o schema de saída já estão estáveis e testados; comece validando contra o golden day (sem entrega real).
13. **Métodos de impacto adicionais** (`exposure_weighted_rate`, `business_sensitivity_weighted`) — só quando houver uma segunda métrica de tipo diferente (taxa) para justificar.
14. **Log de auditoria write-only** (`observability/audit_log.py`) + modo `--replay`/backtest contra dados reais.
15. **Fila `recovered`** — exige histórico funcional de execuções anteriores já estável.
16. **Skills de scaffolding** (assistente para novo contrato de métrica, comando de replay de um dia histórico) — automação de conveniência, só depois que o processo manual já é bem entendido.
17. **Segunda fonte de dados real (warehouse de produção)** — troque o adapter de fixture pelo adapter real por último, mantendo a mesma interface definida no passo 1.

---

*Fim do documento. Nenhum código-fonte, nome de tabela, nome de produto, número de negócio, texto de prompt ou credencial do repositório original foi reproduzido acima — apenas arquitetura, padrões estatísticos genéricos e pseudocódigo descritivo.*
