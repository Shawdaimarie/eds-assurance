"""Strict public contracts. Tenant identity is always supplied by authentication."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


Identifier = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,95}$")]
NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Source(Contract):
    source_id: Identifier
    title: Annotated[NonEmpty, Field(max_length=300)]
    content: Annotated[NonEmpty, Field(max_length=50_000)]
    # Attribution only; the service never fetches URLs supplied in source content.
    source_url: Annotated[str, StringConstraints(pattern=r"^https://[^\s]+$", max_length=2048)] | None = None


class Case(Contract):
    case_id: Identifier
    prompt: Annotated[NonEmpty, Field(max_length=8000)]
    expected_behavior: Literal["answer", "abstain"]
    allowed_source_ids: list[Identifier] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_sources(self):
        if len(self.allowed_source_ids) != len(set(self.allowed_source_ids)):
            raise ValueError("allowed_source_ids must be unique")
        if self.expected_behavior == "answer" and not self.allowed_source_ids:
            raise ValueError("answer cases require at least one allowed source")
        return self


class Dataset(Contract):
    name: Annotated[NonEmpty, Field(max_length=200)]
    cases: list[Case] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_cases(self):
        ids = [case.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("case IDs must be unique")
        return self


class Citation(Contract):
    source_id: Identifier
    quote: Annotated[NonEmpty, Field(max_length=8000)]


class TokenUsage(Contract):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    cache_creation_input_tokens: int = Field(default=0, ge=0)


class CollectionMetadata(Contract):
    provider: Literal["openai", "anthropic", "xai"]
    requested_model: Annotated[NonEmpty, Field(max_length=200)]
    returned_model: Annotated[NonEmpty, Field(max_length=200)] | None = None
    provider_request_id: Annotated[str, Field(max_length=256)] | None = None
    request_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    response_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    collector_version: Literal["http-collector-v1"] = "http-collector-v1"
    timing_source: Literal["client_perf_counter"] = "client_perf_counter"
    usage: TokenUsage | None = None
    input_rate_usd_per_million: float | None = Field(default=None, ge=0)
    output_rate_usd_per_million: float | None = Field(default=None, ge=0)
    cost_basis: Literal["unavailable", "operator_rate_estimate"] = "unavailable"


class Observation(Contract):
    case_id: Identifier
    answer: str = Field(max_length=12_000)
    abstained: bool
    citations: list[Citation] = Field(default_factory=list, max_length=30)
    reported_latency_ms: float = Field(ge=0, le=86_400_000)
    reported_cost_usd: float | None = Field(default=None, ge=0, le=100_000)
    collection: CollectionMetadata | None = None

    @model_validator(mode="after")
    def valid_answer(self):
        if not self.abstained and not self.answer.strip():
            raise ValueError("non-abstaining responses require an answer")
        return self


class Policy(Contract):
    min_behavior_pass_rate: float = Field(default=1.0, ge=0, le=1)
    min_evidence_contract_pass_rate: float = Field(default=1.0, ge=0, le=1)
    max_reported_p95_latency_ms: float = Field(default=500.0, gt=0)
    max_reported_total_cost_usd: float = Field(default=1.0, ge=0)


class RunRequest(Contract):
    dataset_id: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    label: Annotated[NonEmpty, Field(max_length=200)]
    model_label: Annotated[NonEmpty, Field(max_length=200)]
    observation_kind: Literal["synthetic_fixture", "recorded_model_output", "live_model_output"]
    observations: list[Observation] = Field(min_length=1, max_length=100)
    policy: Policy = Field(default_factory=Policy)

    @model_validator(mode="after")
    def live_provenance(self):
        if self.observation_kind == "live_model_output" and any(item.collection is None for item in self.observations):
            raise ValueError("live observations require collector metadata")
        return self
