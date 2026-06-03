# PFIN — Phase 6: Security, Governance & CI/CD

**Project:** Canadian Political Contributions Analytics Platform  
**Abbreviation:** pfin  
**Version:** 1.0  
**Date:** June 2026  
**Author:** Arsalan Eslami

---

## 1. Purpose and Scope

Phase 6 hardens the platform for production readiness. It covers service principal creation, secret management via Key Vault, Auto Loader File Events permissions, VNet injection, branch protection, Unity Catalog ABAC policies, audit logging, Declarative Automation Bundles, and GitHub Actions CI/CD pipelines.

No item in this phase changes the data already flowing through Bronze → Silver → Gold → Dashboards. All changes are infrastructure, security, and automation.

---

## 2. Phase 6 Deliverables

| # | Deliverable | Source |
|---|---|---|
| 1 | Service Principal `pfin-databricks-sp` | Deferred from Phase 0 |
| 2 | Key Vault `pfin-canadacentral-kv` | Deferred from Phase 0 |
| 3 | File Events role assignments (3 IAM roles) | Deferred from Phase 0 |
| 4 | VNet Injection on Databricks workspace | Deferred from Phase 0 |
| 5 | Branch protection rules on `main` and `develop` | Deferred from Phase 0 |
| 6 | Service principal as dashboard publisher | Carry-forward from Phase 5 |
| 7 | Unity Catalog ABAC policies | New |
| 8 | Audit logging review — no PII exposure | New |
| 9 | Declarative Automation Bundle (`bundles/databricks.yml`) | New |
| 10 | GitHub Actions CI/CD workflows | New |
| 11 | Phase 6 documentation | New |

---

## 3. Service Principal

**Name:** `pfin-databricks-sp`  
**Purpose:** Non-interactive identity used by GitHub Actions and Databricks Automation Bundles to deploy and run pipelines without a personal user account.

### 3.1 Manual Steps (Azure Portal)

1. Go to **Microsoft Entra ID → App registrations → New registration**.
2. Set the name to `pfin-databricks-sp`.
3. Leave **Supported account types** as "Accounts in this organizational directory only".
4. Leave **Redirect URI** blank.
5. Click **Register**.
6. On the overview page, copy the **Application (client) ID** and **Directory (tenant) ID**. Save both — you will need them later.
7. Go to **Certificates & secrets → Client secrets → New client secret**.
8. Set description to `pfin-phase6-cicd` and expiry to **12 months**.
9. Click **Add**. Copy the **Value** immediately — it is shown only once.

### 3.2 Role Assignment for the Service Principal

The service principal needs **Contributor** on the resource group so GitHub Actions can deploy bundles and manage Databricks resources.

1. Go to **Resource Groups → pfin-canadacentral-rg → Access control (IAM) → Add role assignment**.
2. Role: **Contributor**.
3. Members: Select **User, group, or service principal** → search for `pfin-databricks-sp` → select it.
4. Click **Review + assign**.

### 3.3 CLI Equivalent

```bash
# Creates the SP and assigns Contributor on the resource group in one command
az ad sp create-for-rbac \
  --name pfin-databricks-sp \
  --role Contributor \
  --scopes /subscriptions/$(az account show --query id -o tsv)/resourceGroups/pfin-canadacentral-rg
```

Output contains `appId`, `password`, and `tenant`. Save all three.

---

## 4. Key Vault

**Name:** `pfin-canadacentral-kv`  
**Purpose:** Centralized secret store for service principal credentials, Databricks PATs, and any future secrets. GitHub Actions retrieves secrets from here at deploy time.

### 4.1 Manual Steps (Azure Portal)

1. Go to **Key Vaults → Create**.
2. Resource group: `pfin-canadacentral-rg`.
3. Key vault name: `pfin-canadacentral-kv`.
4. Region: **Canada Central**.
5. Pricing tier: **Standard**.
6. Under **Access configuration**, select **Azure role-based access control (recommended)**.
7. Click **Review + create → Create**.

### 4.2 Grant Yourself Secrets Officer Role

You need this role to add secrets to the vault.

1. Go to **pfin-canadacentral-kv → Access control (IAM) → Add role assignment**.
2. Role: **Key Vault Secrets Officer**.
3. Members: Select your own Entra account.
4. Click **Review + assign**.

### 4.3 Store Service Principal Secrets

1. Go to **pfin-canadacentral-kv → Secrets → Generate/Import**.
2. Create three secrets:

| Secret Name | Value | Description |
|---|---|---|
| `sp-client-id` | The Application (client) ID from Section 3 | Service principal app ID |
| `sp-client-secret` | The client secret Value from Section 3 | Service principal password |
| `sp-tenant-id` | The Directory (tenant) ID from Section 3 | Entra tenant ID |

### 4.4 CLI Equivalent

```bash
# Create the Key Vault
az keyvault create \
  --name pfin-canadacentral-kv \
  --resource-group pfin-canadacentral-rg \
  --location canadacentral \
  --enable-rbac-authorization true

# Grant yourself Secrets Officer
az role assignment create \
  --assignee $(az ad signed-in-user show --query id -o tsv) \
  --role "Key Vault Secrets Officer" \
  --scope $(az keyvault show --name pfin-canadacentral-kv --query id -o tsv)

# Store secrets
az keyvault secret set --vault-name pfin-canadacentral-kv --name sp-client-id --value "<appId>"
az keyvault secret set --vault-name pfin-canadacentral-kv --name sp-client-secret --value "<password>"
az keyvault secret set --vault-name pfin-canadacentral-kv --name sp-tenant-id --value "<tenant>"
```

---

## 5. File Events Role Assignments (Auto Loader)

**Purpose:** These three roles allow the Databricks Access Connector to set up Azure EventGrid notifications on the storage account. With File Events enabled, Auto Loader reacts to new files instantly via event notifications instead of polling the directory — significantly more efficient at scale.

**Principal:** `pfin-canadacentral-ac` (managed identity of the Access Connector)  
**Scope:** `pfincanadacentralsa` (the ADLS Gen2 storage account)

### 5.1 Roles to Assign

| # | Role | Why |
|---|---|---|
| 1 | Storage Account Contributor | Allows configuration of EventGrid event subscriptions on the storage account |
| 2 | EventGrid EventSubscription Contributor | Allows creation and management of EventGrid subscriptions |
| 3 | Storage Queue Data Contributor | Allows reading event notifications from the storage queue that EventGrid writes to |

### 5.2 Manual Steps (Azure Portal)

Repeat the following for each of the three roles:

1. Go to **Storage accounts → pfincanadacentralsa → Access control (IAM) → Add role assignment**.
2. Select the role (from the table above).
3. Members: Select **Managed identity** → **Select members**.
4. Filter by **Databricks Access Connector** → select `pfin-canadacentral-ac`.
5. Click **Review + assign**.

### 5.3 CLI Equivalent

```bash
SA_ID=$(az storage account show \
  --name pfincanadacentralsa \
  --resource-group pfin-canadacentral-rg \
  --query id -o tsv)

AC_PRINCIPAL=$(az databricks access-connector show \
  --name pfin-canadacentral-ac \
  --resource-group pfin-canadacentral-rg \
  --query identity.principalId -o tsv)

az role assignment create --assignee $AC_PRINCIPAL --role "Storage Account Contributor" --scope $SA_ID
az role assignment create --assignee $AC_PRINCIPAL --role "EventGrid EventSubscription Contributor" --scope $SA_ID
az role assignment create --assignee $AC_PRINCIPAL --role "Storage Queue Data Contributor" --scope $SA_ID
```

---

## 6. Resource Tagging

Apply the standard project tags to the new Key Vault resource. The service principal is an Entra object and does not support Azure resource tags.

### 6.1 Manual Steps (Azure Portal)

1. Go to **pfin-canadacentral-kv → Tags**.
2. Add the following tags:

| Tag Key | Value |
|---|---|
| Project | Canadian-Political-Contributions-Analytics-Platform |
| ProjectShortName | Political-Finance |
| Abbreviation | pfin |
| Environment | dev |
| Owner | Arsalan Eslami |
| CostCenter | TBD — assign before production deployment |

3. Click **Save**.

### 6.2 CLI Equivalent

```bash
az keyvault update \
  --name pfin-canadacentral-kv \
  --resource-group pfin-canadacentral-rg \
  --tags \
    Project="Canadian-Political-Contributions-Analytics-Platform" \
    ProjectShortName="Political-Finance" \
    Abbreviation="pfin" \
    Environment="dev" \
    Owner="Arsalan Eslami" \
    CostCenter="TBD"
```

---

## 7. Branch Protection Rules

**Purpose:** Prevent direct pushes to `main` and `develop`. All changes must go through pull requests.

**Prerequisite:** GitHub Team plan or a public repository. If the repository is on the GitHub Free plan and private, branch protection rules are not available — consider making the repo public or upgrading.

### 7.1 Manual Steps (GitHub)

For **both** `main` and `develop`:

1. Go to **pfin-analytics → Settings → Branches → Add branch ruleset** (or **Add rule** under Branch protection rules if using classic).
2. Branch name pattern: `main` (then repeat for `develop`).
3. Enable the following:
   - ✅ Require a pull request before merging
   - ✅ Require approvals: **1**
   - ✅ Require status checks to pass before merging (add CI checks after GitHub Actions are configured)
   - ✅ Require branches to be up to date before merging
   - ✅ Do not allow bypassing the above settings
4. Click **Save changes**.

### 7.2 CLI Equivalent (GitHub CLI)

```bash
# Requires GitHub CLI (gh) authenticated
# Classic branch protection — repeat for develop
gh api repos/{owner}/pfin-analytics/branches/main/protection \
  --method PUT \
  --input - <<'EOF'
{
  "required_pull_request_reviews": {
    "required_approving_review_count": 1
  },
  "required_status_checks": {
    "strict": true,
    "contexts": []
  },
  "enforce_admins": true,
  "restrictions": null
}
EOF
```

---

## 8. VNet Injection (Production Hardening)

**Purpose:** Places Databricks compute nodes inside a customer-managed VNet, restricting network traffic and eliminating public IPs on cluster nodes.

**Important considerations:**
- VNet injection **cannot be added to an existing workspace** — it must be configured at workspace creation time.
- To enable this, you would need to create a **new workspace** with VNet injection and migrate resources.
- For a dev/portfolio project, the current setup with **Secure Cluster Connectivity (No Public IP)** already enabled provides reasonable network isolation.

### 8.1 Recommendation

**Defer VNet injection** unless you plan to deploy this to a real production environment. Document it as a production-readiness step. The current workspace already has Secure Cluster Connectivity enabled, which means cluster nodes have no public IP addresses and all traffic exits through the control plane.

If you do proceed in the future, the steps are:

1. Create a VNet with two dedicated subnets (one for host, one for container).
2. Create an NSG with the required Databricks rules.
3. Create a new Databricks workspace with VNet injection pointing to those subnets.
4. Migrate Unity Catalog metastore assignment, external locations, notebooks, and pipelines.

### 8.2 CLI Equivalent (New Workspace with VNet Injection)

```bash
# Step 1: Create VNet and subnets
az network vnet create \
  --name pfin-canadacentral-vnet \
  --resource-group pfin-canadacentral-rg \
  --location canadacentral \
  --address-prefix 10.0.0.0/16

az network vnet subnet create \
  --name pfin-host-subnet \
  --vnet-name pfin-canadacentral-vnet \
  --resource-group pfin-canadacentral-rg \
  --address-prefix 10.0.1.0/24 \
  --delegations Microsoft.Databricks/workspaces

az network vnet subnet create \
  --name pfin-container-subnet \
  --vnet-name pfin-canadacentral-vnet \
  --resource-group pfin-canadacentral-rg \
  --address-prefix 10.0.2.0/24 \
  --delegations Microsoft.Databricks/workspaces

# Step 2: Create workspace with VNet injection
az databricks workspace create \
  --name political-finance-ws-vnet \
  --resource-group pfin-canadacentral-rg \
  --location canadacentral \
  --sku premium \
  --managed-resource-group pfin-canadacentral-ws-vnet-mrg \
  --vnet pfin-canadacentral-vnet \
  --private-subnet pfin-host-subnet \
  --public-subnet pfin-container-subnet \
  --no-public-ip
```

---

## 9. Updated Resource Inventory

After completing Sections 3–6, the full resource inventory becomes:

| Resource Type | Name | Status |
|---|---|---|
| Resource Group | `pfin-canadacentral-rg` | ✅ Created (Phase 0) |
| Storage Account (ADLS Gen2) | `pfincanadacentralsa` | ✅ Created (Phase 0) |
| Access Connector | `pfin-canadacentral-ac` | ✅ Created (Phase 0) |
| Databricks Workspace | `political-finance-ws` | ✅ Created (Phase 0) |
| Databricks Managed RG | `pfin-canadacentral-ws-mrg` | ✅ Auto-created (Phase 0) |
| Service Principal | `pfin-databricks-sp` | ⬜ Phase 6 |
| Key Vault | `pfin-canadacentral-kv` | ⬜ Phase 6 |

## 10. Updated Role Assignments

| Principal | Role | Scope | Phase |
|---|---|---|---|
| `pfin-canadacentral-ac` | Storage Blob Data Contributor | `pfincanadacentralsa` | Phase 0 |
| `pfin-databricks-sp` | Contributor | `pfin-canadacentral-rg` | Phase 6 |
| Your Entra account | Key Vault Secrets Officer | `pfin-canadacentral-kv` | Phase 6 |
| `pfin-canadacentral-ac` | Storage Account Contributor | `pfincanadacentralsa` | Phase 6 |
| `pfin-canadacentral-ac` | EventGrid EventSubscription Contributor | `pfincanadacentralsa` | Phase 6 |
| `pfin-canadacentral-ac` | Storage Queue Data Contributor | `pfincanadacentralsa` | Phase 6 |

---

## 11. Remaining Phase 6 Work

The following deliverables will be documented separately after the infrastructure items above are completed:

| # | Deliverable | Status |
|---|---|---|
| 1 | Service Principal created | ⬜ |
| 2 | Key Vault created and secrets stored | ⬜ |
| 3 | File Events role assignments (3 roles) | ⬜ |
| 4 | Key Vault tagged | ⬜ |
| 5 | Branch protection rules on `main` and `develop` | ⬜ |
| 6 | VNet Injection | ⏭ Deferred to production |
| 7 | Service principal as dashboard publisher | ⬜ |
| 8 | Unity Catalog ABAC policies | ⬜ |
| 9 | Audit logging review — no PII exposure | ⬜ |
| 10 | Declarative Automation Bundle | ⬜ |
| 11 | GitHub Actions CI/CD workflows | ⬜ |
| 12 | Phase 6 documentation finalized | ⬜ |

---

## 12. Document Control

| Date | Version | Change | Author |
|---|---|---|---|
| 2026-06-02 | 1.0 | Initial Phase 6 infrastructure documentation | Arsalan Eslami |

---

File location: `docs/phase-6/security.md` in the pfin-analytics repository.
