import json
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import catalog

def load_mcp_config():
    with open('mcp.json', 'r') as f:
        return json.load(f)

def connect_to_databricks():
    # Load configuration
    config = load_mcp_config()
    
    # Initialize the workspace client
    workspace = WorkspaceClient(
        host=config['host'],
        token=config['token']
    )
    
    # Test the connection by listing catalogs
    try:
        catalogs = workspace.catalogs.list()
        print("Successfully connected to Databricks!")
        print("\nAvailable catalogs:")
        for catalog in catalogs:
            print(f"- {catalog.name}")
    except Exception as e:
        print(f"Error connecting to Databricks: {str(e)}")

if __name__ == "__main__":
    connect_to_databricks() 