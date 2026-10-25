"""Included ChatGPT usage only. No setting, alias or key authorizes API spend.

Quota snapshots are admission evidence, not a provider-side hard spending cap.
Never buy credits, consume reset credits or infer allowance from a credit balance.
"""

ALLOWED_BACKENDS = frozenset({'codex-cli', 'codex-app-server'})
CODEX_OVERRIDES = ('forced_login_method="chatgpt"', 'model_provider="openai"', 'service_tier="default"')
API_ENV_KEYS = frozenset({'OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENROUTER_API_KEY',
                          'ANTHROPIC_API_KEY', 'JARVIS_DEEPAGENTS_API_KEY'})
ROUTE_ENV_KEYS = frozenset({'OPENAI_BASE_URL'})
QUOTA_PERCENT = 100
ERROR_MESSAGES = {
    'subscription_required': 'JARVIS uses your signed-in ChatGPT account only. Sign in with ChatGPT through Codex to continue; paid API providers are disabled.',
    'quota_exhausted': 'Your included Codex allowance is unavailable or exhausted. Wait for it to reset; JARVIS will not switch to a paid provider or buy credits.',
    'usage_unavailable': 'JARVIS could not verify your included Codex allowance. Try again when account usage is available; no paid fallback was attempted.',
}


class UsagePolicyError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(ERROR_MESSAGES[code])


def require_backend(backend):
    if backend not in ALLOWED_BACKENDS:
        raise UsagePolicyError('subscription_required')


def codex_environment(environment):
    return {key: value for key, value in environment.items() if key not in API_ENV_KEYS | ROUTE_ENV_KEYS}


def require_codex_config(config):
    if (not isinstance(config, dict) or config.get('forced_login_method') != 'chatgpt'
            or config.get('model_provider') != 'openai' or config.get('service_tier') != 'default'
            or not isinstance(config.get('model_providers') or {}, dict)
            or (config.get('model_providers') or {}).get('openai')):
        raise UsagePolicyError('subscription_required')


def quota_blocked(bucket):
    """Sparse notifications can revoke admission, but cannot establish recovery."""
    if not isinstance(bucket, dict):
        return False
    if bucket.get('rateLimitReachedType') or bucket.get('spendControlReached') is True:
        return True
    return any(isinstance(bucket.get(name), dict)
               and type(bucket[name].get('usedPercent')) is int
               and bucket[name]['usedPercent'] >= QUOTA_PERCENT for name in ('primary', 'secondary'))


def require_included_usage(snapshot):
    if not isinstance(snapshot, dict):
        raise UsagePolicyError('usage_unavailable')
    if snapshot.get('ordinaryUsageAllowed') is False:
        raise UsagePolicyError('quota_exhausted')
    # The installed protocol explicitly says null is unknown. A low percentage,
    # an elapsed reset timestamp, or remaining credits cannot restore permission.
    if snapshot.get('ordinaryUsageAllowed') is not True:
        raise UsagePolicyError('usage_unavailable')
    buckets = snapshot.get('rateLimitsByLimitId')
    bucket = buckets.get('codex') if isinstance(buckets, dict) else None
    if bucket is None:
        bucket = snapshot.get('rateLimits')
    if not isinstance(bucket, dict):
        raise UsagePolicyError('usage_unavailable')
    if quota_blocked(bucket):
        raise UsagePolicyError('quota_exhausted')
    windows = [bucket[name] for name in ('primary', 'secondary') if bucket.get(name) is not None]
    if not windows or any(not isinstance(window, dict)
                          or type(window.get('usedPercent')) is not int
                          or not 0 <= window['usedPercent'] < QUOTA_PERCENT for window in windows):
        raise UsagePolicyError('usage_unavailable')
    return {'mode': 'chatgpt-included', 'included_usage_allowed': True, 'paid_api_allowed': False}
