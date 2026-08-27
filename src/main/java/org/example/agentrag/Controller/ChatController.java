package org.example.agentrag.Controller;

import lombok.AllArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.example.agentrag.Dto.CreateChatRequest;
import org.example.agentrag.model.Chat;
import org.example.agentrag.services.IchatService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@AllArgsConstructor
@RequestMapping("/api/Chat")
public class ChatController {

    private IchatService chatService;


    @PostMapping
    public Chat createChat(
            @RequestBody CreateChatRequest request,
            Authentication authentication
    ) {

        System.out.println("AUTH : " + authentication);
        System.out.println("NAME : " + authentication.getName());
        System.out.println("AUTHORITIES : "
                + authentication.getAuthorities());


        return chatService.createChat(
                authentication.getName(),
                request
        );
    }

    @GetMapping
    public List<Chat> getChats(Authentication authentication) {

        String email = authentication.getName();

        return chatService.getChats(email);
    }
    @DeleteMapping("delete/{chatId}")
    public ResponseEntity<Void> deleteChat(
            @PathVariable Long chatId,
            Authentication authentication
    ) {

        chatService.deleteChat(
                authentication.getName(),
                chatId
        );

        return ResponseEntity.noContent().build();
    }
    @PutMapping("/pin/{chatId}")
    public ResponseEntity<Chat> togglePin(
            @PathVariable Long chatId,
            Authentication authentication
    ) {

        Chat chat = chatService.togglePinChat(
                authentication.getName(),
                chatId
        );

        return ResponseEntity.ok(chat);
    }


}
