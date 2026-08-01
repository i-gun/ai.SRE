# NewRelic APM Service to Azure DevOps Repository Mapping Report

**Analysis Date:** 2026-08-01  
**Services Analyzed:** 129 production services (CoStar Digital property commerce platform)  
**Repositories Scanned:** 278 repositories across 15 projects  
**Report Generated:** Generated automatically via service-to-repository mapping analysis

---

## Executive Summary

The service-to-repository mapping analysis achieved **40.3% direct coverage** across NewRelic APM services, with **56.5% internal coverage** when excluding external/managed services. This report provides strategic guidance on repository organization, service tracking, and deployment patterns.

### Key Findings

| Metric | Value | Status |
|--------|-------|--------|
| **Total Services** | 129 | - |
| **Matched Services** | 52 (40.3%) | ✓ Good starting point |
| **Unmatched Services** | 40 (31%) | ⚠ Requires action |
| **External/Managed** | 37 (28.7%) | ℹ External integrations |
| **Internal Coverage** | 56.5% | ✓ Acceptable |
| **Projects Scanned** | 15 | - |

---

## Service Classification Analysis

### Internal Services (92 total)
Services deployed and managed within the CoStar Digital platform infrastructure:
- **Matched (52):** Successfully mapped to Azure DevOps repositories
- **Unmatched (40):** Missing or unmapped repository references

### External/Managed Services (37 total)
Third-party and managed services that don't require repository mapping:
- NewRelic Databricks Integration
- Tibco, MAPI, NMAPI services
- RFID system services
- Autosearch integration services
- Atlas SAPI services
- OneTrust data handling services

---

## Repository Organization Patterns

### By Project (Top Coverage)

#### 1. **digital-ado-exp** (Experience Layer)
- **Repository Count:** 40+ mapped services
- **Primary Pattern:** `cds.*-experience-api` services
- **Technology:** Go (Golang), REST APIs
- **Branch Strategy:** Primarily `develop` branch (43 services)
- **Services Covered:**
  - Cart Experience API
  - Checkout/Order Experience API
  - Category Experience API
  - Store Experience API
  - Profile Experience API
  - And 35+ more experience layer services

#### 2. **digital-ado-mer** (Merchandise/DMS Layer)
- **Repository Count:** 7 repositories
- **Primary Pattern:** `cds.dms.*` services
- **Services Covered:**
  - DMS Availability (cache builder, cron API)
  - DMS Pricing (cache builder, cron API)
  - DMS Panda (product analysis, cron API)
  - DMS Rules Management & Rule Engine Merchandising

#### 3. **digital-ado-ful** (Fulfillment Layer)
- **Repository Count:** 4 repositories
- **Services Covered:**
  - Order Pickup Service
  - SCIM (customer identity management)
  - SFSC (Salesforce Commerce Cloud)
  - IOMS Schedulers

#### 4. **digital-ado-asm** (Search & Analytics)
- **Repository Count:** 1 primary repository
- **Services:** Digital ASM Runway CV

### Repository Name Patterns

| Pattern | Count | Examples |
|---------|-------|----------|
| **cds_services** | 19 | `cds.category-experience-api`, `cds.dms.*` |
| **api_services** | 10 | API-specific deployments |
| **dms_services** | 6 | Distributed Merchandise System |
| **integration_services** | 2 | External integrations |
| **platform_services** | 1 | Core platform |
| **experience_services** | 1 | Experience layer |

---

## Matched Services Breakdown

### High Confidence Matches (0.85-1.0)
Services with exact or near-exact repository mappings:

**Exact Matches (Confidence: 1.0)**
- `cds.category-experience-api-prod` → `cds.category-experience-api`
- `cds.dms.availability-prod` → `cds.dms.availability`
- And 5+ more exact matches

**High Similarity Matches (Confidence: 0.85-0.99)**
- `cds.cart-experience-api-prod` (0.864)
- `cds.chatbot-experience-api-prod` (0.851)
- `cds.authorization-experience-api-prod` (0.755)

### Medium Confidence Matches (0.6-0.84)
Services matched through token overlap and similarity:
- Primary matching strategy for composite service names
- Confidence range: 0.57-0.79
- Total: 40+ services

---

## Unmatched Services by Category

### CDS Services Without Repository Mapping (26 services)

**Core CDS Services Missing:**
- `cds.api.link-loyalty` - Loyalty card linking
- `cds.api.merge-loyalty-cards` - Loyalty consolidation
- `cds.api.shipping-address` - Shipping management
- `cds.dam.ai-asset-metadata-api` - Digital Asset Management AI
- `cds.dam.media-logic-engine-api` - Media processing
- `cds.dam.webhook-receiver-api` - DAM webhooks
- `cds.digital-ads-api` - Advertising platform
- `cds.digital-common-config-api` - Shared configuration
- `cds.digital-product-api` - Product catalog
- `cds.encoding-decoding-api` - Data encoding/decoding
- `cds.express.delivery-api` - Express delivery service
- `cds.global-configuration-api` - Global settings
- `cds.healthcheck-orchestration` - Health monitoring
- `cds.mle-ai.product-copy-api` - AI product descriptions
- `cds.notifications-sender-api` - Notification engine
- `cds.shared.ai-vector-search-api` - Vector search (AI)
- And 10 more CDS services

**Recommendation:** Create dedicated repositories for these CDS services in `digital-ado-exp` and relevant domain projects.

### Infrastructure/Legacy Services Without Mapping (11 services)

- `ai-conversation-orchestrator-api` - AI orchestration
- `aoa-prod-015-2ohl-costar-defender-func` - Defender integration
- `corp-prod-046-0jzv-cc-rg_prod` - Corp infrastructure
- `hos-prod` - Home & Outdoor Services
- `neodynamic-prod` - Neodynamic service
- `Prod-Corp-Inv-Cleaner-Gen2` - Inventory cleaning
- `Prod-Corp-Inv-Consumer-Gen2` - Inventory consumption
- `Prod-Corp-Inv-Supplier-Gen2` - Supplier inventory
- `Prod-Digital-Chit-Gateway-Gen2` - Digital gateway
- `Prod-Frontier-Loyalty-Self-Serv` - Frontier loyalty
- `redbox-prod` - Redbox integration

**Recommendation:** Review with infrastructure teams; some may be in different project structures or require consolidation.

### Legacy Platform Services (3 services)
- `P-DMT-FPPE` - Platform DMT services
- `P-DMT-MDTE` - Platform DMT services
- `P-DMT-MPPE` - Platform DMT services

**Recommendation:** Document migration path or consolidation plan.

---

## Technology Stack Insights

### Detected Tech Stack Patterns

| Language | Primary Services | Repository Count |
|----------|------------------|------------------|
| **Golang** | Experience layer APIs (`cds.*-experience-api`) | 40+ |
| Other patterns | Infrastructure, integration | Various |

**Observation:** Golang appears dominant in the experience/CDS layer, suggesting a microservices-first architecture using Go for API services.

### Branch Strategy

| Branch | Service Count | Typical Use |
|--------|---------------|-----------|
| **develop** | 43 | CI/CD pre-production deployments |
| **main** | 9 | Production deployments |

**Recommendation:** Establish clear merge gate policies for both branches; validate deployment automation.

---

## Organization Recommendations

### 🟥 HIGH PRIORITY

**1. Create 26 CDS Service Repositories**
- **Action:** Create dedicated repositories for unmatched CDS services
- **Projects:** Primarily `digital-ado-exp`, `digital-ado-mer`, `digital-ado-ful`
- **Timeline:** 1-2 sprints
- **Benefits:**
  - Complete service inventory coverage
  - Clearer deployment ownership
  - Better traceability in CI/CD pipelines
  
**Recommended Repository Structure:**
```
digital-ado-exp/
  - cds.api.link-loyalty
  - cds.api.merge-loyalty-cards
  - cds.api.shipping-address
  - cds.dam.ai-asset-metadata-api
  - cds.dam.media-logic-engine-api
  - cds.encoding-decoding-api
  - cds.digital-ads-api
  - [+ 18 more]

digital-ado-mer/
  - cds.dms.cache-builder
  - cds.dms.pcode-cache-builder
  - cds.dms.rule-engine-merchandising

digital-ado-ful/
  - [fulfillment-related CDS services]
```

### 🟨 MEDIUM PRIORITY

**1. Document External/Managed Service Integrations (37 services)**
- **Action:** Create service catalog documentation for all external integrations
- **Timeline:** 1-2 weeks
- **Deliverables:**
  - External service matrix (service name → provider → API endpoint)
  - Integration contact points and escalation paths
  - SLA/support documentation per external service
  
**External Services Requiring Documentation:**
- Databricks, OneTrust, Tibco, Autosearch, Atlas SAPI
- RFID systems and services
- MAPI/NMAPI legacy services

**2. Infrastructure Service Review (11 services)**
- **Action:** Audit legacy infrastructure services for consolidation/migration opportunities
- **Timeline:** 2-3 weeks
- **Questions to Answer:**
  - Are these services still in production?
  - Can they be consolidated into existing repositories?
  - Do they have separate compliance/security requirements?

**3. Repository Naming Consistency**
- **Current Issue:** Service names include environment suffixes (`-prod`, `-prd`) that differ from repo names
- **Action:** Establish naming convention standard that synchronizes NewRelic service names with repository names
- **Timeline:** Document standard now, enforce for new services

---

### 🟦 LOW PRIORITY

**1. Establish Service-to-Repository Mapping as CI/CD Artifact**
- **Action:** Integrate mapping generation into build/release pipeline
- **Timeline:** Next sprint
- **Benefits:**
  - Automatic sync between NewRelic services and repositories
  - Real-time visibility into deployment coverage
  - Early detection of deployment pattern drift

**2. Repository Tech Stack Standardization**
- **Current:** Golang dominant in experience APIs
- **Action:** Document recommended tech stacks per service layer
- **Timeline:** Documentation sprint

**3. Branch Strategy Audit**
- **Current:** Most services use `develop` branch, some use `main`
- **Action:** Audit and standardize branch protection rules, merge gates
- **Timeline:** Infrastructure team review

---

## Deployment Pattern Analysis

### Identified Patterns

#### Pattern 1: Experience Layer APIs (40+ services)
- **Repository:** `cds.category-experience-api` (central experience platform)
- **Branch:** `develop` (CI/CD deployments)
- **Services:** Cart, checkout, product, profile, store, category, etc.
- **Tech Stack:** Golang/Go
- **Deployment Model:** Likely monorepo or shared platform with feature branches

**Implications:**
- Multiple NewRelic services may deploy from single repository
- Unified experience platform with feature isolation
- Clear need for feature toggles/deployment controls

#### Pattern 2: Merchandise/DMS Services (6-7 repositories)
- **Repositories:** `cds.dms.availability`, `cds.dms.panda`, `cds.dms.pricing`
- **Branch:** `main` (stable production)
- **Services:** Cache builders, pricing engines, availability services
- **Deployment Model:** Service-per-repository (microservices)

**Implications:**
- Clear separation of concerns
- Dedicated deployment pipelines per service
- Better for independent scaling/updates

#### Pattern 3: Fulfillment Layer (4 repositories)
- **Repositories:** SCIM, SFSC, IOMS Schedulers, Order Pickup
- **Branch:** `main` (stable production)
- **Services:** Customer identity, order management
- **Deployment Model:** Service-per-repository

#### Pattern 4: External Integrations
- **Services:** Databricks, Tibco, RFID, Autosearch
- **Repositories:** Not tracked in Azure DevOps (external vendor systems)
- **Implication:** Requires separate integration documentation

---

## Coverage Analysis

### Completeness Assessment

**Overall Coverage:**
- ✓ 52 services matched (40.3%)
- ⚠ 40 services unmatched (31%)
- ℹ 37 external services (28.7%)

**Internal Service Coverage:**
- ✓ 52 of 92 internal services matched (56.5%)
- ⚠ 40 internal services without explicit repository mapping

**Recommendations:**
1. **Immediate (1-2 weeks):** Reconcile 40 unmatched internal services
2. **Short-term (1-2 sprints):** Create missing CDS repositories
3. **Ongoing:** Maintain mapping as part of deployment pipeline

---

## Project-Level Insights

### digital-ado-exp (Experience Layer)
- **Status:** ✓ Well-established, high coverage
- **Services:** 40+ matched (cart, checkout, category, product, profile, etc.)
- **Recommendation:** Continue pattern, add missing CDS services

### digital-ado-mer (Merchandise/DMS)
- **Status:** ✓ Solid coverage
- **Services:** 7 repositories (availability, pricing, panda, rules)
- **Recommendation:** Add cache builders and rule engine services

### digital-ado-ful (Fulfillment)
- **Status:** ✓ Good coverage
- **Services:** 4 repositories (SCIM, SFSC, IOMS, Order Pickup)
- **Recommendation:** Monitor for growth; add order-related CDS services

### digital-ado-asm (Search & Analytics)
- **Status:** ⚠ Minimal coverage
- **Services:** 1 repository mapped
- **Recommendation:** Review search-related CDS services; may need new repos

### Other Projects
- **digital-ado-001, digital-ado-aisc, digital-ado-aut, digital-ado-fin, digital-ado-loy, digital-ado-mkt, digital-ado-sch, digital-ado-shd, digital-ado-syn:** Limited direct service-to-repo mappings detected
- **Recommendation:** Audit these projects for service alignment

---

## Data Quality & Limitations

### Analysis Methodology
- **Matching Algorithm:** Multi-strategy pattern matching (exact, substring, token overlap, sequence similarity)
- **Confidence Scoring:** 0.0-1.0 scale based on match type and overlap percentage
- **Minimum Threshold:** 0.5 confidence for match acceptance

### Known Limitations
1. **Environment Suffix Handling:** Service names include `-prod`, `-prd` suffixes that are stripped for matching
2. **Monorepo vs Microrepo:** Some services may share repositories; matching shows primary/strongest match
3. **Renamed Services:** Services renamed in NewRelic but not updated in repository names
4. **External Services:** Deliberately excluded; not tracked in Azure DevOps
5. **Repository Size:** Size data not populated in current map (may indicate empty repos)

### Data Freshness
- **Repository Map Generated:** 2026-07-31 11:06:23 UTC
- **Services File:** Current as of analysis date
- **Recommendation:** Regenerate mapping monthly or on major deployment changes

---

## Next Steps & Action Items

### Week 1-2: Assessment & Planning
- [ ] Review HIGH PRIORITY recommendations with platform team
- [ ] Identify owners for each unmatched service category
- [ ] Create issue tracking for new CDS repositories

### Week 3-4: Repository Creation
- [ ] Create 26 missing CDS service repositories
- [ ] Set up branch protection rules (develop/main)
- [ ] Configure CI/CD pipeline hooks

### Month 2: Documentation & Automation
- [ ] Document external service integrations (37 services)
- [ ] Create service-to-repository mapping dashboard
- [ ] Integrate mapping generation into CI/CD

### Ongoing: Maintenance
- [ ] Monthly mapping refresh
- [ ] Quarterly coverage audits
- [ ] Update as new services added to production

---

## Appendices

### Appendix A: Exact Match Services (Confidence: 1.0)
```json
1. cds.category-experience-api-prod → cds.category-experience-api (digital-ado-exp)
2. cds.dms.availability-prod → cds.dms.availability (digital-ado-mer)
3. [Additional exact matches in detailed JSON output]
```

### Appendix B: Complete Service Listing
- See `azuregit_service_repository_map.json` for complete details including:
  - All 52 matched services with confidence scores
  - All 40 unmatched internal services with project inferences
  - All 37 external/managed services

### Appendix C: Repository Inventory by Project
- 15 projects scanned
- 278 total repositories
- 52 actively matched to NewRelic services

---

## Contact & Questions

For questions about this analysis or to request updates:
1. Review the detailed JSON output: `azuregit_service_repository_map.json`
2. Check the generated repository list: `azuregit_repo_map.json`
3. Refer to Azure DevOps organization: `cantire`

---

**Report Generated:** 2026-08-01 05:05:41 UTC  
**Analysis Tool:** NewRelic APM → Azure DevOps Service Repository Mapper  
**Status:** ✓ Complete  
