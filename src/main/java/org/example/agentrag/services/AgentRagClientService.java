package org.example.agentrag.services;

import org.example.agentrag.Dto.AgentRequest;
import org.example.agentrag.Dto.AgentResponse;

public interface AgentRagClientService {
    public AgentResponse ask(AgentRequest request);
}
