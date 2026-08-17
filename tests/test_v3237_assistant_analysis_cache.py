from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


def test_analysis_cache_reuses_context_and_returns_isolated_copies():
    from assistant_analysis_cache import AssistantAnalysisCache

    calls = []

    def builder(*, year=None):
        calls.append(year)
        return {"year": year, "months": [{"month": f"{year}_08", "metrics": {"gas_m3": 12.3}}]}

    cache = AssistantAnalysisCache(builder)
    first = cache.refresh(year=2026)
    second = cache.get(year=2026)
    second["months"][0]["metrics"]["gas_m3"] = 999
    third = cache.get(year=2026)

    assert calls == [2026]
    assert first["months"][0]["metrics"]["gas_m3"] == 12.3
    assert third["months"][0]["metrics"]["gas_m3"] == 12.3


def test_main_wires_full_analysis_cache_before_runtime_probe():
    source = (APP / "main.py").read_text(encoding="utf-8")
    assert "from assistant_analysis_cache import AssistantAnalysisCache" in source
    assert "ASSISTANT_ANALYSIS_CACHE = AssistantAnalysisCache(build_assistant_analysis_context)" in source
    assert "analysis_provider=get_assistant_analysis_context" in source
    assert "analysis_cache_prewarm = prewarm_assistant_analysis_cache()" in source
    quarter_pos = source.index("prewarm = prewarm_assistant_quarter_hour_cache()")
    analysis_pos = source.index("analysis_cache_prewarm = prewarm_assistant_analysis_cache()")
    probe_pos = source.index("result = run_assistant_runtime_probe(app_version=APP_VERSION)")
    assert quarter_pos < analysis_pos < probe_pos
