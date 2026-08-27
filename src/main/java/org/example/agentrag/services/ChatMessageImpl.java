package org.example.agentrag.services;

import lombok.AllArgsConstructor;
import org.example.agentrag.Dto.AgentRequest;
import org.example.agentrag.Dto.AgentResponse;
import org.example.agentrag.Dto.SendMessageRequest;
import org.example.agentrag.Repository.ChatMessageRepo;
import org.example.agentrag.Repository.ChatRepo;
import org.example.agentrag.Repository.UserRepo;
import org.example.agentrag.model.Chat;
import org.example.agentrag.model.ChatMessage;
import org.example.agentrag.model.SenderType;
import org.example.agentrag.model.User;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

@Service
@AllArgsConstructor
public class ChatMessageImpl implements IChatMessageService {

    private final AgentRagClientService agentRagClientService;

    private final UserRepo userRepo;

    private final ChatRepo chatRepo;

    private final ChatMessageRepo chatMessageRepo;

    private final HallucinationEvaluationService hallucinationEvaluationService;

    @Override
    public AgentResponse sendMessage(
            String email,
            Long chatId,
            SendMessageRequest request
    ) {

        // ==========================
        // Authenticated user
        // ==========================
        User user = userRepo
                .findByEmail(email)
                .orElseThrow(() ->
                        new RuntimeException("User not found"));

        // ==========================
        // Chat
        // ==========================
        Chat chat = chatRepo
                .findById(chatId)
                .orElseThrow(() ->
                        new RuntimeException("Chat not found"));

        if (chat.getUser().getId()!=user.getId()) {
            throw new RuntimeException("Unauthorized");
        }

        // ==========================
        // Save USER message
        // ==========================
        ChatMessage userMessage = new ChatMessage();

        userMessage.setChat(chat);
        userMessage.setSender(SenderType.USER);
        userMessage.setContent(request.getMessage());
        userMessage.setTimestamp(LocalDateTime.now());
        userMessage.setPinned(false);
        userMessage.setEdited(false);

        chatMessageRepo.save(userMessage);

        // ==========================
        // Call AgentRAG
        // ==========================
        AgentRequest agentRequest = new AgentRequest();

        agentRequest.setPrompt(request.getMessage());
        agentRequest.setUserId(user.getId());
        agentRequest.setChatId(chatId);

        AgentResponse response =
                agentRagClientService.ask(agentRequest);

        // ==========================
// Save Hallucination Evaluation
// ==========================

        hallucinationEvaluationService.saveEvaluation(

                chatId,

                email,

                request.getMessage(),

                response.getAnswer(),

                response.getGrounded(),

                response.getScore()

        );

        // ==========================
        // Save AGENT response
        // ==========================
        ChatMessage agentMessage = new ChatMessage();

        agentMessage.setChat(chat);
        agentMessage.setSender(SenderType.AGENT);
        agentMessage.setContent(response.getAnswer());
        agentMessage.setTimestamp(LocalDateTime.now());
        agentMessage.setPinned(false);
        agentMessage.setEdited(false);

        chatMessageRepo.save(agentMessage);

        return response;
    }

    @Override
    public List<ChatMessage> getMessages(
            String email,
            Long chatId
    ) {

        User user = userRepo
                .findByEmail(email)
                .orElseThrow(() ->
                        new RuntimeException("User not found"));

        Chat chat = chatRepo
                .findById(chatId)
                .orElseThrow(() ->
                        new RuntimeException("Chat not found"));

        if (chat.getUser().getId()!=user.getId()) {
            throw new RuntimeException("Unauthorized");
        }

        return chatMessageRepo
                .findByChatOrderByTimestampAsc(chat);

    }
}