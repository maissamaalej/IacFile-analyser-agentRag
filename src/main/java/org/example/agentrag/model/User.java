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
public class User {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private long id;


    private String email;


    private String firstName;


    private String lastName;


    private String password;


    @Enumerated(EnumType.STRING)
    private UserRole role;

    private String avatarUrl;


    private boolean isActive = true;




    @OneToMany(
            mappedBy = "user",
            cascade = CascadeType.ALL,
            orphanRemoval = true
    )
    @JsonIgnore
    private List<Chat> chats = new ArrayList<>();

}
