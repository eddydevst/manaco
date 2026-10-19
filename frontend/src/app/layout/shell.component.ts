import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { AuthService } from '../core/auth.service';
import { MENU } from '../core/nav';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="shell">
      <aside class="side" [class.open]="menuAbierto()">
        <div class="side-top">
          <div class="brand"><span class="logo">M</span><span class="bt"><b>MANACO</b><small>Gestión comercial</small></span></div>
          <button class="menu-btn" type="button" (click)="menuAbierto.set(!menuAbierto())" [attr.aria-expanded]="menuAbierto()">
            {{ menuAbierto() ? 'Cerrar' : 'Menú' }}
          </button>
        </div>
        <nav class="nav" aria-label="Módulos">
          @for (g of menu(); track g.grupo) {
            <div class="ng">
              <span class="ng-t">{{ g.grupo }}</span>
              @for (i of g.items; track i.ruta) {
                <a class="nv" [routerLink]="['/', i.ruta]" routerLinkActive="on" ariaCurrentWhenActive="page">{{ i.etiqueta }}</a>
              }
            </div>
          }
        </nav>
        <div class="me">
          <span class="av">{{ iniciales() }}</span>
          <span class="me-t"><b>{{ auth.usuario()?.nombre }}</b>
            <small>{{ auth.usuario()?.roles?.join(', ') }}@if (auth.usuario()?.sucursal) { · {{ auth.usuario()?.sucursal }} }</small></span>
        </div>
        <div class="side-actions"><button class="lk" type="button" (click)="auth.cerrarSesion()">Cerrar sesión</button></div>
      </aside>
      <main class="main"><router-outlet></router-outlet></main>
    </div>`,
})
export class ShellComponent implements OnInit {
  auth = inject(AuthService);
  private router = inject(Router);
  menuAbierto = signal(false);
  menu = computed(() => {
    this.auth.usuario();
    return MENU.map((g) => ({ ...g, items: g.items.filter((i) => this.auth.puede(i.permiso)) })).filter((g) => g.items.length);
  });
  iniciales = computed(() => (this.auth.usuario()?.nombre || '').split(/\s+/).map((x) => x[0]).slice(0, 2).join('').toUpperCase());

  ngOnInit() {
    this.auth.refrescar().catch(() => {});
    this.router.events.pipe(filter((e) => e instanceof NavigationEnd)).subscribe(() => this.menuAbierto.set(false));
  }
}

@Component({
  selector: 'app-sin-acceso',
  standalone: true,
  template: `<div class="card"><div class="empty"><h2>No tienes acceso a este módulo</h2>
    <p>Tu rol no incluye este permiso. Pide a un administrador que lo asigne en Usuarios y roles.</p></div></div>`,
})
export class SinAccesoComponent {}
