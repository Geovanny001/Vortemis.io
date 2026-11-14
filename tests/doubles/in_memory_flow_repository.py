from vortemis.domain.entities.network_flow import NetworkFlow


class InMemoryFlowRepository:
    def __init__(self) -> None:
        self.saved_flows: list[NetworkFlow] = []

    async def save_batch(self, flows: list[NetworkFlow]) -> int:
        known = {flow.flow_id for flow in self.saved_flows}
        inserted = 0
        for flow in flows:
            if flow.flow_id in known:
                continue
            known.add(flow.flow_id)
            self.saved_flows.append(flow)
            inserted += 1
        return inserted
