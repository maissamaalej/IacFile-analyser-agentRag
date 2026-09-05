import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface SendMessageRequest {
  message: string;
}

export interface AgentResponse {
  answer: string;
  resources?: any[];
  explanation?: string;
  showFixAction?: boolean;
}

@Injectable({
  providedIn: 'root'
})
export class ChatMessageService {

  private apiUrl = '/api/chatMessage';

  constructor(private http: HttpClient) {}

  sendMessage(
    chatId: number,
    request: SendMessageRequest
  ): Observable<AgentResponse> {

    return this.http.post<AgentResponse>(
      `${this.apiUrl}/${chatId}/messages`,
      request
    );

  }
  getMessages(chatId:number){

  return this.http.get<any[]>(

    `${this.apiUrl}/${chatId}/messages`

  );

}

}