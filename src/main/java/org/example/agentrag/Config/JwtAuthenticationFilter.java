package org.example.agentrag.Config;


import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;


import lombok.RequiredArgsConstructor;


import org.example.agentrag.services.IUserService;
import org.example.agentrag.services.JwtService;


import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;

import org.springframework.security.core.context.SecurityContextHolder;

import org.springframework.security.core.userdetails.UserDetails;

import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;

import org.springframework.stereotype.Component;

import org.springframework.util.StringUtils;

import org.springframework.web.filter.OncePerRequestFilter;


import java.io.IOException;



@Component
@RequiredArgsConstructor
public class JwtAuthenticationFilter
        extends OncePerRequestFilter {



    private final JwtService jwtService;


    private final IUserService userService;



    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain
    )
            throws ServletException, IOException {


        String authHeader =
                request.getHeader("Authorization");



        String jwt = null;

        String email = null;


        if(StringUtils.hasText(authHeader)
                &&
                authHeader.startsWith("Bearer ")) {



            jwt = authHeader.substring(7);



            try {

                email =
                        jwtService.extractUsername(jwt);


            } catch(Exception e) {


                System.out.println(
                        "Erreur extraction JWT : "
                                + e.getMessage()
                );

            }

        }



        if(email != null
                &&
                SecurityContextHolder
                        .getContext()
                        .getAuthentication() == null) {



            UserDetails userDetails =
                    userService
                            .loadUserByUsername(email);



            if(jwtService.isValidToken(
                    jwt,
                    userDetails
            )) {



                UsernamePasswordAuthenticationToken authentication =


                        new UsernamePasswordAuthenticationToken(

                                userDetails,

                                null,

                                userDetails.getAuthorities()

                        );




                authentication.setDetails(

                        new WebAuthenticationDetailsSource()
                                .buildDetails(request)

                );




                SecurityContextHolder
                        .getContext()
                        .setAuthentication(
                                authentication
                        );

            }


        }


        filterChain.doFilter(
                request,
                response
        );


    }

}