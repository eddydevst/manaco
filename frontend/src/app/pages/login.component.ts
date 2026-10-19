import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../core/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="login">
      <section class="login-art">
        <div class="brand" style="padding:0"><span class="logo">M</span><span class="bt"><b>MANACO</b><small>Sistema integral de gestión comercial</small></span></div>
        <h1>De la venta diaria a la decisión gerencial</h1>
        <p>Productos, compras, inventario por sucursal y punto de venta en un solo lugar. Cada operación alimenta los indicadores y los pronósticos de demanda.</p>
        <ol class="flow">
          <li><span>01</span>Operaciones comerciales</li><li><span>02</span>Datos estructurados</li><li><span>03</span>Indicadores y reportes</li>
          <li><span>04</span>Análisis de tendencias</li><li><span>05</span>Pronósticos</li><li><span>06</span>Decisiones gerenciales</li>
        </ol>
      </section>
      <section class="login-form">
        <form class="card login-card" (ngSubmit)="entrar()">
          <div><h2 style="font-size:22px">Ingresar</h2><p class="muted" style="margin-top:4px">Usa tu correo y contraseña.</p></div>
          <label class="field" for="lg-c"><span>Correo</span>
            <input id="lg-c" name="correo" type="email" [(ngModel)]="correo" autocomplete="username" required></label>
          <label class="field" for="lg-p"><span>Contraseña</span>
            <input id="lg-p" name="password" type="password" [(ngModel)]="password" autocomplete="current-password" required></label>
          <button class="btn btn-p btn-lg" type="submit" [disabled]="cargando || !correo || !password">
            @if (cargando) { <span class="spin"></span> } Ingresar
          </button>
        </form>
      </section>
    </div>`,
})
export class LoginComponent {
  private auth = inject(AuthService);
  private router = inject(Router);
  correo = '';
  password = '';
  cargando = false;

  async entrar() {
    this.cargando = true;
    try {
      await this.auth.login(this.correo, this.password);
      this.router.navigate(['/']);
    } catch {
      /* el error ya se mostró */
    } finally {
      this.cargando = false;
    }
  }
}
