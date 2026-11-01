"""Small, framework-independent helpers for port congestion decisions."""


def counter_rate_bps(old_bytes, old_time, new_bytes, new_time):
    """Return counter delta in bits/s, or None for reset/invalid samples."""
    elapsed = new_time - old_time
    if elapsed <= 0 or new_bytes < old_bytes:
        return None
    return (new_bytes - old_bytes) * 8 / elapsed


def congestion_transition(is_congested, rate_bps, high_bps, low_bps):
    """Return 'congested', 'clear', or None using hysteresis thresholds."""
    if high_bps < low_bps:
        raise ValueError("high threshold must be >= low threshold")
    if not is_congested and rate_bps >= high_bps:
        return "congested"
    if is_congested and rate_bps < low_bps:
        return "clear"
    return None
