from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, Field


class LLMGenerate(BaseModel):
    type: Literal["llm_generate"]
    prompt: str


class LLMPatch(BaseModel):
    type: Literal["llm_patch"]
    prompt: str


class CreateFileStep(BaseModel):
    action: Literal["create_file"]
    path: str
    content: Optional[str] = None
    content_source: Optional[LLMGenerate] = None


class EditFileStep(BaseModel):
    action: Literal["edit_file"]
    path: str
    patch_source: LLMPatch


class RunCmdStep(BaseModel):
    action: Literal["run_cmd"]
    cmd: str


class AssertContainsStep(BaseModel):
    action: Literal["assert_contains"]
    path: str
    text: str


class AssertBuildSuccessStep(BaseModel):
    action: Literal["assert_build_success"]


class LLMStep(BaseModel):
    action: Literal["llm_step"]
    analysis: str
    allowed_actions: List[Literal["create_file", "edit_file"]] = Field(
        default_factory=lambda: ["create_file", "edit_file"]
    )
    allowed_paths: List[str] = Field(default_factory=list)


Step = Annotated[
    CreateFileStep
    | EditFileStep
    | RunCmdStep
    | AssertContainsStep
    | AssertBuildSuccessStep
    | LLMStep,
    Field(discriminator="action"),
]


class PlanConstraints(BaseModel):
    max_files_changed: Optional[int] = 100
    forbid_paths: List[str] = Field(default_factory=list)


class Plan(BaseModel):
    mode: Literal["fix", "feature"]
    task: str
    repo_root: str
    constraints: Optional[PlanConstraints] = None
    steps: List[Step]
