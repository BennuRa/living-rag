from __future__ import annotations

import json
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.schemas.agent_task_case import AgentTaskCase
from app.schemas.evaluation_entities import EvaluationCase, EvaluationDataset


def shared_agent_task_dataset_dir() -> Path:
    """Return the Monorepo directory containing shared Agent task JSONL files."""

    repository_root = Path(__file__).resolve().parents[4]
    return repository_root / "shared" / "datasets" / "agent-tasks"


def load_agent_task_cases(dataset_dir: Path) -> list[AgentTaskCase]:
    """Load and validate all JSONL task cases from one dataset directory."""

    if not dataset_dir.is_dir():
        raise ValueError(
            f"Agent task dataset directory does not exist: {dataset_dir}"
        )

    cases: list[AgentTaskCase] = []
    known_case_ids: set[str] = set()

    for dataset_file in sorted(dataset_dir.glob("*.jsonl")):
        with dataset_file.open(encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                content = line.strip()
                if not content:
                    continue

                try:
                    payload = json.loads(content)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Invalid JSON in {dataset_file.name} "
                        f"at line {line_number}"
                    ) from exc

                try:
                    task_case = AgentTaskCase.model_validate(payload)
                except ValidationError as exc:
                    raise ValueError(
                        f"Invalid task case in {dataset_file.name} "
                        f"at line {line_number}: {exc}"
                    ) from exc

                if task_case.case_id in known_case_ids:
                    raise ValueError(
                        f"Duplicate Agent task case_id: {task_case.case_id!r}"
                    )

                known_case_ids.add(task_case.case_id)
                cases.append(task_case)

    if not cases:
        raise ValueError(
            f"No Agent task cases found in dataset directory: {dataset_dir}"
        )

    return cases


def _load_jsonl_task_cases(
    dataset_file: Path,
) -> list[AgentTaskCase]:
    """Load and validate Agent task cases from one JSONL file."""

    task_cases: list[AgentTaskCase] = []
    known_case_ids: set[str] = set()

    with dataset_file.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            content = line.strip()
            if not content:
                continue

            try:
                payload = json.loads(content)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON in {dataset_file.name} "
                    f"at line {line_number}"
                ) from exc

            task_case = _validate_task_case(
                payload=payload,
                source_name=dataset_file.name,
                location=f"line {line_number}",
            )

            if task_case.case_id in known_case_ids:
                raise ValueError(
                    f"Duplicate Agent task case_id: {task_case.case_id!r}"
                )

            known_case_ids.add(task_case.case_id)
            task_cases.append(task_case)

    if not task_cases:
        raise ValueError(
            f"No Agent task cases found in dataset file: {dataset_file}"
        )

    return task_cases


def _load_yaml_task_cases(
    dataset_file: Path,
) -> tuple[list[AgentTaskCase], str]:
    """Load and validate Agent task cases from one YAML file."""

    with dataset_file.open(encoding="utf-8") as file:
        payload = yaml.safe_load(file)

    if not isinstance(payload, dict):
        raise TypeError(
            f"YAML evaluation dataset must be an object: {dataset_file}"
        )

    version = payload.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError(
            f"YAML evaluation dataset requires a non-empty version: "
            f"{dataset_file}"
        )

    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError(
            f"YAML evaluation dataset requires a non-empty cases list: "
            f"{dataset_file}"
        )

    task_cases: list[AgentTaskCase] = []
    known_case_ids: set[str] = set()

    for index, raw_case in enumerate(raw_cases, start=1):
        task_case = _validate_task_case(
            payload=raw_case,
            source_name=dataset_file.name,
            location=f"case #{index}",
        )

        if task_case.case_id in known_case_ids:
            raise ValueError(
                f"Duplicate Agent task case_id: {task_case.case_id!r}"
            )

        known_case_ids.add(task_case.case_id)
        task_cases.append(task_case)

    return task_cases, version


def _validate_task_case(
    payload: object,
    source_name: str,
    location: str,
) -> AgentTaskCase:
    """Validate one raw task payload as an AgentTaskCase."""

    if not isinstance(payload, dict):
        raise TypeError(
            f"Task case in {source_name} at {location} must be an object"
        )

    try:
        return AgentTaskCase.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(
            f"Invalid task case in {source_name} at {location}: {exc}"
        ) from exc


def load_evaluation_dataset(
    dataset_file: Path,
) -> tuple[EvaluationDataset, list[EvaluationCase]]:
    """Load one JSONL or YAML file as an evaluation dataset."""

    if not dataset_file.is_file():
        raise ValueError(
            f"Evaluation dataset file does not exist: {dataset_file}"
        )

    suffix = dataset_file.suffix.lower()

    if suffix == ".jsonl":
        task_cases = _load_jsonl_task_cases(dataset_file)
        version = "1"
    elif suffix in {".yaml", ".yml"}:
        task_cases, version = _load_yaml_task_cases(dataset_file)
    else:
        raise ValueError(
            f"Unsupported evaluation dataset format: {dataset_file.suffix}"
        )

    dataset = EvaluationDataset(
        name=dataset_file.stem,
        source_path=str(dataset_file),
        version=version,
    )

    cases = [
        EvaluationCase(
            dataset_id=dataset.dataset_id,
            task=task_case,
        )
        for task_case in task_cases
    ]

    return dataset, cases

def load_shared_agent_task_cases() -> list[AgentTaskCase]:
    """Load the Monorepo's shared Agent task dataset."""

    return load_agent_task_cases(shared_agent_task_dataset_dir())