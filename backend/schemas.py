from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator


AmbiguityType = Literal["lexical", "syntactic", "semantic", "syntax", "pragmatic"]
Classification = Literal["clean", "ambiguous"]
TypeSource = Literal[
    "stage_b",
    "linguistic",
    "linguistic_override",
    "heuristic",
    "hybrid",
    "bert",
    "llm",
]
IssueSeverity = Literal["high", "medium", "low"]
EvidenceSource = Literal["bert", "linguistic", "hybrid", "llm"]
IssueSource = Literal["linguistic", "llm"]
RequirementKind = Literal[
    "functional",
    "performance",
    "security",
    "usability",
    "availability",
    "compatibility",
    "other",
]


class AnalyzeRequest(BaseModel):
    requirement: str = Field(..., min_length=1, max_length=2000)

    @field_validator("requirement")
    @classmethod
    def requirement_must_have_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("requirement must not be empty or whitespace-only")
        return stripped


class StageAPrediction(BaseModel):
    """Stage A ML evidence: clean vs ambiguous. Not the final assessment."""

    label: Classification = Field(..., description="Stage A predicted label.")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Stage A probability of the predicted label.",
    )
    source: Literal["bert"] = "bert"
    stage: Literal["stage_a"] = "stage_a"


class StageBPrediction(BaseModel):
    """Stage B ML evidence: sentence-level type. Never overwrites the final type."""

    label: AmbiguityType = Field(..., description="Stage B predicted type.")
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Stage B probability of the predicted type, if available.",
    )
    source: Literal["bert"] = "bert"
    stage: Literal["stage_b"] = "stage_b"


class MlPrediction(BaseModel):
    """Raw two-stage BERT evidence. Canonical nested fields are stage_a and stage_b."""

    classification: Classification = Field(
        ...,
        description="Backward-compatible Stage A label.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Backward-compatible Stage A confidence.",
    )
    ambiguity_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Stage A P(ambiguous) as 0-100. Not the fused final score.",
    )
    source: Literal["bert"] = "bert"
    stage: Literal["stage_a"] = "stage_a"
    stage_b_type: AmbiguityType | None = Field(
        default=None,
        description="Backward-compatible Stage B type.",
    )
    stage_a: StageAPrediction | None = None
    stage_b: StageBPrediction | None = None


class DetectedIssue(BaseModel):
    """One linguistic finding. Spans come from the detector, not BERT tokens."""

    phrase: str
    start: int
    end: int
    ambiguity_type: AmbiguityType
    category: str
    reason: str
    suggestion: str
    severity: IssueSeverity
    confidence: float = Field(0.95, ge=0.0, le=1.0)
    source: Literal["linguistic"] = "linguistic"

    @computed_field
    @property
    def type(self) -> AmbiguityType:
        return self.ambiguity_type


class IssueView(BaseModel):
    """Normalized issue for frontend highlighting and cards."""

    id: str
    phrase: str
    start: int
    end: int
    type: AmbiguityType
    ambiguity_type: AmbiguityType
    severity: IssueSeverity
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: IssueSource = "linguistic"
    reason: str
    suggestion: str
    category: str


class FinalAssessment(BaseModel):
    """Canonical conclusion after evidence fusion.

    ``ambiguity_score`` is internal (higher = more ambiguous).
    ``clarity_score`` is user-facing requirement quality (higher = clearer).
    ``score`` is an alias of ``clarity_score`` for the UI.
    """

    status: Classification = Field(..., description="Authoritative clean vs ambiguous.")
    ambiguity_score: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="Fused ambiguity 0-10 (higher = more ambiguous).",
    )
    clarity_score: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="Requirement quality / clarity 0-10 (higher = clearer).",
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="Alias of clarity_score for user-facing displays.",
    )
    severity: IssueSeverity | None = None
    ambiguity_type: AmbiguityType | None = Field(
        default=None,
        description="Canonical final type (same as type).",
    )
    type: AmbiguityType | None = Field(
        default=None,
        description="Canonical final type after fusion.",
    )
    source: EvidenceSource = "bert"


class LlmPhraseView(BaseModel):
    """One LLM-identified phrase. Spans are located in the original text."""

    text: str
    reason: str
    suggestion: str = ""
    start: int | None = None
    end: int | None = None
    source: Literal["llm"] = "llm"

    @computed_field
    @property
    def phrase(self) -> str:
        return self.text


class LlmAnalysis(BaseModel):
    """Independent LLM reasoning evidence. Never includes provider secrets."""

    available: bool
    reason: str | None = Field(
        default=None,
        description="Safe unavailable reason such as 'Optional review unavailable'.",
    )
    is_ambiguous: bool | None = None
    score: float | None = Field(default=None, ge=0.0, le=10.0)
    type: AmbiguityType | None = None
    ambiguity_type: AmbiguityType | None = None
    severity: IssueSeverity | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    explanation: str | None = None
    ambiguous_phrases: list[LlmPhraseView] = Field(default_factory=list)
    source: Literal["llm"] = "llm"


class UserPhrase(BaseModel):
    """One user-facing ambiguous phrase with a local explanation."""

    text: str
    start: int | None = None
    end: int | None = None
    ambiguity_type: AmbiguityType | None = None
    type_label: str | None = None
    severity: IssueSeverity | None = None
    why: str
    suggestion: str = ""
    specify: str | None = None


class UserAssessment(BaseModel):
    """Default-facing analysis result. Hides pipeline internals."""

    status: Literal["needs_improvement", "clear"]
    title: str
    ambiguity_type: AmbiguityType | None = None
    type_label: str | None = None
    why: str
    suggested_requirement: str | None = None
    missing_information: list[str] = Field(default_factory=list)
    phrases: list[UserPhrase] = Field(default_factory=list)
    requirement_type: RequirementKind | None = None
    requirement_type_label: str | None = None
    score: float | None = Field(
        default=None,
        ge=0.0,
        le=10.0,
        description="User-facing clarity / requirement quality (higher = clearer).",
    )
    score_label: str | None = None
    ambiguity_score: float | None = Field(
        default=None,
        ge=0.0,
        le=10.0,
        description="Fused ambiguity 0-10 (higher = more ambiguous).",
    )
    clarity_score: float | None = Field(
        default=None,
        ge=0.0,
        le=10.0,
        description="Same as score: clarity 0-10 (higher = clearer).",
    )


class AnalyzeResponse(BaseModel):
    """Hybrid analysis response.

    Canonical fields: final_assessment, ml_prediction.stage_a/stage_b,
    linguistic_findings, llm_analysis, issues, suggested_requirement.
    Legacy top-level classification/confidence/ambiguity_score remain BERT-only.
    """

    requirement: str
    classification: Classification = Field(
        ...,
        description="Legacy BERT Stage A label. Use final_assessment.status.",
    )
    ambiguity_type: AmbiguityType | None = Field(
        default=None,
        description="Legacy alias of final_assessment.type.",
    )
    ambiguity_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Legacy Stage A P(ambiguous)×100. Use ml_prediction.ambiguity_score.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Legacy Stage A confidence. Use ml_prediction.stage_a.confidence.",
    )
    explanation: str
    suggested_requirement: str | None
    type_source: TypeSource | None = None
    flagged_phrase: str | None = None
    flagged_start: int | None = None
    flagged_end: int | None = None
    overall_status: Classification = Field(
        default="clean",
        description="Alias of final_assessment.status.",
    )
    ml_prediction: MlPrediction | None = None
    detected_issues: list[DetectedIssue] = Field(default_factory=list)
    linguistic_findings: list[DetectedIssue] = Field(default_factory=list)
    issues: list[IssueView] = Field(default_factory=list)
    linguistic_severity: IssueSeverity | None = None
    final_assessment: FinalAssessment | None = None
    final_score: float | None = Field(
        default=None,
        ge=0.0,
        le=10.0,
        description="Alias of final_assessment.clarity_score (user-facing).",
    )
    fused_ambiguity_score: float | None = Field(
        default=None,
        ge=0.0,
        le=10.0,
        description="Fused ambiguity 0-10 (higher = more ambiguous).",
    )
    clarity_score: float | None = Field(
        default=None,
        ge=0.0,
        le=10.0,
        description="Requirement quality / clarity 0-10 (higher = clearer).",
    )
    llm_analysis: LlmAnalysis | None = None
    user_assessment: UserAssessment | None = None
    missing_information: list[str] = Field(default_factory=list)


class QualityCheck(BaseModel):
    id: str
    label: str
    passed: bool
    detail: str | None = None


class GenerateRequest(BaseModel):
    idea: str = Field(..., min_length=1, max_length=2000)
    requirement_type: RequirementKind | None = None
    details: str | None = Field(default=None, max_length=2000)

    @field_validator("idea")
    @classmethod
    def idea_must_have_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("idea must not be empty or whitespace-only")
        return stripped


class GenerateResponse(BaseModel):
    idea: str
    requirement_type: RequirementKind
    suggested_requirement: str
    explanation: str
    missing_information: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    ready_to_use: bool = False
    quality_checks: list[QualityCheck] = Field(default_factory=list)
    analysis: AnalyzeResponse | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    model_loaded: bool
    stage_a_loaded: bool
    stage_b_loaded: bool
    error: str | None = None


class ErrorResponse(BaseModel):
    error: str
    code: str
