"""Pydantic v2 models for admiral-mcp."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RunPhase(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    DENY = "deny"
    TIMEOUT = "timeout"


class RunRecord(BaseModel):
    run_id: str
    repo: str
    phases: list[str]
    harness: str
    current_phase: int = 0
    status: RunPhase = RunPhase.QUEUED
    cost: float = 0.0
    diff_content: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApprovalRecord(BaseModel):
    approval_id: str
    run_id: str
    summary: str
    diff_ref: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decision: ApprovalDecision | None = None


class RegisterRunResult(BaseModel):
    success: bool
    message: str
    run_id: str


class UpdateProgressResult(BaseModel):
    success: bool
    message: str
    run_id: str
    phase: int


class RequestApprovalResult(BaseModel):
    success: bool
    message: str
    approval_id: str
    decision: ApprovalDecision


class ResolveApprovalResult(BaseModel):
    success: bool
    message: str
    approval_id: str
    decision: ApprovalDecision


class GetDiffResult(BaseModel):
    success: bool
    message: str
    diff_ref: str
    content: str | None = None
