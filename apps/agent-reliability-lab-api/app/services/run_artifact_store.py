from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from app.schemas.evaluation_entities import EvaluationRunArtifact


class EvaluationRunArtifactStore:
    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def save(self, artifact: EvaluationRunArtifact) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)

        run_id = artifact.evaluation_run.evaluation_run_id
        target_path = self._output_dir / f"{run_id}.json"
        temporary_path = self._output_dir / f"{run_id}.tmp"

        payload = artifact.model_dump(mode="json")
        temporary_path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary_path.replace(target_path)

        return target_path

    def load(self, evaluation_run_id: UUID) -> EvaluationRunArtifact:
        target_path = self._output_dir / f"{evaluation_run_id}.json"

        if not target_path.is_file():
            raise FileNotFoundError(
                f"Evaluation run artifact not found: {target_path}",
            )

        payload = json.loads(
            target_path.read_text(encoding="utf-8"),
        )

        return EvaluationRunArtifact.model_validate(payload)

    def list_runs(self) -> list[EvaluationRunArtifact]:
        """Load all saved evaluation artifacts, newest completed run first."""

        if not self._output_dir.is_dir():
            return []

        artifacts = [
            self._load_path(path)
            for path in self._output_dir.glob("*.json")
        ]

        return sorted(
            artifacts,
            key=self._artifact_sort_key,
            reverse=True,
        )

    def _load_path(self, artifact_path: Path) -> EvaluationRunArtifact:
        payload = json.loads(
            artifact_path.read_text(encoding="utf-8"),
        )

        return EvaluationRunArtifact.model_validate(payload)

    @staticmethod
    def _artifact_sort_key(
        artifact: EvaluationRunArtifact,
    ) -> datetime:
        evaluation_run = artifact.evaluation_run
        timestamp = (
            evaluation_run.completed_at
            or evaluation_run.started_at
        )

        if timestamp is None:
            return datetime.min.replace(tzinfo=UTC)

        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)

        return timestamp