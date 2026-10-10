"""Content identities of recomputed research, never acceptance or authority."""

from auto_invest.market_data.intraday import digest, encode


def archive_input_identity(provider, synthetic, adjustment_policy, lineage):
    """Caller has verified each immutable source/manifest, CSV, and session.

    Source retrieval times remain bound by their original raw/manifest hashes.
    The generated combined manifest remains an artifact, not the input identity.
    """
    return dict(schema=1, scope="intraday-archive-input-v1", provider=provider,
                synthetic=synthetic, adjustment_policy=adjustment_policy, archives=lineage)


def research_content_digest(report):
    """Exclude only report generation time; bind every other computed field.

    New scope deliberately differs from the old whole-report byte digest. Old
    registrations are not re-signed or upgraded by this pure function.
    """
    if not isinstance(report, dict):
        raise ValueError("RESEARCH_CONTENT_INVALID")
    content = {key: value for key, value in report.items() if key != "generated_at_utc"}
    return digest(encode(dict(schema=1, scope="intraday-research-content-v1", report=content)))
