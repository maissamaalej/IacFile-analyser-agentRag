package org.example.agentrag.Repository;

import org.example.agentrag.model.Chat;
import org.example.agentrag.model.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface ChatRepo extends JpaRepository<Chat,Long> {
    List<Chat> findAllByUserIdOrderByPinnedDescLastActivityAtDesc(Long userId);
    Optional<Chat> findByIdAndUser(Long id, User user);
}
