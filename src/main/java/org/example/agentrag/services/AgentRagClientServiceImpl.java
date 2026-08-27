package org.example.agentrag.services;


import org.example.agentrag.Dto.AgentRequest;
import org.example.agentrag.Dto.AgentResponse;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

@Service
public class AgentRagClientServiceImpl implements AgentRagClientService {

    private final WebClient webClient;

    public AgentRagClientServiceImpl(WebClient.Builder builder) {
        this.webClient = builder
                .baseUrl("http://localhost:8001")
                .build();
    }

    public AgentResponse ask(AgentRequest request) {

        return webClient.post()
                .uri("/chat")
                .bodyValue(request)
                .retrieve()
                .bodyToMono(AgentResponse.class)
                .block();
    }
}
