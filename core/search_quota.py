"""Daily search API quota manager."""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class QuotaStatus:
    """Current quota status for a provider."""
    used: int = 0
    limit: int = 0
    reset_at: str = ""
    remaining: int = 0


class SearchQuotaManager:
    """
    Daily search API quota manager.
    
    Tracks daily usage per provider and enforces limits.
    Usage is persisted to a JSON file and resets at configured hour (default: midnight UTC).
    """
    
    def __init__(self, quota_file: str = "knowledge/search_quota.json"):
        self._quota_file = Path(quota_file)
        self._lock = threading.Lock()
        self._daily_usage: dict[str, dict] = {}
        self._load()
    
    def _load(self):
        """Load quota state from file."""
        if self._quota_file.exists():
            try:
                with open(self._quota_file, "r") as f:
                    self._daily_usage = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._daily_usage = {}
        self._cleanup_old_days()
    
    def _save(self):
        """Save quota state to file."""
        try:
            with open(self._quota_file, "w") as f:
                json.dump(self._daily_usage, f, indent=2)
        except IOError:
            pass
    
    def _cleanup_old_days(self):
        """Remove entries for days that have passed their reset time."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._daily_usage = {
            k: v for k, v in self._daily_usage.items()
            if v.get("date") == today
        }
    
    def _get_today_key(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    def check_quota(self, provider: str, limit: int, enabled: bool = True) -> tuple[bool, QuotaStatus]:
        """
        Check if a request is allowed under the quota.
        
        Returns:
            (allowed, status) - allowed is True if request is within quota
        """
        if not enabled:
            return True, QuotaStatus(used=0, limit=limit, remaining=limit)
        
        with self._lock:
            today = self._get_today_key()
            key = f"{provider}_{today}"
            
            if key not in self._daily_usage:
                self._daily_usage[key] = {"date": today, "used": 0}
            
            entry = self._daily_usage[key]
            used = entry.get("used", 0)
            remaining = max(0, limit - used)
            
            status = QuotaStatus(
                used=used,
                limit=limit,
                remaining=remaining
            )
            
            if used >= limit:
                return False, status
            
            return True, status
    
    def record_usage(self, provider: str, count: int = 1):
        """Record API usage for a provider."""
        with self._lock:
            today = self._get_today_key()
            key = f"{provider}_{today}"
            
            if key not in self._daily_usage:
                self._daily_usage[key] = {"date": today, "used": 0}
            
            self._daily_usage[key]["used"] = self._daily_usage[key].get("used", 0) + count
            self._save()
    
    def get_status(self, provider: str, limit: int, enabled: bool = True) -> QuotaStatus:
        """Get current quota status for a provider."""
        if not enabled:
            return QuotaStatus(used=0, limit=limit, remaining=limit)
        
        with self._lock:
            today = self._get_today_key()
            key = f"{provider}_{today}"
            
            if key not in self._daily_usage:
                return QuotaStatus(used=0, limit=limit, remaining=limit)
            
            used = self._daily_usage[key].get("used", 0)
            return QuotaStatus(
                used=used,
                limit=limit,
                remaining=max(0, limit - used)
            )
    
    def reset(self, provider: str | None = None):
        """Reset quota for a specific provider or all providers."""
        with self._lock:
            if provider:
                key_prefix = f"{provider}_"
                self._daily_usage = {
                    k: v for k, v in self._daily_usage.items()
                    if not k.startswith(key_prefix)
                }
            else:
                self._daily_usage = {}
            self._save()


# Global singleton instance
_quota_manager: SearchQuotaManager | None = None


def get_quota_manager() -> SearchQuotaManager:
    global _quota_manager
    if _quota_manager is None:
        _quota_manager = SearchQuotaManager()
    return _quota_manager
