from vortemis.domain.entities.network_flow import NetworkFlow


class InMemoryFlowRepository:
    def __init__(self) -> None:
        self.saved_flows: list[NetworkFlow] = []

    async def save_batch(self, flows: list[NetworkFlow]) -> None:
        self.saved_flows.extend(flows)
