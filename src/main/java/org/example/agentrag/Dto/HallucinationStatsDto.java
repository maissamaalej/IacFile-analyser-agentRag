package org.example.agentrag.Dto;


import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@AllArgsConstructor
@NoArgsConstructor
public class HallucinationStatsDto {

    private double hallucinationRate;

    private double averageScore;

    private long totalEvaluations;
}
