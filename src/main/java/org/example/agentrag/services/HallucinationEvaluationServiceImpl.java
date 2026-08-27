package org.example.agentrag.services;

import lombok.AllArgsConstructor;
import org.example.agentrag.Repository.ChatRepo;
import org.example.agentrag.Repository.HallucinationEvaluationRepo;
import org.example.agentrag.Repository.UserRepo;
import org.example.agentrag.model.Chat;
import org.example.agentrag.model.HallucinationEvaluation;
import org.example.agentrag.model.User;
import org.springframework.stereotype.Service;

@Service
@AllArgsConstructor
public class HallucinationEvaluationServiceImpl  implements HallucinationEvaluationService{

    private final HallucinationEvaluationRepo repository;
    private final ChatRepo chatRepo;
    private final UserRepo userRepo;

    @Override
    public HallucinationEvaluation saveEvaluation(
            Long chatId,
            String email,
            String question,
            String answer,
            Boolean grounded,
            Double score
    ) {

        System.out.println("===== SAVE HALLUCINATION =====");
        System.out.println("chatId = " + chatId);
        System.out.println("email = " + email);
        System.out.println("question = " + question);
        System.out.println("score = " + score);
        System.out.println("grounded = " + grounded);


        User user = userRepo.findByEmail(email)
                .orElseThrow(() -> new RuntimeException("User not found"));


        Chat chat = chatRepo.findById(chatId)
                .orElseThrow(() -> new RuntimeException("Chat not found"));


        HallucinationEvaluation evaluation =
                HallucinationEvaluation.builder()
                        .chat(chat)
                        .user(user)
                        .question(question)
                        .answer(answer)
                        .grounded(grounded)
                        .score(score)
                        .build();


        return repository.save(evaluation);
    }
}
