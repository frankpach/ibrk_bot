from pathlib import Path


def _parse_requirements() -> dict[str, str]:
    requirements = {}
    for raw_line in Path("requirements.txt").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        name, version = line.split("==", 1)
        requirements[name] = version
    return requirements


def test_python_telegram_bot_major_matches_apscheduler_dependency():
    requirements = _parse_requirements()

    assert requirements["APScheduler"].startswith("3.11.")
    assert int(requirements["python-telegram-bot"].split(".", 1)[0]) >= 20
