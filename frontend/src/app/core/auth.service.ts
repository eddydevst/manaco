import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { ApiService } from './api.service';

export interface Usuario {
  id_usuario: number;
  nombre: string;
  correo: string;
  id_sucursal: number | null;
  sucursal: string | null;
  roles: string[];
  permisos: string[];
}

export const TOKEN_KEY = 'manaco_token';
const USER_KEY = 'manaco_usuario';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private api = inject(ApiService);
  private router = inject(Router);

  readonly usuario = signal<Usuario | null>(this.leer());
  readonly autenticado = computed(() => !!this.usuario());

  private leer(): Usuario | null {
    try {
      return localStorage.getItem(TOKEN_KEY) ? JSON.parse(localStorage.getItem(USER_KEY) || 'null') : null;
    } catch {
      return null;
    }
  }

  async login(correo: string, password: string): Promise<void> {
    const r = await this.api.post<{ access_token: string; usuario: Usuario }>('/api/auth/login', { correo, password });
    localStorage.setItem(TOKEN_KEY, r.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(r.usuario));
    this.usuario.set(r.usuario);
  }

  /** Vuelve a leer los permisos del usuario (por si un administrador los cambió). */
  async refrescar(): Promise<void> {
    const u = await this.api.get<Usuario>('/api/auth/me');
    localStorage.setItem(USER_KEY, JSON.stringify(u));
    this.usuario.set(u);
  }

  cerrarSesion(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    this.usuario.set(null);
    this.router.navigate(['/login']);
  }

  puede(permiso: string): boolean {
    return !!this.usuario()?.permisos.includes(permiso);
  }

  /** Sucursal fija del usuario (cajeros) o null si puede ver todas. */
  sucursalFija(): number | null {
    return this.usuario()?.id_sucursal ?? null;
  }
}
