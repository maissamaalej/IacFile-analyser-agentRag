package org.example.agentrag.Controller;

import lombok.AllArgsConstructor;
import org.example.agentrag.Dto.AuthResponse;
import org.example.agentrag.Dto.SigninRequest;
import org.example.agentrag.Dto.SignupRequest;
import org.example.agentrag.services.AuthService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;


@RestController
@RequestMapping("/api/auth")
@AllArgsConstructor
public class AuthController {
    private final AuthService authService;

    @PostMapping("/signup")
    public ResponseEntity<AuthResponse> signup(
            @RequestBody SignupRequest request) {

        return ResponseEntity.ok(authService.signup(request));
    }

    @PostMapping("/signin")
    public ResponseEntity<AuthResponse> signin(
            @RequestBody SigninRequest request) {

        return ResponseEntity.ok(authService.signin(request));
    }
}
