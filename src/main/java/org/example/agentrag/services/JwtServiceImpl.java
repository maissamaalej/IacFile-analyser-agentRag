package org.example.agentrag.services;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import javax.crypto.SecretKey;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.stereotype.Service;

import java.security.Key;
import java.util.Date;
import java.util.HashMap;

@Service
public class JwtServiceImpl implements JwtService {

    @Value("${jwt.secret}")
    private String SECRET_KEY;



    @Value("${jwt.expiration}")
    private long jwtExpiration;




    public String generateToken(
            UserDetails userDetails
    ){

        return Jwts.builder()

                .subject(
                        userDetails.getUsername()
                )

                .issuedAt(
                        new Date()
                )

                .expiration(
                        new Date(
                                System.currentTimeMillis()
                                        + jwtExpiration
                        )
                )

                .signWith(
                        getSigningKey()
                )

                .compact();

    }




    public String extractUsername(
            String token
    ){

        return extractAllClaims(token)
                .getSubject();

    }




    public boolean isValidToken(
            String token,
            UserDetails userDetails
    ){


        String username =
                extractUsername(token);



        return username.equals(
                userDetails.getUsername()
        )
                &&
                !isTokenExpired(token);

    }





    private boolean isTokenExpired(
            String token
    ){

        return extractExpiration(token)
                .before(
                        new Date()
                );

    }





    private Date extractExpiration(
            String token
    ){

        return extractAllClaims(token)
                .getExpiration();

    }





    private Claims extractAllClaims(
            String token
    ){

        return Jwts.parser()

                .verifyWith(
                        getSigningKey()
                )

                .build()

                .parseSignedClaims(token)

                .getPayload();

    }



    private SecretKey getSigningKey(){

        return Keys.hmacShaKeyFor(
                SECRET_KEY.getBytes()
        );

    }

}
