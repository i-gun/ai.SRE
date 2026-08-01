# Combined Service/Repository Mapping Report

Status: APPROVED

Generated at (UTC): 2026-08-01T08:09:10.736435+00:00

## Source Inputs
- Services list: `data/newrelic_apm_service_names_1679802.txt`
- AzureGit map: `artifacts/azuregit_service_repository_map.json`
- Confluence map: `artifacts/confluence_service_knowledge_map.json`
- Jira signal: Jira subagent (label-focused run)

## Combined Totals
- Services analyzed: 129
- Mapped (single+): 52
- Mapped (multi-signal): 2
- Documentation-only: 3
- Unmapped: 74

## Jira Label Signal Metrics
- total_jira_issues_scanned: 1808
- issues_with_labels: 1808
- total_mapping_candidates: 0
- high_confidence_candidates: 0
- unique_services_covered: 0

## Top Mapped Candidates (first 20)

| Service | Repository | Project | Confidence | Signals |
|---|---|---|---:|---:|
| cds.category-experience-api-prod | cds.category-experience-api | digital-ado-exp | 0.750 | 1 |
| cds.dms.availability-prod | cds.dms.availability | digital-ado-mer | 0.750 | 1 |
| cds.dms.panda-prod | cds.dms.panda | digital-ado-mer | 0.750 | 1 |
| cds.dms.pricing-prod | cds.dms.pricing | digital-ado-mer | 0.750 | 1 |
| digital-asm-runway-cv-prod | digital-asm-runway-cv | digital-ado-asm | 0.750 | 1 |
| cds.store-experience-api-prod | cds.category-experience-api | digital-ado-exp | 0.713 | 2 |
| ioms-prod | digital-ful-ioms-schedulers-func | digital-ado-ful | 0.712 | 1 |
| scim-prod | digital-ful-scim | digital-ado-ful | 0.712 | 1 |
| sfsc-prod | digital-ful-sfsc | digital-ado-ful | 0.712 | 1 |
| cds.cart-experience-api-prod | cds.category-experience-api | digital-ado-exp | 0.648 | 1 |
| cds.chatbot-experience-api-prod | cds.category-experience-api | digital-ado-exp | 0.638 | 1 |
| cds.weather-experience-api-prod | cds.category-experience-api | digital-ado-exp | 0.638 | 1 |
| cds.dms.availability-cron-api-prod | cds.dms.availability | digital-ado-mer | 0.628 | 1 |
| cds.digital-store-api-prod | digital-gcp-gmb-store-hours-api | digital-ado-exp | 0.614 | 2 |
| cds.asset-experience-api-prod | cds.category-experience-api | digital-ado-exp | 0.600 | 1 |
| cds.order-experience-api-prod | cds.category-experience-api | digital-ado-exp | 0.600 | 1 |
| cds.tire-vendor-experience-api-prod | cds.category-experience-api | digital-ado-exp | 0.600 | 1 |
| cds.ads-experience-api-prod | cds.category-experience-api | digital-ado-exp | 0.593 | 1 |
| cds.esl-experience-api-prod | cds.category-experience-api | digital-ado-exp | 0.593 | 1 |
| cds.pep-experience-api-prod | cds.category-experience-api | digital-ado-exp | 0.593 | 1 |

## Unmapped Services (first 30)
- ai-conversation-orchestrator-api-prd
- aoa-prod-015-2ohl-costar-defender-func
- cds.api.link-loyalty-prod
- cds.api.merge-loyalty-cards-prod
- cds.api.shipping-address-prod
- cds.contact-us-api-prod
- cds.dam.ai-asset-metadata-api-prod
- cds.dam.media-logic-engine-api-prod
- cds.dam.webhook-receiver-api-prod
- cds.dam.webhook-updates-processor-wmc-prod
- cds.digital-ads-api-prod
- cds.digital-common-config-api-prod
- cds.digital-product-api-prod
- cds.dms.cache-builder-prod
- cds.dms.pcode-cache-builder-prod
- cds.dms.rule-engine-merchandising-cron-api-prod
- cds.dms.rule-engine-merchandising-prod
- cds.encoding-decoding-api-prod
- cds.exp.scan-buy-api-prod
- cds.express.delivery-api-prod
- cds.global-configuration-api-prod
- cds.healthcheck-orchestration-prod
- cds.merge-loyalty-cards-experience-api-prod
- cds.mle-ai.product-copy-api-prod
- cds.notifications-sender-api-prod
- cds.notifications-sender-exp-api-prod
- cds.onetrust.historical-data-cron-api-prod
- cds.shared.ai-vector-search-api-prod
- cds.shipping-address-exp-api-prod
- corp-prod-046-0jzv-cc-rg_prod

## Governance
This report is approved and promoted as a canonical combined mapping snapshot.
