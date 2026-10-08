import re
import time
import unicodedata
from typing import Any, Dict, List

from src.schemas import AgentState
from src.recuperacao import normalizar_texto
from src.workflow import executar_sistema, formatar_evidencias_para_llm

# ============================================================
# A.5 — VERIFICADORES DO BENCHMARK HERDADO
# ============================================================

def verificar_elementos_esperados(
    resposta: str,
    esperados
):
    """
    Verifica a presença dos elementos esperados na resposta.
    Preserva o critério utilizado no benchmark anterior.
    """

    if esperados is None:
        return None, None

    if len(esperados) == 0:
        return [], None

    resposta_norm = normalizar_texto(resposta)

    encontrados = []

    for esperado in esperados:
        esperado_norm = normalizar_texto(esperado)

        encontrados.append(
            esperado_norm in resposta_norm
        )

    cobertura = (
        sum(encontrados) / len(encontrados)
    )

    return encontrados, cobertura


def verificar_caso_benchmark(
    caso,
    resultado
):
    """
    Aplica os critérios herdados aos casos automáticos.
    Casos manuais permanecem sinalizados para inspeção.
    """

    # --------------------------------------------------------
    # Avaliação manual
    # --------------------------------------------------------

    if caso["verificacao"] == "manual":

        return {
            "aprovado": None,
            "cobertura": None,
            "elementos_encontrados": None,
            "abstencao_correta": None,
            "possui_evidencias": bool(resultado.evidence),
            "avaliacao": "manual",
        }

    # --------------------------------------------------------
    # Informação ausente
    # --------------------------------------------------------

    if caso["tipo"] == "informacao_ausente":

        aprovado = (
            resultado.insufficient_information is True
        )

        return {
            "aprovado": aprovado,
            "cobertura": None,
            "elementos_encontrados": None,
            "abstencao_correta": aprovado,
            "possui_evidencias": bool(resultado.evidence),
            "avaliacao": "automatica",
        }

    # --------------------------------------------------------
    # Casos objetivos
    # --------------------------------------------------------

    encontrados, cobertura = (
        verificar_elementos_esperados(
            resultado.answer,
            caso["esperado"],
        )
    )

    cobertura_minima = caso.get(
        "cobertura_minima",
        1.0,
    )

    aprovado = (
        cobertura is not None
        and cobertura >= cobertura_minima
        and resultado.insufficient_information is False
    )

    return {
        "aprovado": aprovado,
        "cobertura": cobertura,
        "elementos_encontrados": encontrados,
        "abstencao_correta": None,
        "possui_evidencias": bool(resultado.evidence),
        "avaliacao": "automatica",
    }
def extrair_trace_execucao(
    estado: AgentState
) -> Dict[str, Any]:
    """
    Extrai informações intermediárias do workflow
    sem alterar o comportamento do sistema.
    """

    evidencias_recuperadas = (
        estado.get("evidencias", [])
        or []
    )

    documentos = [
        evidencia.get("arquivo")
        for evidencia in evidencias_recuperadas
    ]

    secoes = {
        evidencia.get("arquivo"):
            evidencia.get(
                "secoes_selecionadas",
                []
            )
        for evidencia
        in evidencias_recuperadas
    }

    contexto_recuperado = (
        formatar_evidencias_para_llm(
            evidencias_recuperadas
        )
        if evidencias_recuperadas
        else ""
    )

    return {
        "dimensoes_detectadas":
            estado.get("dimensoes", []),

        "documentos_consultados":
            documentos,

        "secoes_recuperadas":
            secoes,

        "evidencias_recuperadas":
            evidencias_recuperadas,

        "contexto_recuperado":
            contexto_recuperado,

        "evidencia_suficiente":
            estado.get(
                "evidencia_suficiente"
            ),

        "justificativa_suficiencia":
            estado.get(
                "justificativa_suficiencia"
            ),

        "dimensoes_faltantes":
            estado.get(
                "dimensoes_faltantes",
                []
            ),

        "erro":
            estado.get("erro"),
    }
# ============================================================
# VALIDAÇÃO DE FIDELIDADE DAS EVIDÊNCIAS
# ============================================================

def normalizar_para_validacao(
    texto: str
) -> str:
    """
    Normaliza texto para comparação determinística
    de evidências, removendo diferenças puramente
    de formatação.
    """

    if not texto:
        return ""

    # Remove acentos
    texto = unicodedata.normalize(
        "NFKD",
        texto
    )

    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(
            caractere
        )
    )

    # Minúsculas
    texto = texto.lower()

    # Remove marcações Markdown
    texto = re.sub(
        r"[*_`#]",
        "",
        texto
    )

    # Normaliza espaços
    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()

def validar_evidencias_declaradas(
    evidencias_declaradas: List[str],
    contexto_recuperado: str,
) -> Dict[str, Any]:
    """
    Verifica se cada evidência declarada pelo modelo
    pode ser localizada no contexto efetivamente
    disponibilizado para geração da resposta.
    """

    contexto_normalizado = (
        normalizar_para_validacao(
            contexto_recuperado
        )
    )

    resultados = []

    for evidencia in evidencias_declaradas:

        evidencia_normalizada = (
            normalizar_para_validacao(
                evidencia
            )
        )

        encontrada = (
            bool(evidencia_normalizada)
            and evidencia_normalizada
            in contexto_normalizado
        )

        resultados.append(
            {
                "evidencia":
                    evidencia,

                "encontrada_no_contexto":
                    encontrada,
            }
        )

    total = len(resultados)

    total_validadas = sum(
        item["encontrada_no_contexto"]
        for item in resultados
    )

    fidelidade = (
        total_validadas / total
        if total > 0
        else None
    )

    return {
        "total_evidencias":
            total,

        "total_validadas":
            total_validadas,

        "fidelidade":
            fidelidade,

        "todas_validadas":
            (
                total > 0
                and total_validadas == total
            ),

        "detalhes":
            resultados,
    }
def executar_caso(
    caso: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Executa um caso de teste e produz um registro
    padronizado para avaliação posterior.
    """

    inicio = time.perf_counter()

    try:

        resposta, metricas, estado = (
            executar_sistema(
                caso["pergunta"]
            )
        )

        latencia_total = (
            time.perf_counter()
            - inicio
        )

        verificacao = (
            verificar_caso_benchmark(
                caso,
                resposta,
            )
        )

        trace = extrair_trace_execucao(
            estado
        )
        validacao_evidencias = (
            validar_evidencias_declaradas(
                evidencias_declaradas=
                    resposta.evidence,

                contexto_recuperado=
                    trace[
                        "contexto_recuperado"
                    ],
            )
        )

        return {

            # ----------------------------------------------
            # Identificação do caso
            # ----------------------------------------------

            "id":
                caso["id"],

            "grupo":
                caso["grupo"],

            "dimensao":
                caso["dimensao"],

            "tipo":
                caso["tipo"],

            "verificacao":
                caso["verificacao"],

            "pergunta":
                caso["pergunta"],

            "esperado":
                caso["esperado"],

            # ----------------------------------------------
            # Resposta do sistema
            # ----------------------------------------------

            "resposta":
                resposta.answer,

            "evidencias_declaradas":
                resposta.evidence,

            "documento_declarado":
                resposta.document_id,

            "confianca":
                resposta.confidence,

            "informacao_insuficiente":
                resposta.insufficient_information,

            # ----------------------------------------------
            # Benchmark herdado
            # ----------------------------------------------

            "avaliacao":
                verificacao["avaliacao"],

            "cobertura":
                verificacao["cobertura"],

            "aprovado":
                verificacao["aprovado"],

            "abstencao_correta":
                verificacao[
                    "abstencao_correta"
                ],

            # Mantido apenas para comparação
            # com o critério anterior.
            "possui_evidencias":
                verificacao[
                    "possui_evidencias"
                ],


            # ----------------------------------------------
            # Fidelidade textual das evidências
            # ----------------------------------------------

            "total_evidencias_declaradas":
                validacao_evidencias[
                    "total_evidencias"
                ],

            "total_evidencias_validadas":
                validacao_evidencias[
                    "total_validadas"
                ],

            "fidelidade_evidencias":
                validacao_evidencias[
                    "fidelidade"
                ],

            "todas_evidencias_validadas":
                validacao_evidencias[
                    "todas_validadas"
                ],

            "detalhes_validacao_evidencias":
                validacao_evidencias[
                    "detalhes"
                ],

            # ----------------------------------------------
            # Trace do workflow
            # ----------------------------------------------

            "dimensoes_detectadas":
                trace[
                    "dimensoes_detectadas"
                ],

            "documentos_consultados":
                trace[
                    "documentos_consultados"
                ],

            "secoes_recuperadas":
                trace[
                    "secoes_recuperadas"
                ],

            "evidencias_recuperadas":
                trace[
                    "evidencias_recuperadas"
                ],

            "contexto_recuperado":
                trace[
                    "contexto_recuperado"
                ],

            "evidencia_suficiente":
                trace[
                    "evidencia_suficiente"
                ],

            "justificativa_suficiencia":
                trace[
                    "justificativa_suficiencia"
                ],

            # ----------------------------------------------
            # Métricas operacionais
            # ----------------------------------------------

            "latencia_s":
                round(
                    latencia_total,
                    3
                ),

            "chamadas_llm":
                metricas[
                    "chamadas_llm"
                ],

            "chamadas_ferramentas":
                metricas[
                    "chamadas_ferramentas"
                ],

            "passos":
                metricas["passos"],

            "erro":
                metricas["erro"],
        }

    except Exception as e:

        return {

            # ----------------------------------------------
            # Identificação do caso
            # ----------------------------------------------

            "id":
                caso["id"],

            "grupo":
                caso["grupo"],

            "dimensao":
                caso["dimensao"],

            "tipo":
                caso["tipo"],

            "verificacao":
                caso["verificacao"],

            "pergunta":
                caso["pergunta"],

            "esperado":
                caso["esperado"],

            # ----------------------------------------------
            # Resposta do sistema
            # ----------------------------------------------

            "resposta":
                None,

            "evidencias_declaradas":
                [],

            "documento_declarado":
                None,

            "confianca":
                None,

            "informacao_insuficiente":
                None,

            # ----------------------------------------------
            # Benchmark herdado
            # ----------------------------------------------

            "avaliacao":
                caso["verificacao"],

            "cobertura":
                None,

            "aprovado":
                False,

            "abstencao_correta":
                None,

            "possui_evidencias":
                False,

            # ----------------------------------------------
            # Fidelidade textual das evidências
            # ----------------------------------------------

            "total_evidencias_declaradas":
                0,

            "total_evidencias_validadas":
                0,

            "fidelidade_evidencias":
                None,

            "todas_evidencias_validadas":
                False,

            "detalhes_validacao_evidencias":
                [],

            # ----------------------------------------------
            # Trace do workflow
            # ----------------------------------------------

            "dimensoes_detectadas":
                [],

            "documentos_consultados":
                [],

            "secoes_recuperadas":
                {},

            "evidencias_recuperadas":
                [],

            "contexto_recuperado":
                "",

            "evidencia_suficiente":
                None,

            "justificativa_suficiencia":
                None,

            # ----------------------------------------------
            # Métricas operacionais
            # ----------------------------------------------

            "latencia_s":
                round(
                    time.perf_counter()
                    - inicio,
                    3
                ),

            "chamadas_llm":
                None,

            "chamadas_ferramentas":
                None,

            "passos":
                None,

            "erro":
                str(e),
        }
