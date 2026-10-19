import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../core/api.service';
import { PIPES } from '../shared/pipes';

@Component({
  selector: 'app-bitacora',
  standalone: true,
  imports: [FormsModule, ...PIPES],
  template: `
    <header class="ph"><div><div class="ph-t"><h1>Bitácora</h1></div><p>Historial de operaciones: quién, cuándo, qué acción y los datos antes y después del cambio.</p></div></header>
    <section class="card">
      <div class="filters">
        <label class="field w2" for="bt-q"><span>Buscar</span><input id="bt-q" type="search" [(ngModel)]="q" (ngModelChange)="buscar()" placeholder="Acción, número de venta, SKU…"></label>
        <label class="field" for="bt-u"><span>Usuario</span><select id="bt-u" [(ngModel)]="usuario" (ngModelChange)="ir(1)">
          <option [ngValue]="null">Todos</option>@for (u of usuarios; track u.id_usuario) { <option [ngValue]="u.id_usuario">{{ u.nombre }}</option> }</select></label>
        <label class="field" for="bt-e"><span>Entidad</span><select id="bt-e" [(ngModel)]="entidad" (ngModelChange)="ir(1)">
          <option [ngValue]="null">Todas</option>@for (e of entidades; track e) { <option [ngValue]="e">{{ e }}</option> }</select></label>
      </div>
      <div class="tw"><table class="t">
        <thead><tr><th>Fecha</th><th>Usuario</th><th>Acción</th><th>Entidad</th><th>Detalle</th><th></th></tr></thead>
        <tbody>@for (b of items; track b.id_bitacora) {
          <tr><td class="sm" style="white-space:nowrap">{{ b.fecha | fechaHora }}</td><td>{{ b.usuario || '—' }}</td><td class="mono sm b">{{ b.accion }}</td>
            <td><span class="badge b-mut">{{ b.entidad }}</span></td><td class="sm muted" style="max-width:46ch">{{ resumen(b) }}</td>
            <td><button class="btn btn-sm" type="button" (click)="abierto = abierto === b.id_bitacora ? null : b.id_bitacora" [attr.aria-expanded]="abierto === b.id_bitacora">{{ abierto === b.id_bitacora ? 'Ocultar' : 'Cambios' }}</button></td></tr>
          @if (abierto === b.id_bitacora) {
            <tr><td colspan="6"><div class="row">
              <div class="c1"><h3>Antes</h3><pre class="json">{{ json(b.datos_anteriores) }}</pre></div>
              <div class="c1"><h3>Después</h3><pre class="json">{{ json(b.datos_nuevos) }}</pre></div></div></td></tr>
          }
        } @empty { <tr><td colspan="6"><div class="empty">Sin registros con estos filtros.</div></td></tr> }</tbody></table></div>
      <div class="pager"><span>{{ total }} registros · página {{ pagina }} de {{ paginas() }}</span>
        <span style="display:flex;gap:6px"><button class="btn btn-sm" type="button" (click)="ir(pagina - 1)" [disabled]="pagina <= 1">Anterior</button>
          <button class="btn btn-sm" type="button" (click)="ir(pagina + 1)" [disabled]="pagina >= paginas()">Siguiente</button></span></div>
    </section>`,
})
export class BitacoraComponent implements OnInit {
  private api = inject(ApiService);
  q = '';
  usuario: number | null = null;
  entidad: string | null = null;
  usuarios: any[] = [];
  entidades: string[] = [];
  items: any[] = [];
  total = 0;
  pagina = 1;
  abierto: number | null = null;
  private t: any;

  async ngOnInit() { this.usuarios = await this.api.get('/api/bitacora/usuarios'); this.ir(1); }
  paginas() { return Math.max(1, Math.ceil(this.total / 50)); }
  buscar() { clearTimeout(this.t); this.t = setTimeout(() => this.ir(1), 300); }

  async ir(p: number) {
    this.pagina = Math.max(1, p);
    const r = await this.api.get('/api/bitacora', { q: this.q, id_usuario: this.usuario, entidad: this.entidad, pagina: this.pagina });
    this.items = r.items;
    this.total = r.total;
    this.entidades = r.entidades;
  }

  resumen(b: any) {
    const d = b.datos_nuevos || b.datos_anteriores || {};
    return Object.entries(d).slice(0, 3).map(([k, v]) => `${k}: ${typeof v === 'object' ? '…' : v}`).join(' · ');
  }
  json(x: any) { return x ? JSON.stringify(x, null, 2) : '—'; }
}
