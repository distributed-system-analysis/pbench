from pbench import configtools


class AgentConfig:
    def __init__(self):
        opts, _ = configtools.parse_args()
        pbench_config, _ = configtools.init(opts, "_PBENCH_AGENT_CONFIG")

        self.agent = pbench_config["pbench-agent"]
        self.results = pbench_config["results"]

    def get_agent(self):
        return self.agent

    def get_results(self):
        return self.results
