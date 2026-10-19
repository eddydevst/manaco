import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { ToastService } from '../core/toast.service';
import { GraficoLineasComponent, Serie } from '../shared/graficos';
import { PIPES, fmt } from '../shared/pipes';
import { ordenSugerida } from './compras.component';

@Component({
  selector: 'app-pronosticos',
  standalone: true,
  imports: [FormsModule, GraficoLineasComponent, ...PIPES],
  template: `
    <header class="ph">
      <div><div class="ph-t"><h1>Pronósticos de demanda</h1></div><p>Proyección de unidades por producto o categoría a partir del historial de ventas, con recomendación de reposición.</p></div>
      <div class="ph-a">
        <label class="field" for="pr-n"><span>Nivel</span><select id="pr-n" [(ngModel)]="nivel" (ngModelChange)="sel = 'T'; cargar()">
          <option value="PRODUCTO">Producto</option><option value="CATEGORIA">Categoría</option></select></label>
        <label class="field" for="pr-s"><span>Sucursal</span><select id="pr-s" [(ngModel)]="sucursal" (ngModelChange)="cargar()" [disabled]="!!auth.sucursalFija()">
          <option [ngValue]="null">Todas</option>@for (s of sucursales; track s.id_sucursal) { <option [ngValue]="s.id_sucursal">{{ s.nombre }}</option> }</select></label>
        <button class="btn btn-d" type="button" (click)="guardar()" [disabled]="!d">Guardar pronóstico</button>
      </div>
    </header>

    @if (!d) { <div class="cargando"><span class="spin"></span> Entrenando y validando modelos…</div> }
    @if (d) {
      <section class="kpis">
        <div class="kpi"><span class="l">Historial usado</span><span class="v">{{ d.meses.length }} meses</span><span class="d">{{ d.meses[0] | mes }} a {{ d.meses[d.meses.length - 1] | mes }}</span></div>
        <div class="kpi"><span class="l">Demanda proyectada {{ d.meses_pronostico[1] | mes }}</span><span class="v">{{ (d.total.pronostico?.[1] || 0) | num }} pares</span><span class="d">todas las líneas</span></div>
        <div class="kpi"><span class="l">Error medio (MAPE)</span><span class="v">{{ d.total.mape | pct }}</span><span class="d">{{ d.total.modelo || 'sin modelo' }}</span></div>
        <div class="kpi warn"><span class="l">Reposición sugerida</span><span class="v">{{ sugeridoTotal() | num }} pares</span><span class="d">{{ conSugerencia() }} {{ nivel === 'CATEGORIA' ? 'categorías' : 'productos' }}</span></div>
        <div class="kpi pur"><span class="l">Riesgo de sobrestock</span><span class="v">{{ sobrestock() | num }}</span><span class="d">cobertura mayor a 120 días</span></div>
      </section>

      <div class="row">
        <section class="card c2">
          <div class="card-h"><h2>Unidades mensuales · {{ nombreSel() }}</h2>
            <label class="field" for="pr-sel" style="min-width:200px"><span class="sr">Serie</span><select id="pr-sel" [(ngModel)]="sel" (ngModelChange)="armarGrafico()">
              <option value="T">Total</option>@for (e of d.entidades; track e.clave) { <option [value]="'' + e.clave">{{ e.nombre }}</option> }</select></label></div>
          <div class="legend"><span class="lg"><i style="border-top-color:var(--accent)"></i>Ventas reales</span><span class="lg"><i style="border-top-color:var(--warn)"></i>Mes en curso (parcial)</span>
            <span class="lg"><i style="border-top-color:var(--info);border-top-style:dashed"></i>Pronóstico</span></div>
          <app-grafico-lineas [etiquetas]="etiquetas" [series]="series" descripcion="Unidades vendidas por mes y pronóstico de los próximos 3 meses"></app-grafico-lineas>
          @if (modeloSel()) { <p class="sm muted">Modelo elegido: {{ modeloSel() }}. Error de validación: {{ mapeSel() | pct }}.</p> }
        </section>
        <section class="card c1"><h2>Método</h2>
          <p class="sm">Para cada serie se prueban tres modelos y se elige el de menor error al pronosticar los últimos 3 meses completos:</p>
          <p class="sm">· Promedio móvil de 3 meses.<br>· Promedio móvil estacional (índice por mes del año, por ejemplo la campaña escolar).<br>· Regresión lineal con tendencia y mes del año (scikit-learn).</p>
          <p class="sm">La reposición sugerida cubre la demanda del próximo mes más un 20 % de stock de seguridad, menos el stock actual.</p>
          @if (d.ultimo_guardado) { <p class="note">Último pronóstico guardado: {{ d.ultimo_guardado.fecha_generacion | fechaHora }} por {{ d.ultimo_guardado.usuario }}.</p> }
        </section>
      </div>

      <section class="card">
        <div class="card-h"><h2>Recomendaciones de abastecimiento</h2></div>
        <div class="tw"><table class="t">
          <thead><tr><th>{{ nivel === 'CATEGORIA' ? 'Categoría' : 'Producto' }}</th><th class="num">Últimos 3 meses</th>
            @for (m of d.meses_pronostico; track m) { <th class="num">{{ m | mes }}</th> }
            <th class="num">Stock actual</th><th class="num">Cobertura</th><th class="num">Reponer</th><th>Señal</th><th>Modelo</th>
            @if (nivel === 'PRODUCTO' && auth.puede('compras.crear')) { <th></th> }</tr></thead>
          <tbody>@for (e of d.entidades; track e.clave) {
            <tr><td class="b">{{ e.nombre }}</td><td class="num">{{ e.ultimos_3 | num }}</td>
              @for (v of (e.pronostico || [null, null, null]); track $index) { <td class="num" [class.b]="$index === 1">{{ v === null ? '—' : (v | num) }}</td> }
              <td class="num">{{ e.stock | num }}</td><td class="num">{{ e.cobertura_dias === null ? '—' : (e.cobertura_dias | num) + ' días' }}</td>
              <td class="num b">{{ e.sugerido ? (e.sugerido | num) : '—' }}</td>
              <td><span class="badge {{ e.senal === 'REPONER' ? 'b-warn' : e.senal === 'SOBRESTOCK' ? 'b-pur' : 'b-ok' }}">{{ e.senal === 'REPONER' ? 'Reponer' : e.senal === 'SOBRESTOCK' ? 'Sobrestock' : 'Cubierto' }}</span></td>
              <td class="sm muted">{{ e.modelo || '—' }}</td>
              @if (nivel === 'PRODUCTO' && auth.puede('compras.crear')) {
                <td>@if (e.sugerido > 0) { <button class="btn btn-sm" type="button" (click)="crearOrden(e)">Crear orden</button> }</td> }
            </tr>
          }</tbody></table></div>
      </section>
    }`,
})
export class PronosticosComponent implements OnInit {
  private api = inject(ApiService);
  private toast = inject(ToastService);
  private router = inject(Router);
  auth = inject(AuthService);
  sucursales: any[] = [];
  nivel = 'PRODUCTO';
  sucursal: number | null = null;
  sel = 'T';
  d: any = null;
  etiquetas: string[] = [];
  series: Serie[] = [];

  async ngOnInit() {
    this.sucursal = this.auth.sucursalFija();
    this.sucursales = await this.api.get('/api/sucursales');
    this.cargar();
  }

  async cargar() {
    this.d = null;
    this.d = await this.api.get('/api/pronosticos', { nivel: this.nivel, id_sucursal: this.sucursal });
    this.armarGrafico();
  }

  private entidad() { return this.sel === 'T' ? null : this.d.entidades.find((e: any) => String(e.clave) === String(this.sel)); }
  nombreSel() { return this.entidad()?.nombre || 'Total'; }
  modeloSel() { return this.sel === 'T' ? this.d.total.modelo : this.entidad()?.modelo; }
  mapeSel() { return this.sel === 'T' ? this.d.total.mape : this.entidad()?.mape; }
  sugeridoTotal() { return this.d.entidades.reduce((a: number, e: any) => a + (e.sugerido || 0), 0); }
  conSugerencia() { return this.d.entidades.filter((e: any) => e.sugerido > 0).length; }
  sobrestock() { return this.d.entidades.filter((e: any) => e.senal === 'SOBRESTOCK').length; }

  armarGrafico() {
    const e = this.entidad();
    const hist: number[] = e ? e.historial : this.d.total.historial;
    const parcial: number = e ? e.parcial : this.d.total.parcial;
    const fc: number[] | null = e ? e.pronostico : this.d.total.pronostico;
    const n = hist.length;
    this.etiquetas = [...this.d.meses, ...this.d.meses_pronostico].map((m: string) => fmt.mes(m));
    const largo = this.etiquetas.length;
    const vacio = () => new Array(largo).fill(null);
    const real = vacio(); hist.forEach((v, i) => (real[i] = v));
    const cur = vacio(); if (largo > n) cur[n] = parcial;
    const pron = vacio(); if (fc) { if (n) pron[n - 1] = hist[n - 1]; fc.forEach((v, i) => (pron[n + i] = v)); }
    this.series = [
      { valores: real, color: 'var(--accent)', area: true },
      { valores: cur, color: 'var(--warn)', punto: true },
      { valores: pron, color: 'var(--info)', discontinua: true, punto: true },
    ];
  }

  async guardar() {
    const r = await this.api.post('/api/pronosticos/guardar', { nivel: this.nivel, id_sucursal: this.sucursal });
    this.toast.ok(`Pronóstico guardado (${r.registros} registros).`);
    this.cargar();
  }

  async crearOrden(e: any) {
    const suc = this.sucursal ?? this.auth.sucursalFija();
    const s = await this.api.get('/api/pronosticos/sugerencia-oc', { id_producto: e.clave, cantidad: e.sugerido, id_sucursal: suc });
    ordenSugerida.datos = { ...s, items: s.items.map((l: any) => ({ ...l })) };
    this.router.navigate(['/compras']);
  }
}
