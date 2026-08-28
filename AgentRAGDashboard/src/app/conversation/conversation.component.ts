import { Component,OnInit } from '@angular/core';
import { ChatService } from '../services/chat.service';
import { ChatMessageService } from '../services/chat-message.service';
import { Chat } from '../interfaces/chat';
import { ActivatedRoute } from '@angular/router';

export type ResourceStatus = 'compliant' | 'warning' | 'critical';

export interface ResourceResult {
  id: string;
  status: ResourceStatus;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  text?: string;
  file?: { name: string };
  resources?: ResourceResult[];
  explanation?: string;
  showFixAction?: boolean;
}

@Component({
  selector: 'app-conversation',
  templateUrl: './conversation.component.html',
  styleUrls: ['./conversation.component.css']
})
export class ConversationComponent implements OnInit {

  draftMessage = '';

  pendingFile: File | null = null;

  currentChatId: number | null = null;

  messages: ChatMessage[] = [];

  isProcessing = false;

  constructor(
    private chatService: ChatService,
    private chatMessageService: ChatMessageService,
    private route: ActivatedRoute
  ) {}

 ngOnInit(){

    this.route.queryParams.subscribe(params=>{


        // Nouvelle conversation
        if(params['new']){

            this.currentChatId = null;

            this.messages = [];

            this.draftMessage = '';

            this.pendingFile = null;

            return;

        }



        const id=params['chatId'];


        if(id){

            this.currentChatId = +id;

            this.loadMessages();

        }


    });

}
loadMessages(){

    if(this.currentChatId==null){

        return;

    }

    this.chatMessageService
    .getMessages(this.currentChatId)
    .subscribe({

        next:(messages:any[])=>{

            this.messages = messages.map(m=>({

                role:m.sender==="USER"
                    ? "user"
                    : "assistant",

                text:m.content

            }));

        },

        error:err=>{

            console.error(err);

        }

    });

}

  sendMessage(): void {

    if ((!this.draftMessage.trim() && !this.pendingFile) || this.isProcessing) {
      return;
    }

    const prompt = this.draftMessage;

    // afficher immédiatement le message utilisateur
    this.messages.push({
      role: 'user',
      text: prompt
    });

    this.draftMessage = '';

    this.isProcessing = true;

    // première conversation
    if (this.currentChatId === null) {
      this.createChat(prompt);
      return;
    }

    this.sendPromptToAgent(prompt);
  }

  createChat(firstMessage: string): void {

    const request = {
      title: firstMessage.substring(0, 40)
    };

    this.chatService.createChat(request).subscribe({

      next: (chat: Chat) => {

        this.currentChatId = chat.id;

        console.log('Chat créé :', chat);

        this.sendPromptToAgent(firstMessage);

      },

      error: err => {

        this.isProcessing = false;

        console.error(err);

      }

    });

  }

  sendPromptToAgent(message: string): void {

    if (this.currentChatId == null) {
      this.isProcessing = false;
      return;
    }

    this.chatMessageService.sendMessage(

      this.currentChatId,

      {
        message: message
      }

    ).subscribe({

      next: response => {
         console.log("Response =", response);

        this.messages.push({

          role: 'assistant',

          text: response.answer,

          resources: response.resources,

          explanation: response.explanation,

          showFixAction: response.showFixAction

        });

        this.isProcessing = false;

      },

      error: err => {

        console.error("Erreur AgentRAG", err);

        this.messages.push({

          role: 'assistant',

          text: 'An error occurred while processing your request.'

        });

        this.isProcessing = false;

      }

    });

  }

  onFileSelected(event: Event): void {

    const input = event.target as HTMLInputElement;

    if (input.files && input.files.length > 0) {

      this.pendingFile = input.files[0];

    }

  }

  removePendingFile(): void {

    this.pendingFile = null;

  }

  requestFix(msg: ChatMessage): void {

    console.log(msg);

  }

  statusClass(status: ResourceStatus): string {

    return {

      compliant: 'ok',

      warning: 'warn',

      critical: 'crit'

    }[status];

  }

  statusLabel(status: ResourceStatus): string {

    return {

      compliant: 'Conforme',

      warning: 'Moyenne',

      critical: 'Critique'

    }[status];

  }

  handleEnter(event: Event){

  const keyboardEvent = event as KeyboardEvent;


  if(keyboardEvent.shiftKey){

    return;

  }


  keyboardEvent.preventDefault();


  this.sendMessage();

}

}