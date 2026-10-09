# LLM-Based Epidemiological Question Answering: From Baseline to Reliability

## Overview

This repository organizes the development and experimental evaluation of an LLM-based question-answering system for epidemiological information.

The project is divided into four incremental deliverables (E1–E4), exploring the transition from basic language-model answering to controlled retrieval, specialized agents, and systematic reliability evaluation.


### 📄 Slides

[Visualizar apresentação em PDF](Sistemas_Multiagentes_Unicamp.pdf)

### 🎥 Vídeo da apresentação

[![Apresentação do projeto](https://img.youtube.com/vi/UZIMWpEVdxc/hqdefault.jpg)](https://youtu.be/UZIMWpEVdxc)

Clique na imagem para assistir ao vídeo.


## System Evolution

| Deliverable | Focus | Research Question |
|---|---|---|
| E1 — Baseline | Answer generation using a pre-selected document and an LLM | Can the LLM answer the question? |
| E2 — Controlled RAG | Question classification, evidence retrieval, sufficiency assessment, and abstention | How can we control the answer? |
| E3 — Multi-Agent Architecture | Supervisor, specialized agents, and semantic processing | How can we specialize the system? |
| E4 — Reliability Evaluation | Robustness, faithfulness, traceability, and silent failures | Can we trust the system? |

## Repository Structure

```text
llm-epidemiological-qa/
├── E1_baseline/
├── E2_controlled_rag/
├── E3_multiagent/
├── E4_reliability/
├── data/
├── docs/
├── README.md
├── requirements.txt
└── .gitignore
```

## Deliverables

### E1 — Baseline: Answer Generation
Investigates the ability of an LLM to answer epidemiological questions using a pre-selected document supplied as context.

### E2 — Controlled RAG
Explores question classification, evidence retrieval, evidence sufficiency assessment, and abstention when evidence is insufficient.

### E3 — Specialized Multi-Agent Architecture
Explores a supervisor, specialized evidence and analysis agents, and semantic processing.

### E4 — Reliability Evaluation
Investigates robustness, faithfulness to evidence, traceability, and silent failures.

## Installation and Execution

Execution instructions, required Python versions, dependencies, and environment variables will be documented after consolidating the implementation files. Each deliverable contains its own README for specific instructions.

## Research Context

This project investigates large language models, retrieval-augmented generation, and specialized agents to support evidence-grounded question answering in epidemiological surveillance.

## Reproducibility

Experimental configurations, evaluation datasets, metrics, and results will be documented for each deliverable. Sensitive data, credentials, API keys, and private datasets must not be committed.

## License

To be defined.

## Citation

Citation information will be added when the repository and associated research outputs are finalized.
