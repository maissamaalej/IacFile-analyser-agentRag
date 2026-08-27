package org.example.agentrag.model;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDateTime;

@Entity
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class ChatMessage {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private long id;

    @Enumerated(EnumType.STRING)
    private SenderType sender;

    @Lob
    @Column(columnDefinition = "LONGTEXT")
    private String content;

    private String metadata;

    private LocalDateTime timestamp = LocalDateTime.now();

    private boolean isPinned = false;

    private boolean isEdited = false;

    private String userQuestionId;

    @ManyToOne
    private Chat chat;

    @OneToOne
    private InfraMetadata infraMetadata;



}
