# Entregável 4 — versão refatorada

Estrutura:

- `E4_RenatoBuenoDomingosDeOliveira_refatorado.ipynb`: protocolo experimental, execuções, tabelas e discussão A–K.
- `src/schemas.py`: modelos estruturados e estado.
- `src/recuperacao.py`: leitura, seleção e compactação dos documentos semânticos.
- `src/workflow.py`: workflow LangGraph, roteamento, suficiência, geração e métricas.
- `src/avaliacao.py`: benchmark, trace e fidelidade textual.
- `src/falhas_silenciosas.py`: verificações da Seção C.
- `src/experimento.py`: repetição das rodadas e análise de estabilidade.

## Colab

Descompacte o pacote preservando a pasta `src/` no mesmo diretório de trabalho do notebook.
Depois execute `Restart session -> Run all`.

Os documentos semânticos continuam sendo localizados pelo mecanismo já existente no notebook
(`data/documentos_semanticos` local ou fallback do Google Drive).
