package org.example.agentrag.services;

import lombok.AllArgsConstructor;
import org.example.agentrag.Dto.CreateChatRequest;
import org.example.agentrag.Repository.ChatRepo;
import org.example.agentrag.Repository.UserRepo;
import org.example.agentrag.model.Chat;
import org.example.agentrag.model.ChatStatus;
import org.example.agentrag.model.User;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

@Service
@AllArgsConstructor
public class ChatServiceImpl implements IchatService {
    private ChatRepo chatRepo;
    private final UserRepo userRepo;

    @Override
    public Chat createChat(String email, CreateChatRequest request) {

        User user = userRepo.findByEmail(email)
                .orElseThrow(() -> new RuntimeException("User not found"));

        Chat chat = new Chat();

        chat.setTitle(
                request.getTitle() == null || request.getTitle().isBlank()
                        ? "New Conversation"
                        : request.getTitle()
        );

        chat.setDescription("");

        chat.setPinned(false);

        chat.setStatus(ChatStatus.ACTIVE);

        chat.setCreatedAt(LocalDateTime.now());

        chat.setUpdatedAt(LocalDateTime.now());

        chat.setLastActivityAt(LocalDateTime.now());

        chat.setUser(user);

        return chatRepo.save(chat);
    }

    @Override
    public List<Chat> getChats(String email) {

        User user = userRepo.findByEmail(email)
                .orElseThrow(() -> new RuntimeException("User not found"));

        return chatRepo.findAllByUserIdOrderByPinnedDescLastActivityAtDesc(user.getId());
    }
    @Override
    public void deleteChat(String email, Long chatId) {

        User user = userRepo.findByEmail(email)
                .orElseThrow(() -> new RuntimeException("User not found"));

        Chat chat = chatRepo.findById(chatId)
                .orElseThrow(() -> new RuntimeException("Chat not found"));

        if (chat.getUser().getId() != user.getId()) {
            throw new RuntimeException("Unauthorized");
        }

        chatRepo.delete(chat);
    }
    @Override
    public Chat togglePinChat(String email, Long chatId) {


        User user = userRepo
                .findByEmail(email)
                .orElseThrow(
                        () -> new RuntimeException("User not found")
                );


        Chat chat = chatRepo
                .findById(chatId)
                .orElseThrow(
                        () -> new RuntimeException("Chat not found")
                );

        if(chat.getUser().getId()!=user.getId()){

            throw new RuntimeException(
                    "Unauthorized chat"
            );
        }



        chat.setPinned(
                !chat.isPinned()
        );


        chat.setUpdatedAt(
                LocalDateTime.now()
        );


        return chatRepo.save(chat);
    }
}
