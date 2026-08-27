package org.example.agentrag.services;

import org.example.agentrag.model.HallucinationEvaluation;

public interface HallucinationEvaluationService  {
    HallucinationEvaluation saveEvaluation(
            Long chatId,
            String email,
            String question,
            String answer,
            Boolean grounded,
            Double score
    );
}
