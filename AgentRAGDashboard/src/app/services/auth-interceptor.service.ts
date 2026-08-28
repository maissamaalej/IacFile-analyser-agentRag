import { Injectable } from '@angular/core';
import {
  HttpInterceptor,
  HttpRequest,
  HttpHandler
} from '@angular/common/http';


@Injectable()
export class AuthInterceptor implements HttpInterceptor {


  intercept(
    req: HttpRequest<any>,
    next: HttpHandler
  ) {


    const token =
      localStorage.getItem('token');


    if(token){


      const request = req.clone({

        setHeaders:{
          Authorization:
            `Bearer ${token}`
        }

      });


      return next.handle(request);

    }


    return next.handle(req);

  }

}