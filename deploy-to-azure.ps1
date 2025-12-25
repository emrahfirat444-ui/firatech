<#
.SYNOPSIS
  Deploy Yataş Streamlit app and gateway to Azure: create resource group, ACR, build images, push, and create App Service.

USAGE
  .\deploy-to-azure.ps1 -SubscriptionId <sub-id> -ResourceGroup <rg> -Location "westeurope" -ACRName <acrname> -AppName <appname> -GatewayAppName <gatewayappname>

NOTES
  - Requires Azure CLI installed and user must run `az login` interactively, or use a service principal beforehand.
  - This script uses `az acr build` to build images in the cloud; no local Docker daemon required.
  - After running, the script outputs a JSON file named `azure-gh-actions-creds.json` you can paste into GitHub Secret `AZURE_CREDENTIALS`.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SubscriptionId,
    [Parameter(Mandatory=$true)][string]$ResourceGroup,
    [Parameter(Mandatory=$false)][string]$Location = "westeurope",
    [Parameter(Mandatory=$true)][string]$ACRName,
    [Parameter(Mandatory=$true)][string]$AppName,
    [Parameter(Mandatory=$false)][string]$GatewayAppName = "$AppName-gateway",
    [Parameter(Mandatory=$false)][string]$PlanName = "yatas-plan",
    [Parameter(Mandatory=$false)][string]$ImageTag = "latest"
)

# Safety: respect STOP_COSTS to avoid accidental cloud costs
if ($env:STOP_COSTS -eq "1") {
  Write-Host "STOP_COSTS=1 - Aborting deploy-to-azure.ps1 to avoid incurring cloud costs."
  exit 0
}

# Require explicit allow to deploy (prevents accidental runs)
if ($env:ALLOW_DEPLOY -ne "1") {
  Write-Host "ALLOW_DEPLOY is not set to 1. Set environment variable ALLOW_DEPLOY=1 to permit deployment. Aborting."
  exit 0
}

Write-Host "Setting subscription to $SubscriptionId"
az account set --subscription $SubscriptionId

Write-Host "Creating resource group $ResourceGroup in $Location..."
az group create --name $ResourceGroup --location $Location | Out-Null

Write-Host "Creating ACR $ACRName (Standard)..."
az acr create --resource-group $ResourceGroup --name $ACRName --sku Standard --admin-enabled true | Out-Null

$acrLoginServer = az acr show --name $ACRName --resource-group $ResourceGroup --query "loginServer" -o tsv
Write-Host "ACR login server: $acrLoginServer"

Write-Host "Building and pushing app image to ACR via az acr build..."
az acr build --registry $ACRName --image "$ACRName/streamlit-app:$ImageTag" -f Dockerfile.app .

Write-Host "Building and pushing gateway image to ACR via az acr build..."
az acr build --registry $ACRName --image "$ACRName/gateway:$ImageTag" -f Dockerfile.gateway .

Write-Host "Creating App Service plan ($PlanName) and Web App ($AppName)..."
az appservice plan create --name $PlanName --resource-group $ResourceGroup --is-linux --sku B1 | Out-Null

Write-Host "Creating Web App for Streamlit..."
az webapp create --resource-group $ResourceGroup --plan $PlanName --name $AppName --deployment-container-image-name "$acrLoginServer/$ACRName/streamlit-app:$ImageTag" | Out-Null

Write-Host "Configure Web App to pull from ACR (set credentials)..."
$acrCred = az acr credential show --name $ACRName --resource-group $ResourceGroup -o json | ConvertFrom-Json
$acrUser = $acrCred.username
$acrPassword = $acrCred.passwords[0].value

az webapp config container set --name $AppName --resource-group $ResourceGroup --docker-custom-image-name "$acrLoginServer/$ACRName/streamlit-app:$ImageTag" --docker-registry-server-url "https://$acrLoginServer" --docker-registry-server-user $acrUser --docker-registry-server-password $acrPassword | Out-Null

Write-Host "Set App Settings: demo mode = 1 (can change in portal later)"
az webapp config appsettings set --resource-group $ResourceGroup --name $AppName --settings "SAP_GATEWAY_DEMO=1" "PORT=80" | Out-Null

Write-Host "Optionally create a separate Web App for gateway ($GatewayAppName)"
az webapp create --resource-group $ResourceGroup --plan $PlanName --name $GatewayAppName --deployment-container-image-name "$acrLoginServer/$ACRName/gateway:$ImageTag" | Out-Null
az webapp config container set --name $GatewayAppName --resource-group $ResourceGroup --docker-custom-image-name "$acrLoginServer/$ACRName/gateway:$ImageTag" --docker-registry-server-url "https://$acrLoginServer" --docker-registry-server-user $acrUser --docker-registry-server-password $acrPassword | Out-Null
az webapp config appsettings set --resource-group $ResourceGroup --name $GatewayAppName --settings "PORT=5000" | Out-Null

Write-Host "Create service principal for GitHub Actions (scoped to the resource group)..."
$ghCreds = az ad sp create-for-rbac --name "gh-actions-$AppName" --role contributor --scopes "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup" --sdk-auth

if ($ghCreds) {
    $outFile = "azure-gh-actions-creds.json"
    $ghCreds | Out-File -Encoding utf8 $outFile
    Write-Host "Created service principal and saved JSON to $outFile. Paste its contents into GitHub secret 'AZURE_CREDENTIALS'"
} else {
    Write-Host "Failed to create service principal. You may create it manually and set AZURE_CREDENTIALS secret."
}

Write-Host "Done. Web App URL: https://$AppName.azurewebsites.net"
Write-Host "Gateway URL: https://$GatewayAppName.azurewebsites.net (if created)"
