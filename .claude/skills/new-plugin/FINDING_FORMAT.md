# Finding Format

Every `run_scan()` must return a list of dicts matching this exact schema.

```python
{
    "platform":       str,   # plugin name, e.g. "aws", "sonarqube"
    "resource":       str,   # unique resource identifier, e.g. "s3://my-bucket"
    "severity":       str,   # one of: CRITICAL | HIGH | MEDIUM | LOW | INFO
    "category":       str,   # one of: security | cost | reliability | performance | compliance
    "finding":        str,   # short human-readable description of the issue
    "recommendation": str,   # actionable fix
    "evidence":       dict,  # raw API response data supporting the finding
}
```

## Severity guidance

| Severity | When to use |
|----------|-------------|
| CRITICAL | Public exposure, leaked credentials, data at risk right now |
| HIGH     | Misconfiguration that can be exploited with low effort |
| MEDIUM   | Best-practice violation with moderate risk |
| LOW      | Minor drift, non-urgent improvement |
| INFO     | Informational observation, no risk implied |

## Category guidance

| Category    | Examples |
|-------------|----------|
| security    | public buckets, open ports, unencrypted storage, IAM over-privilege |
| cost        | idle resources, over-provisioned instances, orphaned volumes |
| reliability | single-AZ deployments, missing health checks, no backups |
| performance | CPU/memory saturation, missing CDN, unindexed queries |
| compliance  | missing tags, audit log gaps, policy violations |
