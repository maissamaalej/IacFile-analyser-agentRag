import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Chat } from '../interfaces/chat';

export interface CreateChatRequest {
  title: string;
}



@Injectable({
  providedIn: 'root'
})
export class ChatService {

  private apiUrl = '/api/Chat';

  constructor(private http: HttpClient) {}

  createChat(request: CreateChatRequest): Observable<Chat> {
    return this.http.post<Chat>(this.apiUrl, request);
  }

   getChats(): Observable<Chat[]> {

    return this.http.get<Chat[]>(
      this.apiUrl
    );

  }
  deleteChat(id:number){

  return this.http.delete<void>(
    `${this.apiUrl}/delete/${id}`
  );

}
togglePin(chatId: number) {
  return this.http.put<Chat>(
    `${this.apiUrl}/pin/${chatId}`,
    {}
  );
}

}