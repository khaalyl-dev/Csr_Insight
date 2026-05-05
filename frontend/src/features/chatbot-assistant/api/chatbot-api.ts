import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface ChatbotRequest {
  prompt: string;
  model?: string;
}

export interface ChatbotResponse {
  model: string;
  response: string;
}

@Injectable({ providedIn: 'root' })
export class ChatbotApi {
  private http = inject(HttpClient);

  chat(payload: ChatbotRequest): Observable<ChatbotResponse> {
    return this.http.post<ChatbotResponse>('/api/chatbot/chat', payload);
  }
}
