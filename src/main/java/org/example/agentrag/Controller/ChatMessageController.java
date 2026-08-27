package org.example.agentrag.Controller;


import lombok.AllArgsConstructor;
import org.example.agentrag.Dto.AgentResponse;
import org.example.agentrag.Dto.SendMessageRequest;
import org.example.agentrag.model.ChatMessage;
import org.example.agentrag.services.IChatMessageService;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/chatMessage")
@AllArgsConstructor
public class ChatMessageController {

    private final IChatMessageService chatMessageService;


    @PostMapping("/{chatId}/messages")
    public AgentResponse sendMessage(
            @PathVariable Long chatId,
            @RequestBody SendMessageRequest request,
            Authentication authentication
    ) {


        return chatMessageService.sendMessage(
                authentication.getName(),
                chatId,
                request
        );

    }
    @GetMapping("/{chatId}/messages")
    public List<ChatMessage> getMessages(
            @PathVariable Long chatId,
            Authentication authentication
    ) {

        return chatMessageService.getMessages(
                authentication.getName(),
                chatId
        );

    }


}
