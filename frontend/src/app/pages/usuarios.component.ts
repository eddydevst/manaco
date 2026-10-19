import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { ToastService } from '../core/toast.service';
import { ModalComponent } from '../shared/graficos';

@Component({
  selector: 'app-usuarios',
  standalone: true,
  imports: [FormsModule, ModalComponent],
  template: `
    <header class="ph">
      <div><div class="ph-t"><h1>Usuarios y roles</h1></div>
        <p>{{ tab === 'usuarios' ? 'Cuentas, rol asignado y restricción por sucursal. Los permisos se validan en cada acción.' : 'Marca qué puede hacer cada rol. El rol Administrador siempre conserva todos los permisos.' }}</p></div>
      <div class="ph-a">@if (tab === 'usuarios') { <button class="btn btn-p" type="button" (click)="editar(null)">Nuevo usuario</button> }
        @else { <button class="btn btn-p" type="button" (click)="nuevoRol = { nombre: '', descripcion: '' }">Nuevo rol</button> }</div>
    </header>
    <section class="card">
      <div class="tabs" role="tablist">
        <button class="tab" role="tab" type="button" [attr.aria-selected]="tab === 'usuarios'" (click)="tab = 'usuarios'">Usuarios</button>
        <button class="tab" role="tab" type="button" [attr.aria-selected]="tab === 'roles'" (click)="tab = 'roles'">Roles y permisos</button>
      </div>
      @if (tab === 'usuarios') {
        <div class="tw"><table class="t"><thead><tr><th>Nombre</th><th>Correo</th><th>Rol</th><th>Sucursal</th><th>Estado</th><th></th></tr></thead>
          <tbody>@for (u of usuarios; track u.id_usuario) {
            <tr><td class="b">{{ u.nombre }}</td><td class="mono sm">{{ u.correo }}</td><td>{{ u.rol || '—' }}</td><td>{{ u.sucursal || 'Todas' }}</td>
              <td><span class="badge {{ u.estado === 'ACTIVO' ? 'b-ok' : 'b-mut' }}">{{ u.estado === 'ACTIVO' ? 'Activo' : 'Inactivo' }}</span></td>
              <td><button class="btn btn-sm" type="button" (click)="editar(u)">Editar</button></td></tr>
          }</tbody></table></div>
      } @else {
        <div class="tw"><table class="t perm-tbl">
          <thead><tr><th>Módulo</th><th>Acción</th>@for (r of roles; track r.id_rol) { <th style="text-align:center">{{ r.nombre }}<br><span class="sm muted">{{ r.usuarios }} usuarios</span></th> }</tr></thead>
          <tbody>@for (p of permisos; track p.codigo) {
            <tr><td class="b">{{ p.recurso }}</td><td class="muted">{{ p.descripcion }} <span class="mono sm">{{ p.codigo }}</span></td>
              @for (r of roles; track r.id_rol) {
                <td><input type="checkbox" [checked]="r.permisos.includes(p.codigo)" [disabled]="r.es_sistema || guardando" (change)="alternar(r, p.codigo, $any($event.target).checked)"
                  [attr.aria-label]="r.nombre + ': ' + p.recurso + ', ' + p.descripcion"></td>
              }</tr>
          }</tbody></table></div>
      }
    </section>

    @if (form) {
      <app-modal [titulo]="form.id_usuario ? 'Editar usuario' : 'Nuevo usuario'" (cerrar)="form = null">
        <form class="form-grid" (ngSubmit)="guardar()">
          <label class="field" for="us-n"><span>Nombre</span><input id="us-n" name="nombre" [(ngModel)]="form.nombre" required></label>
          <label class="field" for="us-c"><span>Correo</span><input id="us-c" name="correo" type="email" [(ngModel)]="form.correo" required></label>
          <label class="field" for="us-r"><span>Rol</span><select id="us-r" name="rol" [(ngModel)]="form.id_rol">
            @for (r of roles; track r.id_rol) { <option [ngValue]="r.id_rol">{{ r.nombre }}</option> }</select></label>
          <label class="field" for="us-s"><span>Restringir a sucursal</span><select id="us-s" name="suc" [(ngModel)]="form.id_sucursal">
            <option [ngValue]="null">Todas las sucursales</option>@for (s of sucursales; track s.id_sucursal) { <option [ngValue]="s.id_sucursal">{{ s.nombre }}</option> }</select></label>
          <label class="field" for="us-e"><span>Estado</span><select id="us-e" name="estado" [(ngModel)]="form.estado" [disabled]="form.id_usuario === auth.usuario()?.id_usuario">
            <option value="ACTIVO">Activo</option><option value="INACTIVO">Inactivo</option></select></label>
          <label class="field" for="us-p"><span>{{ form.id_usuario ? 'Nueva contraseña (opcional)' : 'Contraseña' }}</span>
            <input id="us-p" name="password" type="password" [(ngModel)]="form.password" minlength="6" autocomplete="new-password" [required]="!form.id_usuario"></label>
          <div class="modal-f full"><button type="button" class="btn" (click)="form = null">Cancelar</button><button class="btn btn-p" type="submit">Guardar</button></div>
        </form>
      </app-modal>
    }

    @if (nuevoRol) {
      <app-modal titulo="Nuevo rol" (cerrar)="nuevoRol = null">
        <form class="form-grid" (ngSubmit)="crearRol()">
          <label class="field" for="rl-n"><span>Nombre</span><input id="rl-n" name="nombre" [(ngModel)]="nuevoRol.nombre" required></label>
          <label class="field full" for="rl-d"><span>Descripción</span><input id="rl-d" name="desc" [(ngModel)]="nuevoRol.descripcion"></label>
          <p class="note full">El rol se crea sin permisos. Márcalos después en la matriz.</p>
          <div class="modal-f full"><button type="button" class="btn" (click)="nuevoRol = null">Cancelar</button><button class="btn btn-p" type="submit">Crear rol</button></div>
        </form>
      </app-modal>
    }`,
})
export class UsuariosComponent implements OnInit {
  private api = inject(ApiService);
  private toast = inject(ToastService);
  auth = inject(AuthService);
  tab = 'usuarios';
  usuarios: any[] = [];
  roles: any[] = [];
  permisos: any[] = [];
  sucursales: any[] = [];
  form: any = null;
  nuevoRol: any = null;
  guardando = false;

  async ngOnInit() {
    [this.sucursales, this.permisos] = await Promise.all([this.api.get('/api/sucursales'), this.api.get('/api/permisos')]);
    this.cargar();
  }

  async cargar() { [this.usuarios, this.roles] = await Promise.all([this.api.get('/api/usuarios'), this.api.get('/api/roles')]); }

  editar(u: any) {
    this.form = u ? { ...u, password: '' } : { nombre: '', correo: '', id_rol: this.roles.find((r) => !r.es_sistema)?.id_rol, id_sucursal: null, estado: 'ACTIVO', password: '' };
  }

  async guardar() {
    const datos: any = { nombre: this.form.nombre, correo: this.form.correo, id_rol: this.form.id_rol, id_sucursal: this.form.id_sucursal, estado: this.form.estado };
    if (this.form.password) datos.password = this.form.password;
    try {
      if (this.form.id_usuario) await this.api.put(`/api/usuarios/${this.form.id_usuario}`, datos);
      else await this.api.post('/api/usuarios', datos);
      this.toast.ok('Usuario guardado.');
      this.form = null;
      this.cargar();
    } catch {}
  }

  async alternar(rol: any, codigo: string, marcado: boolean) {
    const permisos = marcado ? [...rol.permisos, codigo] : rol.permisos.filter((p: string) => p !== codigo);
    this.guardando = true;
    try {
      await this.api.put(`/api/roles/${rol.id_rol}/permisos`, { permisos });
      rol.permisos = permisos;
      this.toast.ok(`${marcado ? 'Permiso otorgado' : 'Permiso quitado'} a ${rol.nombre}.`);
      this.auth.refrescar();
    } catch {
      this.cargar();
    } finally { this.guardando = false; }
  }

  async crearRol() {
    try {
      await this.api.post('/api/roles', this.nuevoRol);
      this.toast.ok('Rol creado.');
      this.nuevoRol = null;
      this.tab = 'roles';
      this.cargar();
    } catch {}
  }
}
