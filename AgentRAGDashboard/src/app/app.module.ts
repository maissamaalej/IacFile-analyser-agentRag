import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { DashboardComponent } from './dashboard/dashboard.component';
// import { ShellComponent } from './shell/shell.component';
import { ConversationComponent } from './conversation/conversation.component';
import { LandingComponent } from './landing/landing.component';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { AuthComponent } from './auth/auth.component';
import { HTTP_INTERCEPTORS, HttpClientModule } from '@angular/common/http';
import { ShellComponent } from './shell/shell.component';
import { ScoreCardComponent } from './components/score-card/score-card.component';
import { HallucinationChartComponent } from './components/hallucination-chart/hallucination-chart.component';
import { FeedbackChartComponent } from './components/feedback-chart/feedback-chart.component';
import { AuthInterceptor } from './services/auth-interceptor.service';
 
@NgModule({
  declarations: [
    AppComponent,
    DashboardComponent,
    // ShellComponent,
    ConversationComponent,
    LandingComponent,
    AuthComponent,
    ShellComponent,
    ScoreCardComponent,
    HallucinationChartComponent,
    FeedbackChartComponent
    
  ],
  imports: [
    BrowserModule,
    AppRoutingModule,
    FormsModule,
    CommonModule,
    RouterModule,
    ReactiveFormsModule,
    HttpClientModule
  ],
  providers: [
  {
    provide: HTTP_INTERCEPTORS,
    useClass: AuthInterceptor,
    multi: true
  }
],
  bootstrap: [AppComponent]
})
export class AppModule { }
