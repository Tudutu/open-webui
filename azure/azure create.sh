az login

RESOURCE_GROUP="synai-demo001-rg"
ENVIRONMENT_NAME="synai-demo001-container-environment"
LOCATION="ukwest"

az extension add -n containerapp --upgrade
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights

az group create --name $RESOURCE_GROUP --location $LOCATION --query "properties.provisioningState"

az containerapp env create --name $ENVIRONMENT_NAME --resource-group $RESOURCE_GROUP --location "$LOCATION" --query "properties.provisioningState"

STORAGE_ACCOUNT_NAME="synaidemo001stoacct"
STORAGE_SHARE_NAME="synaidemo001fileshare"

az storage account create --resource-group $RESOURCE_GROUP --name $STORAGE_ACCOUNT_NAME --location "$LOCATION" --kind StorageV2 --sku Standard_LRS --enable-large-file-share --query provisioningState

az storage share-rm create --resource-group $RESOURCE_GROUP --storage-account $STORAGE_ACCOUNT_NAME --name $STORAGE_SHARE_NAME --quota 1024 --enabled-protocols SMB --output table

STORAGE_ACCOUNT_KEY=`az storage account keys list -n $STORAGE_ACCOUNT_NAME --query "[0].value" -o tsv`

STORAGE_MOUNT_NAME="synaidemo001storagemount"

az containerapp env storage set --access-mode ReadWrite --azure-file-account-name $STORAGE_ACCOUNT_NAME --azure-file-account-key $STORAGE_ACCOUNT_KEY --azure-file-share-name $STORAGE_SHARE_NAME --storage-name $STORAGE_MOUNT_NAME --name $ENVIRONMENT_NAME --resource-group $RESOURCE_GROUP --output table

CONTAINER_APP_NAME="synai-demo001-container-app"

# az containerapp registry set --resource-group $RESOURCE_GROUP --server ghcr.io --username XXX --password XXX

az containerapp create --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --environment $ENVIRONMENT_NAME --image ghcr.io/tudutu/open-webui:latest --registry-server ghcr.io --registry-username XXX --registry-password XXX --min-replicas 1 --max-replicas 1 --target-port 80 --ingress external --target-port 8080 --env-vars WEBUI_NAME="Demo Site 1" --cpu 1.0 --memory 2.0Gi ENABLE_PERSISTENT_CONFIG="False" --query properties.configuration.ingress.fqdn

# "synai-demo001-container-app.icypebble-0e79b93c.ukwest.azurecontainerapps.io"

az containerapp show --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --output yaml > app.yaml

az containerapp update --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --yaml app.yaml --output table