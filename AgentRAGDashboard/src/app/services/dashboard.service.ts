import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';


export interface HallucinationStats {

  hallucinationRate:number;

  averageScore:number;

  totalEvaluations:number;

}


@Injectable({
  providedIn:'root'
})
export class DashboardService {


  private apiUrl =
    'http://localhost:8080/api/dashboard';



  constructor(
    private http:HttpClient
  ){}



  getHallucinationStats()
  :Observable<HallucinationStats>{


    return this.http.get<HallucinationStats>(
      `${this.apiUrl}/hallucination`
    );


  }
  getHallucinationChart() {

  return this.http.get<any[]>(
    `${this.apiUrl}/hallucination-chart`
  );

}


}