#!/bin/bash

# PFIN - Azure Resource Tagging Script
# Run this script after all Phase 0 resources are provisioned
# Prerequisites: Azure CLI installed and logged in as arsalan@areslamihotmail.onmicrosoft.com

SUBSCRIPTION_ID="7a5afe2a-8293-49d6-8178-807eded61011"
RESOURCE_GROUP="pfin-canadacentral-rg"

TAGS=(
  "Project=Canadian-Political-Contributions-Analytics-Platform"
  "ProjectShortName=Political-Finance"
  "Abbreviation=pfin"
  "Environment=dev"
  "Owner=Arsalan Eslami"
  "CostCenter=TBD"
)

echo "Setting subscription..."
az account set --subscription $SUBSCRIPTION_ID

echo "Tagging all resources in Resource Group..."
for RESOURCE_ID in $(az resource list --resource-group $RESOURCE_GROUP --query "[].id" -o tsv); do
  if [[ "$RESOURCE_ID" == *"storageAccounts"* ]] || [[ "$RESOURCE_ID" == *"accessConnectors"* ]]; then
    echo "Skipping (handled separately): $RESOURCE_ID"
    continue
  fi
  echo "Tagging: $RESOURCE_ID"
  MSYS_NO_PATHCONV=1 az resource tag \
    --ids "$RESOURCE_ID" \
    --tags "${TAGS[@]}"
done

echo "Tagging Storage Account..."
MSYS_NO_PATHCONV=1 az storage account update \
  --name pfincanadacentralsa \
  --resource-group $RESOURCE_GROUP \
  --tags "${TAGS[@]}"

echo "Tagging Access Connector..."
MSYS_NO_PATHCONV=1 az databricks access-connector update \
  --name pfin-canadacentral-ac \
  --resource-group $RESOURCE_GROUP \
  --tags "${TAGS[@]}"

echo "Done. All resources tagged."