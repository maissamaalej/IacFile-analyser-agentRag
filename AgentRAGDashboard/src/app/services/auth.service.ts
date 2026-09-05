import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { AuthResponse } from '../interfaces/auth-response';
import { SigninRequest } from '../interfaces/signin-request';
import { SignupRequest } from '../interfaces/signup-request';
import { Router } from '@angular/router';


@Injectable({
  providedIn: 'root'
})
export class AuthService {


  private apiUrl = '/api/auth';


  constructor(
    private http: HttpClient,
    private router: Router
  ) {}



  signup(request: SignupRequest): Observable<AuthResponse> {

    return this.http.post<AuthResponse>(
      `${this.apiUrl}/signup`,
      request
    ).pipe(

      tap(response => {

        localStorage.setItem(
          'token',
          response.token
        );

        localStorage.setItem(
          'user',
          JSON.stringify(response.user)
        );

      })

    );

  }



  signin(request: SigninRequest): Observable<AuthResponse> {


    return this.http.post<AuthResponse>(
      `${this.apiUrl}/signin`,
      request
    ).pipe(

      tap(response => {


        localStorage.setItem(
          'token',
          response.token
        );


        localStorage.setItem(
          'user',
          JSON.stringify(response.user)
        );


      })

    );


  }



  logout(){

    localStorage.removeItem('token');

    localStorage.removeItem('user');

    this.router.navigate(['/login']);

  }


}