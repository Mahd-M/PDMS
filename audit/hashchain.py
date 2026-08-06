"""
Tamper-evident hash chaining.

Every row that needs an immutable trail (audit events, evidence
custody entries) stores the SHA-256 hash of the *previous* row's
hash plus its own content. Altering or deleting any past row breaks
every hash after it, so tampering is detectable by walking the chain
and recomputing -- the same integrity idea a blockchain uses, without
needing a blockchain.

This module has no Django model dependency so it can be reused by
any app that needs an append-only, verifiable log.
"""
import hashlib


GENESIS_HASH = "0" * 64  # the "previous hash" for the very first row in a chain


def compute_row_hash(prev_hash: str, *fields: str) -> str:
    """
    Compute this row's hash from the previous row's hash and this
    row's own content fields (already stringified by the caller).
    """
    payload = prev_hash + "|" + "|".join(fields)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_chain(rows, field_extractor) -> tuple[bool, int | None]:
    """
    Walk a chain in order and confirm each row's stored hash matches
    a fresh recomputation. `rows` must be ordered oldest-first.
    `field_extractor(row)` returns the tuple of content fields used
    when the row's hash was first computed.

    Returns (True, None) if the chain is intact, or
    (False, row_id) for the first row that fails verification.
    """
    prev_hash = GENESIS_HASH
    for row in rows:
        expected = compute_row_hash(prev_hash, *field_extractor(row))
        if expected != row.row_hash:
            return False, row.pk
        prev_hash = row.row_hash
    return True, None
