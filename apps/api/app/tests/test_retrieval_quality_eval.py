from app.core.config import get_settings
from app.services.retrieval_quality_eval_service import run_golden_retrieval_eval


def test_golden_retrieval_eval_runs_without_provider_credentials() -> None:
    report = run_golden_retrieval_eval(get_settings())

    assert report["passed"] is True
    assert report["score"] == report["total"]
    metric_keys = {metric["key"] for metric in report["metrics"]}
    assert {
        "positive_above_negative",
        "source_diversity",
        "duplicate_deduped",
        "competitor_coverage",
        "citation_supported",
        "prompt_injection_filtered",
        "stale_source_detected",
    } <= metric_keys
    assert report["retrieval_metrics"]["precision_at_k"] > 0
    assert report["retrieval_metrics"]["unsupported_claim_rate"] > 0
