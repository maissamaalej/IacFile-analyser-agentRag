package org.example.agentrag.Config;


import lombok.RequiredArgsConstructor;

import org.example.agentrag.services.IUserService;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import org.springframework.http.HttpMethod;

import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.ProviderManager;

import org.springframework.security.authentication.dao.DaoAuthenticationProvider;

import org.springframework.security.config.annotation.web.builders.HttpSecurity;

import org.springframework.security.config.http.SessionCreationPolicy;

import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;

import org.springframework.security.web.SecurityFilterChain;

import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;



@Configuration
@RequiredArgsConstructor
public class SecurityConfig {


    private final JwtAuthenticationFilter jwtAuthenticationFilter;


    private final IUserService userService;



    @Bean
    public SecurityFilterChain securityFilterChain(
            HttpSecurity http
    ) throws Exception {


        return http

                .csrf(csrf ->
                        csrf.disable()
                )

                .cors(cors -> {})


                .authorizeHttpRequests(auth -> auth


                        .requestMatchers(
                                "/api/auth/**"
                        )
                        .permitAll()


                        .requestMatchers(
                                HttpMethod.OPTIONS,
                                "/**"
                        )
                        .permitAll()


                        .anyRequest()
                        .authenticated()

                )


                .sessionManagement(session ->
                        session.sessionCreationPolicy(
                                SessionCreationPolicy.STATELESS
                        )
                )


                .addFilterBefore(
                        jwtAuthenticationFilter,
                        UsernamePasswordAuthenticationFilter.class
                )


                .build();

    }





    @Bean
    public PasswordEncoder passwordEncoder(){

        return new BCryptPasswordEncoder();

    }






    @Bean
    public AuthenticationManager authenticationManager(
            PasswordEncoder passwordEncoder
    ){


        DaoAuthenticationProvider provider =
                new DaoAuthenticationProvider(
                        userService
                );


        provider.setPasswordEncoder(
                passwordEncoder
        );


        return new ProviderManager(
                provider
        );

    }

}