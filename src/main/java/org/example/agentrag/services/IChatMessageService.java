package org.example.agentrag.services;


import org.example.agentrag.Dto.AgentResponse;
import org.example.agentrag.Dto.SendMessageRequest;
import org.example.agentrag.model.ChatMessage;

import java.util.List;

public interface IChatMessageService {
    public AgentResponse sendMessage(
            String email,
            Long chatId,
            SendMessageRequest request
    );
    List<ChatMessage> getMessages(
            String email,
            Long chatId
    );
}
