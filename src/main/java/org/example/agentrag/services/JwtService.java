package org.example.agentrag.services;

import org.springframework.security.core.userdetails.UserDetails;

public interface JwtService {
    public String generateToken(UserDetails userDetails);
    public String extractUsername(
            String token
    );
    public boolean isValidToken(
            String token,
            UserDetails userDetails
    );
}
