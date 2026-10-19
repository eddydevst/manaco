import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../core/api.service';
import { ToastService } from '../core/toast.service';
import { ModalComponent } from '../shared/graficos';

@Component({
  selector: 'app-socios',
  standalone: true,
  imports: [FormsModule, ModalComponent],
  template: `
    <header class="ph">
      <div><div class="ph-t"><h1>Socios comerciales</h1></div>
        <p>Relaciones empresariales identificables de MANACO. Los países de las estadísticas de comercio exterior se manejan aparte y no se convierten en socios.</p></div>
      <div class="ph-a"><button class="btn btn-p" type="button" (click)="editar(null)">Nuevo socio</button></div>
    </header>
    <section class="card"><div class="tw"><table class="t">
      <thead><tr><th>Nombre</th><th>País</th><th>Tipo de relación</th><th>Descripción</th><th>Estado</th><th></th></tr></thead>
      <tbody>@for (s of lista; track s.id_socio) {
        <tr><td class="b">{{ s.nombre }}</td><td>{{ s.pais }}</td><td><span class="badge b-info">{{ s.tipo_relacion }}</span></td>
          <td class="sm muted" style="max-width:40ch">{{ s.descripcion }}</td>
          <td><span class="badge {{ s.estado === 'ACTIVO' ? 'b-ok' : 'b-mut' }}">{{ s.estado === 'ACTIVO' ? 'Activo' : 'Inactivo' }}</span></td>
          <td><button class="btn btn-sm" type="button" (click)="editar(s)">Editar</button></td></tr>
      } @empty { <tr><td colspan="6"><div class="empty">Sin socios registrados.</div></td></tr> }</tbody></table></div></section>

    @if (form) {
      <app-modal [titulo]="form.id_socio ? 'Editar socio' : 'Nuevo socio comercial'" (cerrar)="form = null">
        <form class="form-grid" (ngSubmit)="guardar()">
          <label class="field" for="sc-n"><span>Nombre</span><input id="sc-n" name="nombre" [(ngModel)]="form.nombre" required></label>
          <label class="field" for="sc-p"><span>País</span><input id="sc-p" name="pais" [(ngModel)]="form.pais" required></label>
          <label class="field" for="sc-t"><span>Tipo de relación</span><select id="sc-t" name="tipo" [(ngModel)]="form.tipo_relacion">
            @for (t of tipos; track t) { <option [value]="t">{{ t }}</option> }</select></label>
          <label class="field" for="sc-e"><span>Estado</span><select id="sc-e" name="estado" [(ngModel)]="form.estado">
            <option value="ACTIVO">Activo</option><option value="INACTIVO">Inactivo</option></select></label>
          <label class="field full" for="sc-d"><span>Descripción</span><textarea id="sc-d" name="desc" [(ngModel)]="form.descripcion"></textarea></label>
          <div class="modal-f full"><button type="button" class="btn" (click)="form = null">Cancelar</button><button class="btn btn-p" type="submit">Guardar</button></div>
        </form>
      </app-modal>
    }`,
})
export class SociosComponent implements OnInit {
  private api = inject(ApiService);
  private toast = inject(ToastService);
  lista: any[] = [];
  form: any = null;
  tipos = ['Distribuidor', 'Franquicia', 'Cliente mayorista', 'Proveedor estratégico', 'Aliado logístico', 'Otro'];

  ngOnInit() { this.cargar(); }
  async cargar() { this.lista = await this.api.get('/api/socios'); }
  editar(s: any) { this.form = s ? { ...s } : { nombre: '', pais: 'Bolivia', tipo_relacion: 'Distribuidor', descripcion: '', estado: 'ACTIVO' }; }

  async guardar() {
    const datos = { nombre: this.form.nombre, pais: this.form.pais, tipo_relacion: this.form.tipo_relacion, descripcion: this.form.descripcion, estado: this.form.estado };
    try {
      if (this.form.id_socio) await this.api.put(`/api/socios/${this.form.id_socio}`, datos);
      else await this.api.post('/api/socios', datos);
      this.toast.ok('Socio guardado.');
      this.form = null;
      this.cargar();
    } catch {}
  }
}
