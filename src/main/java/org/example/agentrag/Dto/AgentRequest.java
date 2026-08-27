package org.example.agentrag.Dto;


import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@AllArgsConstructor
@NoArgsConstructor
public class AgentRequest {
    private String prompt;
    private Long userId;


    private Long chatId;
}
