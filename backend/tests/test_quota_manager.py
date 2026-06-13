import errno
import json
from datetime import date, timedelta

from app.enrichment.quota_manager import QuotaManager


def test_quota_is_persistent_and_resets_by_date(tmp_path) -> None:
    path = tmp_path / "quota.json"
    manager = QuotaManager(path=path, daily_limit=2)

    assert manager.reserve()
    assert QuotaManager(path=path, daily_limit=2).get_usage() == 1
    assert manager.reserve()
    assert not manager.reserve()

    path.write_text(
        json.dumps(
            {
                "date": (date.today() - timedelta(days=1)).isoformat(),
                "count": 200,
            }
        ),
        encoding="utf-8",
    )
    assert manager.get_usage() == 0
    assert manager.reserve()


def test_bind_mounted_file_falls_back_to_in_place_write(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "quota.json"
    manager = QuotaManager(path=path, daily_limit=2)

    def busy_replace(source, destination):
        raise OSError(errno.EBUSY, "Device or resource busy")

    monkeypatch.setattr("app.enrichment.quota_manager.os.replace", busy_replace)

    assert manager.reserve()
    assert manager.get_usage() == 1
    assert not path.with_suffix(".json.tmp").exists()
