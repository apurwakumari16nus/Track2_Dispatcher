"""Earliest-finish baseline for comparison with objective-driven allocation."""

from simulate import eligible_workshops


def earliest_finish(batch, workshops, queues):
    """Choose the fastest eligible shop; input order resolves exact ties."""
    eligible = eligible_workshops(batch, workshops)
    if not eligible:
        raise ValueError("No eligible workshop; escalate the batch")
    return min(
        eligible,
        key=lambda w: queues[w.workshop_id] + batch["pieces"] / w.capacity + w.lead_days,
    ).workshop_id
