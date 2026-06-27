from app.services.common import metadata as metadata_utils


def test_metadata_merge_preserves_stable_unique_id_lists() -> None:
    merged = metadata_utils.merge_metadata(
        {"competitor_ids": ["a", "b"], "content_type": "text/html"},
        {"competitor_ids": ["b", "c"], "content_type": "application/pdf"},
    )

    assert merged["competitor_ids"] == ["a", "b", "c"]
    assert merged["content_type"] == "application/pdf"


def test_metadata_merge_skips_none_values_and_does_not_mutate_base() -> None:
    base = {"domain": "example.com", "discovered_source_ids": ["1"]}

    merged = metadata_utils.merge_metadata(
        base,
        {"domain": None, "discovered_source_ids": ["1", "2"]},
    )

    assert base == {"domain": "example.com", "discovered_source_ids": ["1"]}
    assert merged == {"domain": "example.com", "discovered_source_ids": ["1", "2"]}
