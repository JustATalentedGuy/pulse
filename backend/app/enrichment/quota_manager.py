import errno
import json
import os
import threading
from datetime import date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import Settings, get_settings
from app.models.groq_quota import GroqQuotaUsage


class QuotaManager:
    def __init__(self, path: Path, daily_limit: int):
        self.path = path
        self.daily_limit = daily_limit
        self._lock = threading.Lock()

    def get_usage(self) -> int:
        with self._lock:
            return self._read_usage()

    def is_available(self) -> bool:
        with self._lock:
            return self._read_usage() < self.daily_limit

    def reserve(self) -> bool:
        with self._lock:
            count = self._read_usage()
            if count >= self.daily_limit:
                return False
            self._write_state({"date": date.today().isoformat(), "count": count + 1})
            return True

    def _read_usage(self) -> int:
        if not self.path.exists():
            return 0
        try:
            state: Any = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        if not isinstance(state, dict):
            return 0
        if state.get("date") != date.today().isoformat():
            return 0
        count = state.get("count", 0)
        return count if isinstance(count, int) and count >= 0 else 0

    def _write_state(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(state), encoding="utf-8")
        try:
            os.replace(temporary, self.path)
        except OSError as exc:
            if exc.errno != errno.EBUSY:
                raise
            # A directly bind-mounted Docker file cannot be replaced.
            # The process lock still serializes this fallback write.
            self.path.write_text(json.dumps(state), encoding="utf-8")
            temporary.unlink(missing_ok=True)


def _quota_date(settings: Settings) -> date:
    from datetime import datetime

    return datetime.now(ZoneInfo(settings.scheduler_timezone)).date()


async def get_quota_usage(
    manager: QuotaManager | None = None,
    settings: Settings | None = None,
) -> int:
    if manager is not None:
        return manager.get_usage()
    current_settings = settings or get_settings()
    if current_settings.groq_quota_backend != "database":
        from app.enrichment.worker import build_quota_manager

        return build_quota_manager(current_settings).get_usage()

    from app.database import SessionLocal

    async with SessionLocal() as session:
        count = await session.scalar(
            select(GroqQuotaUsage.request_count).where(
                GroqQuotaUsage.usage_date == _quota_date(current_settings)
            )
        )
    return count or 0


async def quota_is_available(
    manager: QuotaManager | None = None,
    settings: Settings | None = None,
) -> bool:
    current_settings = settings or get_settings()
    return (
        await get_quota_usage(manager=manager, settings=current_settings)
        < current_settings.groq_daily_limit
    )


async def reserve_quota(
    manager: QuotaManager | None = None,
    settings: Settings | None = None,
) -> bool:
    if manager is not None:
        return manager.reserve()
    current_settings = settings or get_settings()
    if current_settings.groq_quota_backend != "database":
        from app.enrichment.worker import build_quota_manager

        return build_quota_manager(current_settings).reserve()
    if current_settings.groq_daily_limit <= 0:
        return False

    from app.database import SessionLocal

    usage_date = _quota_date(current_settings)
    async with SessionLocal() as session:
        statement = (
            insert(GroqQuotaUsage)
            .values(usage_date=usage_date, request_count=1)
            .on_conflict_do_update(
                index_elements=[GroqQuotaUsage.usage_date],
                set_={
                    "request_count": GroqQuotaUsage.request_count + 1,
                },
                where=(
                    GroqQuotaUsage.request_count
                    < current_settings.groq_daily_limit
                ),
            )
            .returning(GroqQuotaUsage.request_count)
        )
        count = (await session.execute(statement)).scalar_one_or_none()
        await session.commit()
    return count is not None
