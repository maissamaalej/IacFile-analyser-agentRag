package org.example.agentrag.services;

import lombok.AllArgsConstructor;
import org.example.agentrag.Dto.AuthResponse;
import org.example.agentrag.Dto.SigninRequest;
import org.example.agentrag.Dto.SignupRequest;
import org.example.agentrag.Repository.UserRepo;

import org.example.agentrag.model.User;
import org.example.agentrag.model.UserRole;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
@AllArgsConstructor
public class AuthServiceImpl implements AuthService{


    private final UserRepo userRepo;


    private final PasswordEncoder passwordEncoder;


    private final JwtService jwtService;


    private final AuthenticationManager authenticationManager;





    @Override
    public AuthResponse signup(
            SignupRequest request
    ){


        if(userRepo.findByEmail(request.getEmail())
                .isPresent()){

            throw new RuntimeException(
                    "Email déjà utilisé"
            );
        }



        User user = new User();


        user.setEmail(
                request.getEmail()
        );


        user.setFirstName(
                request.getFirstName()
        );


        user.setLastName(
                request.getLastName()
        );



        // Hash password

        user.setPassword(
                passwordEncoder.encode(
                        request.getPassword()
                )
        );

        user.setRole(UserRole.USER);

        userRepo.save(user);



        String token =
                jwtService.generateToken(
                        convertToUserDetails(user)
                );



        return new AuthResponse(token);

    }



    @Override
    public AuthResponse signin(
            SigninRequest request
    ){



        authenticationManager.authenticate(

                new UsernamePasswordAuthenticationToken(

                        request.getEmail(),

                        request.getPassword()

                )

        );



        User user =
                userRepo.findByEmail(
                                request.getEmail()
                        )
                        .orElseThrow(
                                () -> new RuntimeException(
                                        "Utilisateur introuvable"
                                )
                        );




        String token =
                jwtService.generateToken(
                        convertToUserDetails(user)
                );



        return new AuthResponse(token);

    }


    private org.springframework.security.core.userdetails.User

    convertToUserDetails(User user){



        return new org.springframework.security.core.userdetails.User(

                user.getEmail(),

                user.getPassword(),

                user.isActive(),

                true,

                true,

                true,

                java.util.List.of()

        );

    }

}
