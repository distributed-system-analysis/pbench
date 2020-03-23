import os


def get_config():
    """Determine if we are running the agent or the server"""
    if os.environ.get("_PBENCH_SERVER_CONFIG"):
        return "_PBENCH_SERVER_CONFIG"
    elif os.environ.get("_PBENCH_AGENT_CONFIG"):
        return "_PBENCH_AGENT_CONFIG"
    else:
        raise Exception("Unable to determine environment")
