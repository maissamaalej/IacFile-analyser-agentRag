package org.example.agentrag.model;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Entity
@Getter
@Setter
@AllArgsConstructor
@NoArgsConstructor
public class Chat {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private long id;

    private String title;

    private String description;

    @Enumerated(EnumType.STRING)
    private ChatStatus status = ChatStatus.ACTIVE;


    private boolean pinned = false;


    private LocalDateTime createdAt;


    private LocalDateTime updatedAt;


    private LocalDateTime lastActivityAt;

    @ManyToOne
    private User user;


    @OneToMany(
            mappedBy = "chat",
            cascade = CascadeType.ALL,
            orphanRemoval = true,
            fetch = FetchType.LAZY
    )
    @JsonIgnore
    private List<ChatMessage> messages = new ArrayList<>();


    @Transient
    private int messageCount;

    @Transient
    private ChatMessage lastMessage;
}
