package org.example.agentrag.Dto;


import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@AllArgsConstructor
@NoArgsConstructor
public class AgentResponse {
    private String answer;


    private String explanation;


    private Boolean showFixAction;
    private Boolean grounded;

    private Double score;

}
