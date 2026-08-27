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
public class InfraMetadata {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private long id;

    private String fileName;

    private String fileHash;

    private String storagePath;

    private Integer complianceScore;

    private LocalDateTime lastAnalyzedAt;

    private LocalDateTime createdAt;

    private LocalDateTime updatedAt;

    @OneToOne(mappedBy = "infraMetadata")
    private ChatMessage Chatmessage;


}
