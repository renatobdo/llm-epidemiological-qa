from pathlib import Path
from typing import Dict, List
import time

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END

from src.schemas import (
    AgentState,
    ClassificacaoDimensoes,
    RespostaEstruturada,
    VerificacaoSuficiencia,
)
from src.recuperacao import recuperar_documentos_semanticos_compacto


# Dependências externas injetadas pelo notebook.
llm = None
BASE_DOCS = None
classificador_dimensoes_llm = None
verificador_suficiencia_llm = None
structured_llm = None
workflow = None


def configurar_workflow(
    llm_instance,
    base_docs: Path,
):
    """
    Injeta o modelo e o diretório de documentos e compila
    o workflow sem acoplar o módulo ao Colab ou Google Drive.
    """
    global llm
    global BASE_DOCS
    global classificador_dimensoes_llm
    global verificador_suficiencia_llm
    global structured_llm
    global workflow

    llm = llm_instance
    BASE_DOCS = Path(base_docs)

    classificador_dimensoes_llm = (
        llm.with_structured_output(
            ClassificacaoDimensoes
        )
    )

    verificador_suficiencia_llm = (
        llm.with_structured_output(
            VerificacaoSuficiencia
        )
    )

    structured_llm = (
        llm.with_structured_output(
            RespostaEstruturada
        )
    )

    workflow = construir_workflow()

    return workflow


def _verificar_configuracao():
    if (
        llm is None
        or BASE_DOCS is None
        or workflow is None
    ):
        raise RuntimeError(
            "workflow.py ainda não foi configurado. "
            "Execute configurar_workflow(llm, BASE_DOCS)."
        )


# ============================================================
# A.7 — ESTADO DO SISTEMA HERDADO
# ============================================================

DIMENSOES_SUPORTADAS = [
    "geral",
    "temporal",
    "geografica",
    "clinica",
    "virologica",
    "desfechos",
]

MAX_PASSOS = 8

def criar_estado_inicial(
    pergunta: str
) -> AgentState:

    return {
        "pergunta": pergunta,
        "dimensoes": [],
        "plano_recuperacao": [],
        "evidencias": [],
        "documentos_consultados": [],
        "evidencia_suficiente": False,
        "justificativa_suficiencia": None,
        "dimensoes_faltantes": [],
        "resposta_final": None,
        "historico_conversa": [],
        "contexto_anterior": None,
        "pergunta_anterior": None,
        "chamadas_llm": 0,
        "chamadas_ferramentas": 0,
        "passos": 0,
        "erro": None,
    }
SYSTEM_CLASSIFICADOR_DIMENSOES = """
Você é responsável por classificar perguntas
epidemiológicas sobre dengue.

Identifique somente as dimensões estritamente
necessárias para responder à pergunta.

Use exclusivamente as seguintes categorias:

- geral
- temporal
- geografica
- clinica
- virologica
- desfechos

Definições:

geral:
totais nacionais, panorama geral, quantidade total de registros,
notificações ou casos no Brasil.

temporal:
semanas epidemiológicas, períodos, picos,
médias semanais, tendências ou mudança do
número de notificações ao longo do tempo.

Não classifique como temporal apenas porque
a pergunta menciona um ano, como 2026.

Não classifique como temporal expressões como
"evolução do caso", "evolução predominante",
"cura" ou "óbito".

geografica:
UFs, estados, municípios, localização,
distribuição espacial ou incidência por local.

Não classifique como geografica apenas porque
a pergunta menciona "Brasil" como escopo nacional.

clinica:
sinais clínicos, sintomas ou doenças
preexistentes.

virologica:
sorotipos da dengue e informações
relacionadas ao perfil virológico.

desfechos:
hospitalização, evolução do caso, cura,
óbito, categorias de óbito e demais
resultados finais do caso epidemiológico.

A palavra "evolução", quando se referir à
evolução do caso ou do paciente, deve ser
classificada como desfechos e NÃO como temporal.

Regras de decisão:

1. Retorne somente as dimensões realmente
   necessárias para responder à pergunta.

2. Prefira uma única dimensão quando ela
   for suficiente.

3. Use múltiplas dimensões somente quando
   a pergunta solicitar explicitamente
   informações de mais de um aspecto.

4. Para perguntas sobre quantidade total,
   total nacional, número total de registros,
   notificações ou casos no Brasil,
   classifique como:
   ["geral"]

5. A presença de um ano não torna a pergunta
   automaticamente temporal.

6. A palavra "Brasil" não torna a pergunta
   automaticamente geografica quando apenas
   delimita o escopo nacional.

7. Não invente outras categorias.

Retorne somente dimensões necessárias
para responder à pergunta.
"""




def classificar_dimensoes(
    state: AgentState
) -> AgentState:

    pergunta = state["pergunta"]

    try:

        contexto_anterior = state.get(
            "contexto_anterior"
        )

        if contexto_anterior:

            mensagem_classificacao = f"""
CONTEXTO DA CONVERSA:

{contexto_anterior}

PERGUNTA ATUAL:

{pergunta}

Use o contexto anterior somente para resolver
referências da pergunta atual.
"""

        else:
            mensagem_classificacao = pergunta

        resultado = classificador_dimensoes_llm.invoke(
            [
                SystemMessage(
                    content=SYSTEM_CLASSIFICADOR_DIMENSOES
                ),
                HumanMessage(
                    content=mensagem_classificacao
                ),
            ]
        )

        dimensoes = [
            dimensao
            for dimensao in resultado.dimensoes
            if dimensao in DIMENSOES_SUPORTADAS
        ]

        # Remove duplicatas preservando a ordem
        dimensoes = list(
            dict.fromkeys(dimensoes)
        )

        # Comportamento herdado:
        # ausência de dimensão válida -> geral
        if not dimensoes:
            dimensoes = ["geral"]

        return {
            **state,
            "dimensoes": dimensoes,
            "chamadas_llm":
                state["chamadas_llm"] + 1,
            "passos":
                state["passos"] + 1,
            "erro": None,
        }

    except Exception as e:

        return {
            **state,
            "dimensoes": [],
            "passos":
                state["passos"] + 1,
            "erro": str(e),
        }

from langchain_core.tools import tool

LOG_FERRAMENTAS = []


@tool
def ferramenta_documentos_semanticos(
    pergunta: str,
    dimensoes: List[str]
) -> List[Dict]:
    """
    Recupera seções relevantes dos documentos semânticos
    de acordo com a pergunta e as dimensões epidemiológicas.
    """

    dimensoes_validas = [
        dimensao
        for dimensao in dimensoes
        if dimensao in DIMENSOES_SUPORTADAS
    ]

    # Remove duplicatas preservando a ordem
    dimensoes_validas = list(
        dict.fromkeys(dimensoes_validas)
    )

    documentos = (
        recuperar_documentos_semanticos_compacto(
            pergunta=pergunta,
            dimensoes=dimensoes_validas,
            base_docs=BASE_DOCS,
        )
    )

    LOG_FERRAMENTAS.append(
        {
            "tool": "ferramenta_documentos_semanticos",

            "argumentos": {
                "pergunta": pergunta,
                "dimensoes": dimensoes_validas,
            },

            "documentos_retornados": [
                documento["arquivo"]
                for documento in documentos
            ],

            "secoes_retornadas": {
                documento["arquivo"]:
                    documento["secoes_selecionadas"]
                for documento in documentos
            },

            "caracteres_recuperados": sum(
                documento["caracteres_recuperados"]
                for documento in documentos
            ),
        }
    )

    return documentos

###
def formatar_evidencias_para_llm(
    evidencias: List[Dict]
) -> str:

    if not evidencias:
        return "Nenhuma evidência foi recuperada."

    blocos = []

    for evidencia in evidencias:

        bloco = f"""
DOCUMENTO: {evidencia["document_id"]}
DIMENSÃO: {evidencia["dimensao"]}

{evidencia["conteudo"]}
"""

        blocos.append(
            bloco.strip()
        )

    return "\n\n---\n\n".join(blocos)

def recuperar_evidencias(
    state: AgentState
) -> AgentState:

    try:

        dimensoes = state["dimensoes"]

        # Consulta usada para recuperação
        pergunta_recuperacao = state["pergunta"]

        contexto_anterior = state.get(
            "contexto_anterior"
        )

        # O contexto conversacional pode auxiliar a recuperação,
        # mas não é tratado como evidência factual.
        if contexto_anterior:

            pergunta_recuperacao = (
                f"{contexto_anterior}\n\n"
                f"Pergunta atual: {state['pergunta']}"
            )

        documentos = (
            ferramenta_documentos_semanticos.invoke(
                {
                    "pergunta": pergunta_recuperacao,
                    "dimensoes": dimensoes,
                }
            )
        )

        # Preserva evidências já recuperadas no mesmo turno
        documentos_existentes = {
            evidencia["arquivo"]
            for evidencia in state["evidencias"]
        }

        novos_documentos = [
            documento
            for documento in documentos
            if documento["arquivo"]
            not in documentos_existentes
        ]

        evidencias_atualizadas = (
            state["evidencias"]
            + novos_documentos
        )

        documentos_consultados = list(
            dict.fromkeys(
                [
                    evidencia["arquivo"]
                    for evidencia
                    in evidencias_atualizadas
                ]
            )
        )

        return {
            **state,

            "evidencias":
                evidencias_atualizadas,

            "documentos_consultados":
                documentos_consultados,

            "chamadas_ferramentas":
                state["chamadas_ferramentas"] + 1,

            "passos":
                state["passos"] + 1,

            "erro":
                None,
        }

    except Exception as e:

        return {
            **state,

            "chamadas_ferramentas":
                state["chamadas_ferramentas"] + 1,

            "passos":
                state["passos"] + 1,

            "erro":
                str(e),
        }
SYSTEM_VERIFICADOR_SUFICIENCIA = """
Você é responsável por verificar se as evidências
recuperadas são suficientes para responder a uma
pergunta epidemiológica.

Regras:

1. Utilize exclusivamente as evidências fornecidas.

2. Não utilize conhecimento externo.

3. Não responda à pergunta.

4. Apenas determine se as evidências permitem
   responder à pergunta de forma fundamentada.

5. Considere suficiente quando a informação
   necessária estiver explicitamente presente
   nas evidências recuperadas.

6. Não considere a evidência insuficiente apenas
   porque o período disponível corresponde a parte
   de um ano, desde que:
   - a informação solicitada esteja explicitamente
     presente; e
   - o período efetivamente analisado esteja
     claramente informado nas evidências.

7. A simples menção a um ano, como "em 2026",
   não significa automaticamente que a pergunta
   exige cobertura de todas as 52 ou 53 semanas
   epidemiológicas desse ano.

8. Diferencie perguntas como:
   "quantas notificações foram consideradas em 2026?"
   de perguntas que exigem explicitamente cobertura
   integral, como:
   "quantas notificações ocorreram durante todo o
   ano de 2026?"

9. Quando a evidência fornecer diretamente o valor
   solicitado e também informar a janela temporal
   correspondente, considere a evidência suficiente.
   A delimitação temporal poderá ser preservada
   posteriormente na resposta final.

10. Uma limitação de cobertura temporal deve ser
    tratada como uma ressalva ou delimitação do dado,
    e não automaticamente como ausência de evidência.

11. Considere insuficiente quando:
    - a informação solicitada não estiver presente;
    - houver conflito relevante entre evidências;
    - responder exigir inferência factual não
      sustentada pelas evidências disponíveis.

12. Se faltar informação, indique somente as
    dimensões epidemiológicas adicionais que
    poderiam realmente ajudar a responder.

13. Utilize somente estas dimensões:

- geral
- temporal
- geografica
- clinica
- virologica
- desfechos

14. Não invente dimensões.

15. O contexto conversacional pode ser utilizado
    apenas para resolver referências da pergunta atual.

16. O contexto conversacional não deve ser tratado
    como nova evidência epidemiológica. A suficiência
    factual deve ser determinada pelas evidências
    recuperadas.
"""
def verificar_suficiencia(
    state: AgentState
) -> AgentState:

    # Caso determinístico:
    # nenhuma evidência foi recuperada.
    if not state["evidencias"]:

        return {
            **state,
            "evidencia_suficiente": False,
            "justificativa_suficiencia":
                "Nenhuma evidência foi recuperada.",
            "dimensoes_faltantes":
                state["dimensoes"],
            "passos":
                state["passos"] + 1,
            "erro": None,
        }

    try:

        evidencias_texto = (
            formatar_evidencias_para_llm(
                state["evidencias"]
            )
        )

        contexto_conversa = state.get(
            "contexto_anterior"
        )

        mensagem = f"""
CONTEXTO CONVERSACIONAL:

{contexto_conversa or "Não há contexto anterior."}

PERGUNTA ATUAL:

{state["pergunta"]}

EVIDÊNCIAS RECUPERADAS:

{evidencias_texto}

Use o contexto conversacional somente para resolver
referências presentes na pergunta atual.

Avalie a suficiência com base exclusivamente nas
evidências recuperadas.
"""

        resultado = (
            verificador_suficiencia_llm.invoke(
                [
                    SystemMessage(
                        content=SYSTEM_VERIFICADOR_SUFICIENCIA
                    ),
                    HumanMessage(
                        content=mensagem
                    ),
                ]
            )
        )

        dimensoes_faltantes = [
            dimensao
            for dimensao
            in resultado.dimensoes_faltantes
            if dimensao in DIMENSOES_SUPORTADAS
        ]

        dimensoes_faltantes = list(
            dict.fromkeys(
                dimensoes_faltantes
            )
        )

        return {
            **state,
            "evidencia_suficiente":
                resultado.suficiente,
            "justificativa_suficiencia":
                resultado.justificativa,
            "dimensoes_faltantes":
                dimensoes_faltantes,
            "chamadas_llm":
                state["chamadas_llm"] + 1,
            "passos":
                state["passos"] + 1,
            "erro": None,
        }

    except Exception as e:

        return {
            **state,
            "evidencia_suficiente": False,
            "justificativa_suficiencia": None,
            "dimensoes_faltantes": [],
            "passos":
                state["passos"] + 1,
            "erro": str(e),
        }
# ============================================================
# ROTEAMENTO E RECUPERAÇÃO COMPLEMENTAR
# ============================================================

def decidir_apos_suficiencia(
    state: AgentState
) -> str:
    """
    Decide o próximo passo após a avaliação
    da suficiência das evidências.
    """

    # 1. Erro durante o processamento
    if state["erro"] is not None:
        return "abster"

    # 2. Limite de passos atingido
    if state["passos"] >= MAX_PASSOS:
        return "abster"

    # 3. Evidência suficiente
    if state["evidencia_suficiente"]:
        return "gerar_resposta"

    # 4. Há dimensões adicionais ainda não consultadas?
    dimensoes_novas = [
        dimensao
        for dimensao
        in state["dimensoes_faltantes"]
        if (
            dimensao in DIMENSOES_SUPORTADAS
            and dimensao not in state["dimensoes"]
        )
    ]

    if dimensoes_novas:
        return "recuperar_complemento"

    # 5. Não há como ampliar a recuperação
    return "abster"


def preparar_recuperacao_complementar(
    state: AgentState
) -> AgentState:
    """
    Incorpora dimensões adicionais indicadas pelo
    verificador de suficiência e prepara nova recuperação.
    """

    dimensoes_novas = [
        dimensao
        for dimensao
        in state["dimensoes_faltantes"]
        if (
            dimensao in DIMENSOES_SUPORTADAS
            and dimensao not in state["dimensoes"]
        )
    ]

    dimensoes_atualizadas = list(
        dict.fromkeys(
            state["dimensoes"]
            + dimensoes_novas
        )
    )

    return {
        **state,

        "dimensoes":
            dimensoes_atualizadas,

        "dimensoes_faltantes":
            [],

        "evidencia_suficiente":
            False,

        "justificativa_suficiencia":
            None,

        "passos":
            state["passos"] + 1,
    }
# ============================================================
# NÓS TERMINAIS: RESPOSTA E ABSTENÇÃO
# ============================================================

SYSTEM_RESPOSTA = """
Você é um assistente especializado em análise de
documentos epidemiológicos.

Sua tarefa é responder à pergunta utilizando
EXCLUSIVAMENTE as evidências recuperadas pelo workflow.

Regras:

1. Não utilize conhecimento externo.

2. Não invente valores, relações ou interpretações.

3. Sempre forneça evidências presentes nos documentos
   recuperados.

4. Preserve números, percentuais, períodos e unidades.

5. Considere explicitamente limitações descritas
   nos documentos.

6. Quando a pergunta envolver mais de uma dimensão,
   integre as evidências relevantes dos diferentes
   documentos.

7. Se as evidências não forem suficientes:
   - insufficient_information = true;
   - confidence = "baixa";
   - não complete a resposta com conhecimento externo.

8. document_id deve identificar o(s) documento(s)
   efetivamente utilizados na resposta.

9. Não realize cálculos derivados que não estejam
   explicitamente presentes nas evidências, a menos que
   uma ferramenta de cálculo tenha sido utilizada.

A resposta deve seguir o esquema estruturado definido.
"""




def abster_resposta(
    state: AgentState
) -> AgentState:
    """
    Produz uma resposta estruturada de abstenção
    quando as evidências são insuficientes.
    """

    documentos = state[
        "documentos_consultados"
    ]

    if documentos:
        document_id = "; ".join(
            documentos
        )
    else:
        document_id = (
            "nenhum_documento_recuperado"
        )

    resposta = RespostaEstruturada(

        answer=(
            "As evidências disponíveis não são "
            "suficientes para responder à pergunta "
            "com segurança."
        ),

        evidence=[],

        document_id=document_id,

        confidence="baixa",

        insufficient_information=True,
    )

    return {
        **state,

        "resposta_final":
            resposta,

        "passos":
            state["passos"] + 1,
    }


def gerar_resposta(
    state: AgentState
) -> AgentState:
    """
    Gera a resposta final exclusivamente a partir
    das evidências recuperadas pelo workflow.
    """

    try:

        contexto = (
            formatar_evidencias_para_llm(
                state["evidencias"]
            )
        )

        contexto_conversa = state.get(
            "contexto_anterior"
        )

        mensagem_usuario = f"""
CONTEXTO CONVERSACIONAL:

{contexto_conversa or "Não há contexto anterior."}

EVIDÊNCIAS RECUPERADAS:

{contexto}

PERGUNTA ATUAL:

{state["pergunta"]}

Use o contexto conversacional somente para resolver
referências presentes na pergunta atual.

Os fatos epidemiológicos da resposta devem ser
fundamentados nas evidências recuperadas.
"""

        resultado = structured_llm.invoke(
            [
                SystemMessage(
                    content=SYSTEM_RESPOSTA
                ),
                HumanMessage(
                    content=mensagem_usuario
                ),
            ]
        )

        return {
            **state,

            "resposta_final":
                resultado,

            "chamadas_llm":
                state["chamadas_llm"] + 1,

            "passos":
                state["passos"] + 1,

            "erro":
                None,
        }

    except Exception as e:

        return {
            **state,

            "passos":
                state["passos"] + 1,

            "erro":
                str(e),
        }
# ============================================================
# CONSTRUÇÃO DO WORKFLOW
# ============================================================


def construir_workflow():

    builder = StateGraph(
        AgentState
    )

    # --------------------------------------------------------
    # NÓS
    # --------------------------------------------------------

    builder.add_node(
        "classificar_dimensoes",
        classificar_dimensoes,
    )

    builder.add_node(
        "recuperar_evidencias",
        recuperar_evidencias,
    )

    builder.add_node(
        "verificar_suficiencia",
        verificar_suficiencia,
    )

    builder.add_node(
        "preparar_recuperacao_complementar",
        preparar_recuperacao_complementar,
    )

    builder.add_node(
        "gerar_resposta",
        gerar_resposta,
    )

    builder.add_node(
        "abster",
        abster_resposta,
    )

    # --------------------------------------------------------
    # FLUXO PRINCIPAL
    # --------------------------------------------------------

    builder.add_edge(
        START,
        "classificar_dimensoes",
    )

    builder.add_edge(
        "classificar_dimensoes",
        "recuperar_evidencias",
    )

    builder.add_edge(
        "recuperar_evidencias",
        "verificar_suficiencia",
    )

    # --------------------------------------------------------
    # ROTEAMENTO CONDICIONAL
    # --------------------------------------------------------

    builder.add_conditional_edges(
        "verificar_suficiencia",

        decidir_apos_suficiencia,

        {
            "gerar_resposta":
                "gerar_resposta",

            "recuperar_complemento":
                "preparar_recuperacao_complementar",

            "abster":
                "abster",
        },
    )

    # Recuperação complementar retorna ao recuperador
    builder.add_edge(
        "preparar_recuperacao_complementar",
        "recuperar_evidencias",
    )

    # --------------------------------------------------------
    # TÉRMINO
    # --------------------------------------------------------

    builder.add_edge(
        "gerar_resposta",
        END,
    )

    builder.add_edge(
        "abster",
        END,
    )

    return builder.compile()

def executar_sistema(
    pergunta: str
):
    """
    Executa uma pergunta no workflow e retorna:

    - resposta estruturada;
    - métricas da execução;
    - estado final completo.
    """

    _verificar_configuracao()

    estado_inicial = (
        criar_estado_inicial(
            pergunta
        )
    )

    inicio = time.perf_counter()

    resultado = workflow.invoke(
        estado_inicial,
        config={
            "recursion_limit":
                MAX_PASSOS + 5
        },
    )

    latencia = (
        time.perf_counter()
        - inicio
    )

    resposta = resultado[
        "resposta_final"
    ]

    metricas = {

        "latencia_s":
            round(latencia, 3),

        "chamadas_llm":
            resultado["chamadas_llm"],

        "chamadas_ferramentas":
            resultado["chamadas_ferramentas"],

        "passos":
            resultado["passos"],

        "dimensoes":
            resultado["dimensoes"],

        "documentos_consultados":
            resultado["documentos_consultados"],

        "evidencia_suficiente":
            resultado["evidencia_suficiente"],

        "erro":
            resultado["erro"],
    }

    return (
        resposta,
        metricas,
        resultado,
    )
