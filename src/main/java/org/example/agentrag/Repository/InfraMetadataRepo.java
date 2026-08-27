package org.example.agentrag.Repository;

import org.example.agentrag.model.InfraMetadata;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface InfraMetadataRepo extends JpaRepository<InfraMetadata,Long> {
}
