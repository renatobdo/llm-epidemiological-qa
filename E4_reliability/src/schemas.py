from typing import (
    Dict,
    List,
    Literal,
    Optional,
    TypedDict,
)

from pydantic import (
    BaseModel,
    Field,
)


class RespostaEstruturada(BaseModel):

    answer: str = Field(
        description=(
            "Resposta direta à pergunta "
            "epidemiológica."
        )
    )

    evidence: List[str] = Field(
        default_factory=list,
        description=(
            "Trechos declarados como evidência "
            "para sustentar a resposta."
        )
    )

    document_id: str = Field(
        description=(
            "Identificador do documento ou "
            "documentos utilizados."
        )
    )

    confidence: Literal[
        "alta",
        "media",
        "baixa",
    ] = Field(
        description=(
            "Confiança da resposta considerando "
            "apenas as evidências disponíveis."
        )
    )

    insufficient_information: bool = Field(
        description=(
            "True quando as evidências disponíveis "
            "não são suficientes para responder."
        )
    )


class ClassificacaoDimensoes(BaseModel):

    dimensoes: List[str] = Field(
        description=(
            "Lista das dimensões epidemiológicas "
            "necessárias para responder à pergunta."
        )
    )

    justificativa: str = Field(
        description=(
            "Justificativa breve para as dimensões "
            "selecionadas."
        )
    )


class VerificacaoSuficiencia(BaseModel):

    suficiente: bool = Field(
        description=(
            "True somente quando as evidências "
            "recuperadas contêm informação suficiente "
            "para responder à pergunta."
        )
    )

    justificativa: str = Field(
        description=(
            "Justificativa breve baseada exclusivamente "
            "nas evidências recuperadas."
        )
    )

    dimensoes_faltantes: List[str] = Field(
        default_factory=list,
        description=(
            "Dimensões adicionais que parecem necessárias "
            "quando a evidência recuperada é insuficiente."
        )
    )


class AgentState(TypedDict):

    # Entrada
    pergunta: str

    # Interpretação
    dimensoes: List[str]
    plano_recuperacao: List[str]

    # Recuperação
    evidencias: List[Dict]
    documentos_consultados: List[str]

    evidencia_suficiente: bool
    justificativa_suficiencia: Optional[str]
    dimensoes_faltantes: List[str]

    # Saída
    resposta_final: Optional[
        RespostaEstruturada
    ]

    # Contexto conversacional
    historico_conversa: List[Dict]
    contexto_anterior: Optional[str]
    pergunta_anterior: Optional[str]

    # Métricas
    chamadas_llm: int
    chamadas_ferramentas: int

    # Controle
    passos: int
    erro: Optional[str]
