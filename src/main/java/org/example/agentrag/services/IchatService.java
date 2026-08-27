package org.example.agentrag.services;

import org.example.agentrag.Dto.CreateChatRequest;

import org.example.agentrag.model.Chat;

import java.util.List;

public interface IchatService {

    Chat createChat(String email, CreateChatRequest request);

    List<Chat> getChats(String email);
    void deleteChat(String email, Long chatId);
    Chat togglePinChat(String email, Long chatId);


}
