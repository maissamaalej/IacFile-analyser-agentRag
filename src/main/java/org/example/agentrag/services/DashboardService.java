package org.example.agentrag.services;

import lombok.RequiredArgsConstructor;
import org.example.agentrag.Dto.HallucinationPointDTO;
import org.example.agentrag.Dto.HallucinationStatsDto;
import org.example.agentrag.Repository.HallucinationEvaluationRepo;
import org.example.agentrag.model.HallucinationEvaluation;
import org.springframework.stereotype.Service;

import java.time.format.DateTimeFormatter;
import java.util.List;

@Service
@RequiredArgsConstructor
public class DashboardService {

    private final HallucinationEvaluationRepo repository;

    /**
     * Dashboard cards
     */
    public HallucinationStatsDto getHallucinationStats() {

        List<HallucinationEvaluation> evaluations = repository.findAll();

        if (evaluations.isEmpty()) {

            return new HallucinationStatsDto(
                    0.0,
                    0.0,
                    0L
            );

        }

        double averageScore = evaluations.stream()
                .filter(e -> e.getScore() != null)
                .mapToDouble(HallucinationEvaluation::getScore)
                .average()
                .orElse(0.0);

        double hallucinationRate = (1 - averageScore) * 100;

        return new HallucinationStatsDto(

                Math.round(hallucinationRate * 100.0) / 100.0,

                Math.round(averageScore * 100.0) / 100.0,

                (long) evaluations.size()

        );

    }

    /**
     * Chart data
     */
    public List<HallucinationPointDTO> getHallucinationChart() {

        DateTimeFormatter formatter =
                DateTimeFormatter.ofPattern("dd MMM");

        return repository
                .findAllByOrderByCreatedAtAsc()
                .stream()
                .map(evaluation -> {

                    double rate;

                    if (evaluation.getScore() == null) {

                        rate = 100;

                    } else {

                        rate = (1 - evaluation.getScore()) * 100;

                    }

                    return new HallucinationPointDTO(

                            evaluation
                                    .getCreatedAt()
                                    .format(formatter),

                            Math.round(rate * 100.0) / 100.0

                    );

                })
                .toList();

    }

}