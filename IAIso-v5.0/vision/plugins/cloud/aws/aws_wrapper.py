import boto3
from sdk.python.iaiso.engine import IAIsoEngine

class AwsIAIsoWrapper:
    def __init__(self, service):
        self.client = boto3.client(service)
        self.engine = IAIsoEngine(system_id="aws")

    def execute_safe(self, method, **kwargs):
        status = self.engine.update_pressure(tokens=100) # Baseline complexity
        if status == "RELEASED":
            raise Exception("IAIso Release Triggered: AWS Session Severed.")
        return getattr(self.client, method)(**kwargs)
