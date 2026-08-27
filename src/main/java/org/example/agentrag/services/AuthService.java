package org.example.agentrag.services;

import lombok.RequiredArgsConstructor;
import org.example.agentrag.Dto.AuthResponse;
import org.example.agentrag.Dto.SigninRequest;
import org.example.agentrag.Dto.SignupRequest;
import org.springframework.stereotype.Service;


public interface AuthService {
    public AuthResponse signup(SignupRequest request);
    public AuthResponse signin(SigninRequest request);
}
