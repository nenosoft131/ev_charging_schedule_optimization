from datetime import datetime


class TimeFormatter:
    """Timestamp formatting helpers."""

    @staticmethod
    def iso_z(ts: datetime) -> str:
        """ISO 8601 string with Z suffix when timestamp is naive or UTC."""
        s = ts.isoformat()
        if s.endswith("+00:00"):
            return s[:-6] + "Z"
        if s.endswith("Z") or "+" in s[10:] or s[10:].count("-") > 0:
            return s
        return s + "Z"
