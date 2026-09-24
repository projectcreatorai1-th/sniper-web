# SECURITY + SUPPLY CHAIN REPORT (§35-§37)

2026-09-25T03:31:14

## Secrets scan
- patterns: api_key / password / token / private key across source,
  config, logs, docs, artifacts
- result: CLEAN
- redaction policy: secrets are never written by the system (no
  credential fields exist in OUR EA config; broker connection data is
  supplied by the environment at demo time, never committed)

## SBOM
```json
{
 "schema": "CycloneDX-like minimal SBOM (hand-built, stdlib only)",
 "generated": "2026-09-25T03:31:14",
 "components": [
  {
   "name": "python",
   "version": "3.12.10",
   "scope": "runtime",
   "license": "PSF"
  },
  {
   "name": "openpyxl",
   "version": "3.1.5",
   "scope": "analysis-only (Analyzer + validator)",
   "license": "MIT"
  }
 ],
 "frontend": [
  {
   "name": "vanilla-js-spa",
   "version": "n/a",
   "dependencies": []
  }
 ],
 "notes": "OUR EA runtime (core/our_ea/**) is pure Python stdlib; no third-party imports; JS has zero dependencies",
 "vulnerability_check": "no third-party runtime deps -> no known CVE surface in OUR EA runtime"
}
```

## Build provenance
```json
{
 "schema": "BUILD_PROVENANCE_V1",
 "source_commit": "42bc65e8aac0068e938a70863d9f971d9969c236",
 "build_environment": {
  "python": "3.12.10",
  "os": "Windows-10-10.0.19045-SP0",
  "machine": "AMD64"
 },
 "dependencies": [
  {
   "name": "python",
   "version": "3.12.10",
   "scope": "runtime",
   "license": "PSF"
  },
  {
   "name": "openpyxl",
   "version": "3.1.5",
   "scope": "analysis-only (Analyzer + validator)",
   "license": "MIT"
  }
 ],
 "config": "OUR_EA_CONFIG_V1",
 "artifacts": {},
 "build_timestamp": "2026-09-25T03:31:14",
 "reproducibility": "pure-stdlib; replay determinism proven by identical result_hash across runs"
}
```
