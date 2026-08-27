package org.example.agentrag.model;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class HallucinationEvaluation {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private Boolean grounded;

    private Double score;

    @Column(columnDefinition = "TEXT")
    private String question;

    @Lob
    @Column(columnDefinition = "LONGTEXT")
    private String answer;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "chat_id")
    private Chat chat;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id")
    private User user;

    private LocalDateTime createdAt;


    @PrePersist
    public void onCreate(){

        createdAt = LocalDateTime.now();

    }

}