import os
import sys
import yaml
import argparse
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.appcontainers import ContainerAppsAPIClient

def get_config():
    """Parses command-line arguments and returns a configuration dictionary."""
    parser = argparse.ArgumentParser(description="Azure Container App Deployment Script")
    parser.add_argument("--project-name", type=str, required=True, help="The name of the project (e.g., demo-001)")
    args = parser.parse_args()

    project_name = args.project_name
    # Storage account names must be between 3 and 24 characters in length and use numbers and lower-case letters only.
    storage_project_name = project_name.replace("-", "")

    config = {
        "project_name": project_name,
        "resource_group": f"synai-{project_name}-rg",
        "environment_name": f"synai-{project_name}-container-environment",
        "location": "ukwest",
        "storage_account_name": f"synai{storage_project_name}stoacct",
        "storage_share_name": f"synai{storage_project_name}fileshare",
        "storage_mount_name": f"synai{storage_project_name}storagemount",
        "container_app_name": f"synai-{project_name}-container-app",
        "registry_server": "ghcr.io",
        "registry_username": "richardbushnell",
        "image": "ghcr.io/tudutu/open-webui:latest",
        "webui_name": f"Demo Site {project_name}"
    }
    return config

def main():
    """
    Sets up a container app in Azure using the Azure SDK for Python.
    """
    config = get_config()

    try:
        credential = DefaultAzureCredential()
        subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
        if not subscription_id:
            print("Error: AZURE_SUBSCRIPTION_ID environment variable not set.", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error during authentication: {e}", file=sys.stderr)
        print("Please ensure you are logged in to Azure with 'az login' and have the necessary permissions.", file=sys.stderr)
        sys.exit(1)

    registry_password = os.environ.get("REGISTRY_PASSWORD")
    if not registry_password:
        print("Warning: REGISTRY_PASSWORD environment variable not set.", file=sys.stderr)
        sys.exit(1)

    # --- Initialize Clients ---
    resource_client = ResourceManagementClient(credential, subscription_id)
    storage_client = StorageManagementClient(credential, subscription_id)
    container_apps_client = ContainerAppsAPIClient(credential, subscription_id)

    # --- Setup Azure Container App ---

    # Create resource group
    print(f"Creating resource group '{config['resource_group']}'...")
    resource_client.resource_groups.create_or_update(config['resource_group'], {"location": config['location']})
    print("Resource group created.")

    # Create container app environment
    print(f"Creating container app environment '{config['environment_name']}'...")
    container_apps_client.managed_environments.begin_create_or_update(
        config['resource_group'],
        config['environment_name'],
        {
            "location": config['location']
        }
    ).result()
    print("Container app environment created.")

    # Create storage account
    print(f"Creating storage account '{config['storage_account_name']}'...")
    storage_client.storage_accounts.begin_create(
        config['resource_group'],
        config['storage_account_name'],
        {
            "sku": {"name": "Standard_LRS"},
            "kind": "StorageV2",
            "location": config['location'],
            "enable_large_file_share": True
        }
    ).result()
    print("Storage account created.")

    # Create file share
    print(f"Creating file share '{config['storage_share_name']}'...")
    storage_client.file_shares.create(
        config['resource_group'],
        config['storage_account_name'],
        config['storage_share_name'],
        {"properties": {"shareQuota": 1024, "enabledProtocols": "SMB"}}
    )
    print("File share created.")

    # Get storage account key
    print("Retrieving storage account key...")
    storage_keys = storage_client.storage_accounts.list_keys(config['resource_group'], config['storage_account_name'])
    storage_account_key = storage_keys.keys[0].value
    print("Storage account key retrieved.")

    # Set up storage for container app environment
    print(f"Setting up storage mount '{config['storage_mount_name']}'...")
    container_apps_client.managed_environments.begin_update(
        config['resource_group'],
        config['environment_name'],
        {
            "properties": {
                "app_logs_configuration": {
                    "destination": "log-analytics"
                },
                "workload_profiles": [
                    {
                        "name": "Consumption",
                        "workload_profile_type": "Consumption",
                    }
                ]
            }
        }
    ).result()
    print("Storage mount created.")

    # Create container app
    print(f"Creating container app '{config['container_app_name']}'...")
    container_app = container_apps_client.container_apps.begin_create_or_update(
        config['resource_group'],
        config['container_app_name'],
        {
            "location": config['location'],
            "managed_environment_id": container_apps_client.managed_environments.get(config['resource_group'], config['environment_name']).id,
            "configuration": {
                "ingress": {
                    "external": True,
                    "target_port": 8080,
                },
                "registries": [
                    {
                        "server": config['registry_server'],
                        "username": config['registry_username'],
                        "password_secret_ref": "registry-password",
                    }
                ],
                "secrets": [
                    {"name": "registry-password", "value": registry_password}
                ]
            },
            "template": {
                "containers": [
                    {
                        "name": "open-webui",
                        "image": config['image'],
                        "resources": {
                            "cpu": 1.0,
                            "memory": "2.0Gi"
                        },
                        "env": [
                            {"name": "WEBUI_NAME", "value": config["webui_name"]},
                            {"name": "ENABLE_PERSISTENT_CONFIG", "value": "False"}
                        ]
                    }
                ],
                "scale": {
                    "min_replicas": 1,
                    "max_replicas": 1
                }
            }
        }
    ).result()
    print(f"Container app created. FQDN: {container_app.configuration.ingress.fqdn}")

    # Get app configuration
    print("Updating app configuration with volume mount...")
    app_config = container_apps_client.container_apps.get(config['resource_group'], config['container_app_name']).as_dict()

    # Add volume and volume mount
    volume_name = f"{config['project_name']}-azure-file-volume"
    app_config['template']['volumes'] = [
        {
            'name': volume_name,
            'storageName': config['storage_mount_name'],
            'storageType': 'AzureFile'
        }
    ]
    app_config['template']['containers'][0]['volumeMounts'] = [
        {
            'volumeName': volume_name,
            'mountPath': '/app/backend/data'
        }
    ]

    print("Saving app configuration to app.yaml...")
    with open("app.yaml", "w") as f:
        yaml.dump(app_config, f)
    print("App configuration saved.")

    # Update container app from yaml
    print("Updating container app from app.yaml...")
    with open("app.yaml", "r") as f:
        app_yaml_content = yaml.safe_load(f)

    container_apps_client.container_apps.begin_update(
        config['resource_group'],
        config['container_app_name'],
        app_yaml_content
    ).result()
    print("Container app updated.")

    print("Azure Container App setup complete.")

if __name__ == "__main__":
    main()