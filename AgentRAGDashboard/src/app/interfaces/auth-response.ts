export interface AuthResponse {

  token: string;

  user: {
    id: number;
    firstName: string;
    lastName: string;
    email: string;
    role: string;
  };

}