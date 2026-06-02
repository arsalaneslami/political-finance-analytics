# PFIN — Phase 0: Foundation & Infrastructure
## Project: Canadian Political Contributions Analytics Platform 
### Abbreviation: pfin
### Version: 1.0
### Date: May 2026
### Owner: Arsalan Eslami

## 1. Purpose and Scope
Phase 0 establishes everything required before any data engineering work begins. It covers Azure resource provisioning, Databricks workspace configuration, Unity Catalog setup, Entra ID security groups, Git repository initialization, compute setup, and resource tagging.
No Phase 1 work begins until all exit criteria in Section 11 are met.

## 2. Project Identity
FieldValueFull NameCanadian Political Contributions Analytics PlatformShort NamePolitical-FinanceAbbreviationpfinSource DataElections Canada — 3.6 GB CSV, all contributionsScope2025 and 2026 fiscal/election year records onlyOwnerArsalan EslamiAzure RegionCanada CentralGit Repositorypfin-analytics

## 3. Project Phase Overview
PhaseNameGoalPhase 0Foundation & InfrastructureAzure resources, Databricks, Unity Catalog, Git — all provisioned and validatedPhase 1Data Ingestion (Bronze)Extract 2025–2026 records from source CSV; load into Bronze Delta tablePhase 2Transformation (Silver)Type-cast, clean, deduplicate; produce normalized Silver domain tablesPhase 3Gold LayerBuild business aggregations (Gold tables) from SilverPhase 4Political Finance Analytics RulesDefine and encode domain-specific business rules (contribution limits, donor classification, party eligibility)Phase 5Dashboards & ReportingBuild and publish AI/BI Dashboards connected to Gold tables; configure Entra-based access for external usersPhase 6Security, Governance & CI/CDUnity Catalog ABAC policies, audit logging, Declarative Automation Bundles, GitHub Actions deployment pipelines

## 4. Azure Resources
### 4.1 Naming Pattern
pfin-<region>-<resource-type-abbreviation>
Region slug: canadacentral
### 4.2 Resource Inventory
Resource Type Name Status 
Resource Group pfin-canadacentral-rg✅
CreatedStorage Account (ADLS Gen2)pfincanadacentralsa✅ 
CreatedAccess Connectorpfin-canadacentral-ac✅ 
CreatedDatabricks Workspacepolitical-finance-ws✅ 
CreatedDatabricks Managed RGpfin-canadacentral-ws-mrg✅
Auto-createdService Principalpfin-databricks-sp⏭ Deferred to Phase 6
Key Vaultpfin-canadacentral-kv⏭ Deferred to Phase 6
### 4.3 Role Assignments
PrincipalRoleScopepfin-canadacentral-acStorage Blob Data Contributorpfincanadacentralsa
### 4.4 Deferred Role Assignments (Phase 6)
The following roles are required to enable File Events for Auto Loader performance optimization. They were not assigned in Phase 0 and must be added in Phase 6:

Storage Account Contributor
EventGrid EventSubscription Contributor
Storage Queue Data Contributor

All three to be assigned to pfin-canadacentral-ac on pfincanadacentralsa.
### 4.5 Required Tags
Applied to all resources via docs/phase-0/tag-resources.sh:
Tag KeyValueProjectCanadian-Political-Contributions-Analytics-PlatformProjectShortNamePolitical-FinanceAbbreviationpfinEnvironmentdevOwnerArsalan EslamiCostCenterTBD — assign before production deployment

## 5. ADLS Gen2 Storage Structure
Storage Account: pfincanadacentralsa
Hierarchical Namespace: Enabled
ContainerDirectoryPurposelandinglanding/Raw source file drop zone — Auto Loader watches this pathbronzebronze/Raw ingestion layer Delta tablessilversilver/Cleaned and normalized Delta tablesgoldgold/Business aggregation Delta tablesopsops/Audit logs, data quality logs, checkpoints

## 6. Databricks Workspace
SettingValueWorkspace Namepolitical-finance-wsManaged Resource Grouppfin-canadacentral-ws-mrgRegionCanada CentralSecure Cluster Connectivity (No Public IP)EnabledVNet InjectionDisabled (enable in production — Phase 6)Unity CatalogEnabledPlanTrial

7. Unity Catalog
7.1 Storage Credential
FieldValueNamepfin_storage_credTypeAzure Managed IdentityAccess Connectorpfin-canadacentral-ac
7.2 External Location
FieldValueNamepfin_lakehouseURLabfss://landing@pfincanadacentralsa.dfs.core.windows.net/landing/Storage Credentialpfin_storage_credFile EventsForce created — permissions not fully verified (deferred to Phase 6)
7.3 Catalogs
CatalogPurposepfin_devAll development and testing workpfin_prodProduction — schemas to be created in Phase 5
7.4 Schemas (pfin_dev)
SchemaPurposelandingRaw file volume — Auto Loader sourcebronzeRaw ingestion layersilverCleaned and normalized layergoldBusiness aggregationsopsAudit logs, data quality logs, checkpoints
7.5 Volumes
VolumePathPurposepfin_dev.landing.zoneabfss://landing@pfincanadacentralsa.dfs.core.windows.net/landing/raw/Landing zone for raw source file uploads

8. Entra ID Security Groups
Group NameDatabricks RoleAccessentra-pfin-engineerWorkspace AdminFull Databricks workspaceentra-pfin-dashboard-adminDashboard EditorAll dashboards — can publish and editentra-pfin-dashboard-analystDashboard ViewerShared dashboards via link onlyentra-pfin-dashboard-publicDashboard ViewerShared dashboards via link only
Current Members
UserGroupsarsalan@areslamihotmail.onmicrosoft.comentra-pfin-engineer, entra-pfin-dashboard-admin, adminsfaraz@areslamihotmail.onmicrosoft.comentra-pfin-engineerareslami@hotmail.comadmins (backup admin only)
Note: entra-pfin-dashboard-analyst and entra-pfin-dashboard-public are empty — real users will be added in Phase 5.

9. Git Repository
FieldValueRepository Namepfin-analyticsHostGitHubVisibilityPrivateURLhttps://github.com/arsalaneslami/pfin-analyticsDefault BranchmainIntegration Branchdevelop
Branch Strategy
BranchPurposemainProduction-ready code onlydevelopIntegration branch — all features merge here firstfeature/pfin-{ticket}-{desc}New feature developmentfix/pfin-{ticket}-{desc}Bug fixesrelease/v{major}.{minor}Release stabilizationhotfix/pfin-{ticket}-{desc}Critical production fixes
Branch Protection
Branch protection rules were attempted but require GitHub Team plan for private repositories. To be enabled in Phase 6 or when repository is made public.
Folder Structure
pfin-analytics/
├── .github/
│   └── workflows/          ← CI/CD pipeline definitions (Phase 6)
├── src/
│   ├── ingestion/          ← Bronze layer scripts (Phase 1)
│   ├── transformation/     ← Silver scripts (Phase 2)
│   ├── aggregation/        ← Gold scripts (Phase 3)
│   └── pipelines/          ← Lakeflow pipeline definitions
├── dashboards/             ← Exported dashboard JSON (Phase 5)
├── bundles/                ← Declarative Automation Bundles (Phase 6)
│   └── resources/
├── data/
│   └── samples/            ← Small sample CSVs for dev/testing
├── docs/
│   ├── phase-0/
│   ├── phase-1/
│   ├── phase-2/
│   ├── phase-3/
│   ├── phase-4/
│   ├── phase-5/
│   └── phase-6/
├── tests/
└── README.md

10. Compute
SettingValueCluster Namepfin-dev-interactiveRuntime17.3 LTS (Scala 2.13, Spark 4.0.0)Node TypeStandard_D4pds_v6 (16GB, 4 cores)ModeSingle NodeAuto Termination30 minutesUnity Catalog AccessVerified — SELECT current_catalog() returns pfin_dev

11. Tagging Script
Location: docs/phase-0/tag-resources.sh
Applies all required tags to:

Resource Group (az group update)
All resources in the group (loop with MSYS_NO_PATHCONV=1)
Storage Account (az storage account update — handled separately)
Access Connector (az databricks access-connector update — handled separately)

Run with:
bashaz login
bash docs/phase-0/tag-resources.sh

12. Exit Criteria
#CriterionStatus1All Azure resources exist in pfin-canadacentral-rg✅2ADLS containers created with correct directory structure✅3Storage Blob Data Contributor assigned to Access Connector✅4Databricks workspace accessible✅5Unity Catalog enabled with pfin_dev catalog and all schemas✅6External Location pfin_lakehouse validated✅7Landing volume pfin_dev.landing.zone created✅8Entra groups created and synced to Databricks✅9Git repo initialized with folder structure and both branches✅10Databricks workspace connected to GitHub repo✅11Dev cluster running and accessing pfin_dev catalog✅12All resources tagged via script✅

13. Deferred to Phase 6
ItemReasonService Principal pfin-databricks-spOnly needed for CI/CD automationKey Vault pfin-canadacentral-kvOnly needed for secret management in CI/CDFile Events role assignments (3 roles)Optional — improves Auto Loader performanceVNet InjectionProduction hardeningBranch protection rulesRequires GitHub Team plan or public repository

14. Document Control
VersionDateAuthorChange1.0May 2026Arsalan EslamiInitial Phase 0 document