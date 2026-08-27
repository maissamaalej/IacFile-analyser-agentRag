package org.example.agentrag.services;


import lombok.RequiredArgsConstructor;
import org.example.agentrag.Repository.UserRepo;

import org.example.agentrag.model.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;


@Service
@RequiredArgsConstructor
public class UserServiceImpl implements IUserService {


    private final UserRepo userRepo;



    @Override
    public UserDetails loadUserByUsername(String email) {


        User user = userRepo.findByEmail(email)
                .orElseThrow(
                        () -> new UsernameNotFoundException(
                                "Utilisateur non trouvé"
                        )
                );


        return org.springframework.security.core.userdetails.User
                .builder()
                .username(user.getEmail())
                .password(user.getPassword())
                .roles(user.getRole().name())
                .disabled(!user.isActive())
                .build();
    }
}