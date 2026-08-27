package org.example.agentrag.Repository;

import org.example.agentrag.model.HallucinationEvaluation;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface HallucinationEvaluationRepo extends JpaRepository<HallucinationEvaluation, Long> {

    long countByGroundedFalse();



    @Query("""
        SELECT AVG(h.score)
        FROM HallucinationEvaluation h
    """)
    Double averageScore();

    List<HallucinationEvaluation> findAllByOrderByCreatedAtAsc();
}