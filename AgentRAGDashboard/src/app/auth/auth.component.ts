import { Component } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { AuthService } from '../services/auth.service';


@Component({
  selector: 'app-auth',
  templateUrl: './auth.component.html',
  styleUrl: './auth.component.css'
})
export class AuthComponent {


  activeTab = 'login';
  showPassword = false;


  loginForm!: FormGroup;
  signupForm!: FormGroup;


  constructor(
     private route: ActivatedRoute,
  private router: Router,
  private fb: FormBuilder,
  private authService: AuthService
  ){


    this.route.data.subscribe(data=>{
      this.activeTab = data['mode'];
    });


    // LOGIN FORM

    this.loginForm = this.fb.group({

      email:[
        '',
        [
          Validators.required,
          Validators.email
        ]
      ],

      password:[
        '',
        [
          Validators.required,
          Validators.minLength(6)
        ]
      ]

    });



    // SIGNUP FORM

    this.signupForm = this.fb.group({

      firstName:[
        '',
        Validators.required
      ],

      lastName:[
        '',
        Validators.required
      ],


      email:[
        '',
        [
          Validators.required,
          Validators.email
        ]
      ],


      password:[
        '',
        [
          Validators.required,
          Validators.minLength(6)
        ]
      ]

    });

  }



  changeTab(tab:string){

    this.activeTab = tab;


    if(tab === 'login'){
      this.router.navigate(['/login']);
    }
    else{
      this.router.navigate(['/signup']);
    }

  }



  togglePassword(){
    this.showPassword = !this.showPassword;
  }



  login() {

  if (this.loginForm.invalid) {
    this.loginForm.markAllAsTouched();
    return;
  }

  this.authService.signin(this.loginForm.value).subscribe({

    next: (response) => {

      console.log('Connexion réussie', response);

      localStorage.setItem('token', response.token);

      this.router.navigate(['/dashboard']);

    },

    error: (err) => {

      console.error(err);

      alert(err.error?.message || 'Email ou mot de passe incorrect');

    }

  });

}



  signup() {

  if (this.signupForm.invalid) {
    this.signupForm.markAllAsTouched();
    return;
  }

  this.authService.signup(this.signupForm.value).subscribe({

    next: (response) => {

      console.log('Compte créé', response);

      // Sauvegarder le JWT
      localStorage.setItem('token', response.token);

      this.router.navigate(['/login']);

    },

    error: (err) => {

      console.error(err);

      alert(err.error?.message || 'Erreur lors de l\'inscription');

    }

  });

}


}