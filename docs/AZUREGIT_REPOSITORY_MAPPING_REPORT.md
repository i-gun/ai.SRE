# AzureGit Repository Mapping Report

> **Snapshot** — Run `python scripts/azuregit/fetch_repo_map.py --force-refresh` to regenerate locally.

## Snapshot Metadata

- Generated at (UTC): 2026-07-31T11:06:23.349715+00:00
- Azure DevOps organization: cantire
- Scoped projects: 15
- Total repositories: 278
- Repositories with null `defaultBranch`: 9
- Repositories with `size=0`: 16

## Repositories by Project

| Project | Repository Count |
|---|---:|
| digital-ado-sch | 50 |
| digital-ado-exp | 44 |
| digital-ado-shd | 33 |
| digital-ado-ful | 32 |
| digital-ado-mer | 25 |
| digital-ado-mkt | 22 |
| digital-ado-syn | 16 |
| digital-ado-loy | 13 |
| digital-ado-asm | 11 |
| digital-ado-aisc | 9 |
| corp-ado-046 | 7 |
| digital-ado-001 | 5 |
| digital-ado-aut | 5 |
| corp-ado-032 | 3 |
| digital-ado-fin | 3 |

## Default Branch Distribution

| Default Branch | Repository Count |
|---|---:|
| refs/heads/main | 167 |
| refs/heads/develop | 71 |
| refs/heads/master | 29 |
| `<none>` | 9 |
| refs/heads/collab | 1 |
| refs/heads/ecom/master | 1 |

## Top 15 Largest Repositories

| Project | Repository | Size | Default Branch |
|---|---|---:|---|
| digital-ado-mer | digital-mer-west-mdte | 293338329 | refs/heads/master |
| digital-ado-mer | digital-mer-west-mppe | 272958403 | refs/heads/master |
| digital-ado-mer | digital-mer-west-fppe | 267748161 | refs/heads/master |
| digital-ado-mer | digital-mer-west-inventory-service | 264383749 | refs/heads/master |
| digital-ado-ful | digital-ful-sfsc | 237275309 | refs/heads/develop |
| digital-ado-asm | digital-asm-runway-connector | 213303041 | refs/heads/develop |
| digital-ado-ful | digital-odp-sfsc-test | 208268604 | refs/heads/master |
| digital-ado-sch | digital-sch-atlas-auto | 184924025 | refs/heads/develop |
| digital-ado-sch | digital-sch-atlas-data-ingestion | 121790455 | refs/heads/develop |
| digital-ado-sch | digital-sch-atlas-search-api | 82063182 | refs/heads/develop |
| digital-ado-sch | digital-sch-atlas-admin-api | 64875577 | refs/heads/develop |
| digital-ado-sch | digital-sch-fisd-simple-search | 60390326 | refs/heads/master |
| digital-ado-sch | FISD-simple-search | 60390326 | refs/heads/master |
| digital-ado-asm | digital-asm-runway-cv | 54092000 | refs/heads/develop |
| digital-ado-exp | digital-exp-west-product-gw | 52237258 | refs/heads/master |

## Null Default Branch by Project

| Project | Null `defaultBranch` Count |
|---|---:|
| digital-ado-asm | 3 |
| digital-ado-mer | 1 |
| digital-ado-shd | 3 |
| digital-ado-syn | 2 |

## Refresh Procedure

Always refresh mapping before sharing scoped project/repository inventory:

```bash
python scripts/azuregit/fetch_repo_map.py --force-refresh
```

Use cache-aware refresh when full API refresh is not required:

```bash
python scripts/azuregit/fetch_repo_map.py --max-age-hours 6
```
