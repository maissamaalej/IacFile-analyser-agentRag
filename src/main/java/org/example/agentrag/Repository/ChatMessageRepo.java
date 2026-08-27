package org.example.agentrag.Repository;

import org.example.agentrag.model.Chat;
import org.example.agentrag.model.ChatMessage;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ChatMessageRepo  extends JpaRepository<ChatMessage,Long> {
    List<ChatMessage> findByChatOrderByTimestampAsc(Chat chat);}
