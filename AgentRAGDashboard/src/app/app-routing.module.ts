import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { DashboardComponent } from './dashboard/dashboard.component';
import { LandingComponent } from './landing/landing.component';
import { AuthComponent } from './auth/auth.component';
import { ShellComponent } from './shell/shell.component';
import { ConversationComponent } from './conversation/conversation.component';


const routes: Routes = [

  // Landing page
  {
    path: '',
    component: LandingComponent
  },


  // Authentication
  {
    path: 'login',
    component: AuthComponent,
    data: {
      mode: 'login'
    }
  },

  {
    path: 'signup',
    component: AuthComponent,
    data: {
      mode: 'signup'
    }
  },


  // Application with sidebar/navbar
  {
    path: '',
    component: ShellComponent,
    children: [

      {
        path: 'dashboard',
        component: DashboardComponent
      },
      {
        path: 'chat',
        component: ConversationComponent
      },

      {
        path: '',
        redirectTo: 'dashboard',
        pathMatch: 'full'
      }

    ]
  },


  // Unknown routes
  {
    path: '**',
    redirectTo: ''
  }

];


@NgModule({
  imports: [
    RouterModule.forRoot(routes)
  ],
  exports: [
    RouterModule
  ]
})
export class AppRoutingModule {}