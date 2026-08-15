from __future__ import annotations

import json
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
                f"Evaluation run artifact not found: {target_path}"
            )

        payload = json.loads(
            target_path.read_text(encoding="utf-8"),
        )

        return EvaluationRunArtifact.model_validate(payload)