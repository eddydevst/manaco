import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { fmt } from '../shared/pipes';

@Component({
  selector: 'app-reportes',
  standalone: true,
  imports: [FormsModule],
  template: `
    <header class="ph">
      <div><div class="ph-t"><h1>Reportes</h1></div><p>Tablas comerciales, financieras y de proveedores para el rango elegido. Descárgalas en CSV para abrirlas en Excel.</p></div>
      <div class="ph-a">
        <label class="field" for="rp-d"><span>Desde</span><input id="rp-d" type="date" [(ngModel)]="desde" (ngModelChange)="cargar()"></label>
        <label class="field" for="rp-h"><span>Hasta</span><input id="rp-h" type="date" [(ngModel)]="hasta" (ngModelChange)="cargar()"></label>
        <label class="field" for="rp-s"><span>Sucursal</span><select id="rp-s" [(ngModel)]="sucursal" (ngModelChange)="cargar()" [disabled]="!!auth.sucursalFija()">
          <option [ngValue]="null">Todas</option>@for (s of sucursales; track s.id_sucursal) { <option [ngValue]="s.id_sucursal">{{ s.nombre }}</option> }</select></label>
      </div>
    </header>
    <section class="card">
      <div class="tabs" role="tablist">
        @for (t of tipos; track t[0]) { <button class="tab" role="tab" type="button" [attr.aria-selected]="tipo === t[0]" (click)="tipo = t[0]; cargar()">{{ t[1] }}</button> }
      </div>
      <div class="card-h"><h2>{{ r?.titulo }}</h2><button class="btn btn-sm" type="button" (click)="csv()">Descargar CSV</button></div>
      @if (cargando) { <div class="cargando"><span class="spin"></span></div> }
      @if (r && !cargando) {
        <div class="tw"><table class="t">
          <thead><tr>@for (c of r.columnas; track c.clave) { <th [class.num]="c.tipo !== 'texto' && c.tipo !== 'fecha' && c.tipo !== 'mes'">{{ c.etiqueta }}</th> }</tr></thead>
          <tbody>@for (f of r.filas; track $index) {
            <tr>@for (c of r.columnas; track c.clave) {
              <td [class.num]="c.tipo !== 'texto' && c.tipo !== 'fecha' && c.tipo !== 'mes'" [style.color]="color(c, f[c.clave])">{{ valor(c, f[c.clave]) }}</td>
            }</tr>
          } @empty { <tr><td [attr.colspan]="r.columnas.length"><div class="empty">Sin datos en el rango elegido.</div></td></tr> }</tbody>
        </table></div>
      }
    </section>`,
})
export class ReportesComponent implements OnInit {
  private api = inject(ApiService);
  auth = inject(AuthService);
  sucursales: any[] = [];
  tipos = [['categorias', 'Por categoría'], ['sucursales', 'Por sucursal'], ['productos', 'Productos'], ['proveedores', 'Proveedores'],
           ['compras', 'Compras y costos'], ['variacion', 'Variación mensual'], ['pagos', 'Métodos de pago']];
  tipo = 'categorias';
  desde = new Date().getFullYear() + '-01-01';
  hasta = new Date().toISOString().slice(0, 10);
  sucursal: number | null = null;
  r: any = null;
  cargando = false;

  async ngOnInit() {
    this.sucursal = this.auth.sucursalFija();
    this.sucursales = await this.api.get('/api/sucursales');
    this.cargar();
  }

  private params() { return { desde: this.desde, hasta: this.hasta, id_sucursal: this.sucursal }; }

  async cargar() {
    this.cargando = true;
    try { this.r = await this.api.get(`/api/reportes/${this.tipo}`, this.params()); } finally { this.cargando = false; }
  }

  csv() { this.api.descargar(`/api/reportes/${this.tipo}/csv`, `reporte_${this.tipo}.csv`, this.params()); }

  valor(c: any, v: any) {
    if (v === null || v === undefined) return '—';
    switch (c.tipo) {
      case 'bs': return fmt.bs(v);
      case 'pct': return fmt.pct(v);
      case 'entero': return fmt.num(v);
      case 'fecha': return fmt.fecha(v);
      case 'mes': return fmt.mes(v);
      case 'var': return (v >= 0 ? '▲ ' : '▼ ') + fmt.pct(Math.abs(v));
      default: return v;
    }
  }
  color(c: any, v: any) { return c.tipo === 'var' && v !== null ? (v >= 0 ? 'var(--ok)' : 'var(--bad)') : null; }
}
