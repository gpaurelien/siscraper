import json
import logging
import typing as t
from datetime import datetime
from pathlib import Path

from summer_internships_scraper.models.offers import JobOffer

logger = logging.getLogger(__name__)


class JobRepository:
    def __init__(
        self, storage_path: str = "data/jobs.json", logger: logging.Logger = logger
    ) -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_storage_exists()
        self.logger = logger

    def _ensure_storage_exists(self):
        if not self.storage_path.exists():
            self.storage_path.write_text("{}")

    def _load_jobs(self) -> dict:
        try:
            return json.loads(self.storage_path.read_text())
        except json.JSONDecodeError:
            self.logger.error("Corrupted storage file")
            return {}

    def _save_jobs(self, jobs: dict):
        self.storage_path.write_text(json.dumps(jobs, indent=2))

    def add_jobs(self, jobs: t.List[JobOffer]) -> t.Tuple[int, int]:
        """Add new jobs to storage, avoiding duplicates based on their hashes."""
        storage = self._load_jobs()

        new_jobs = 0
        for job in jobs:
            job_hash = job.get_hash()
            if job_hash not in storage:
                storage[job_hash] = job.to()
                storage[job_hash]["first_seen"] = datetime.now().isoformat()
                new_jobs += 1

        self._save_jobs(storage)

        return new_jobs, len(storage)

    def get_all_jobs(self) -> t.List[dict]:
        return list(self._load_jobs().values())

    def get_recent_jobs(self, days: int = 7) -> t.List[dict]:
        storage = self._load_jobs()
        cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)

        recent_jobs = []
        for job in storage.values():
            first_seen = datetime.fromisoformat(job["first_seen"]).timestamp()
            if first_seen >= cutoff:
                recent_jobs.append(job)

        return recent_jobs

    def purge_outdated_jobs(self, max_age_days: int) -> int:
        """
        Remove jobs that are considered outdated from storage.

        A job is outdated if:
        - its ``posted_date`` (if present and parseable) is older than ``max_age_days``, or
        - otherwise, its ``first_seen`` is older than ``max_age_days``.
        """
        if max_age_days <= 0:
            return 0

        storage = self._load_jobs()
        if not storage:
            return 0

        cutoff = datetime.now().timestamp() - (max_age_days * 24 * 60 * 60)

        kept: dict = {}
        removed = 0

        for job_hash, job in storage.items():
            ts: float | None = None

            posted_date = job.get("posted_date")
            if isinstance(posted_date, str):
                try:
                    ts = datetime.fromisoformat(posted_date).timestamp()
                except ValueError:
                    ts = None

            if ts is None:
                try:
                    ts = datetime.fromisoformat(job["first_seen"]).timestamp()
                except Exception:
                    ts = None

            if ts is not None and ts < cutoff:
                self.logger.info(f"Deleting {job.title}, with ID: {job_hash}")
                removed += 1
                continue

            kept[job_hash] = job

        if removed:
            self._save_jobs(kept)

        return removed
