import { Component, OnInit } from '@angular/core';
import { AuthService } from '../services/auth.service';
import { NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs/operators';

import { ChatService } from '../services/chat.service';
import { Chat } from '../interfaces/chat';


@Component({
  selector: 'app-shell',
  templateUrl: './shell.component.html',
  styleUrls: ['./shell.component.css']
})
export class ShellComponent implements OnInit {


  currentChatId: number | null = null;

  isChatPage = false;


  historyChats: Chat[] = [];


  pinnedChats: Chat[] = [];
  

  activeMenuChatId:number | null = null;



  constructor(
    private authService: AuthService,
    private router: Router,
    private chatService: ChatService
  ){


    this.router.events
      .pipe(
        filter(event => event instanceof NavigationEnd)
      )
      .subscribe((event:any)=>{


        this.isChatPage =
          event.urlAfterRedirects.startsWith('/chat');


      });


  }



  ngOnInit(){


    this.loadHistory();


  }


  toggleChatMenu(chatId:number){

  if(this.activeMenuChatId === chatId){
    this.activeMenuChatId = null;
  }
  else{
    this.activeMenuChatId = chatId;
  }

}
pinChat(chat: Chat) {

  this.chatService.togglePin(chat.id).subscribe({

    next: () => {

      // Recharge les listes depuis la base
      this.loadHistory();

      this.activeMenuChatId = null;

    },

    error: err => {
      console.error("Pin error", err);
    }

  });

}

deleteChat(chat:Chat){


  this.chatService
    .deleteChat(chat.id)
    .subscribe({

      next:()=>{


        this.historyChats =
          this.historyChats.filter(
            c=>c.id !== chat.id
          );


        this.activeMenuChatId=null;


      },


      error:err=>{

        console.error(
          "Delete error",
          err
        );

      }


    });


}




  loadHistory() {

  this.chatService.getChats().subscribe({

    next: (chats: Chat[]) => {

      this.pinnedChats = chats.filter(chat => chat.pinned);

      this.historyChats = chats.filter(chat => !chat.pinned);

    },

    error: err => console.error(err)

  });

}




  newConversation(){

    this.currentChatId = null;

    this.router.navigate(
      ['/chat'],
      {
        queryParams:{
          new:true
        }
      }
    );

}





  addChatToHistory(chat:Chat){


    this.historyChats.unshift(
      chat
    );


    this.currentChatId = chat.id;


  }




  onActivate(component:any){


    if(component.chatCreated){


      component.chatCreated.subscribe(

        (chat:Chat)=>{


          this.addChatToHistory(chat);


        }

      );


    }


  }





  logout(){


    this.authService.logout();


  }
  openChat(chat: Chat){

    this.currentChatId = chat.id;

    this.router.navigate(
      ['/chat'],
      {
        queryParams:{
          chatId:chat.id
        }
      }
    );

}



}