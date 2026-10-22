import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../core/api.service';
import { ComexChartComponent } from '../shared/comex-chart.component';
import { GraficoLineasComponent, Serie } from '../shared/graficos';

@Component({
  selector: 'app-comex', standalone: true,
  imports: [FormsModule, ComexChartComponent, GraficoLineasComponent],
  template: `
    <header class="ph"><div><h1>Comercio exterior de calzado</h1><p>Estadísticas externas para el análisis de mercado de MANACO · 2020–2024</p></div></header>
    @if (error) { <section class="card" role="alert"><p>{{ error }}</p><button class="btn" (click)="cargar()">Reintentar</button></section> }
    @if (d) {
      <section class="card"><p><b>País reportante: {{ d.fuente.reportantes.join(', ') }}.</b> Estos datos externos no representan compras, ventas ni resultados de MANACO.</p>
      <p class="sm muted">Fuente: {{ d.fuente.archivo }} · {{ d.fuente.hojas.join(', ') }}. USD/par es valor comercial unitario ponderado, no precio de venta. El saldo no mide pérdidas ni rentabilidad.</p></section>
      <section class="card filters" [attr.aria-busy]="cargando">
        <label class="field"><span>Año</span><select [(ngModel)]="f.anio" (ngModelChange)="cargar()"><option value="">2020–2024</option>@for (v of d.opciones.anio; track v) { <option [value]="v">{{ v }}</option> }</select></label>
        <label class="field"><span>País socio</span><select [(ngModel)]="f.pais" (ngModelChange)="cargar()"><option value="">Todos</option>@for (v of d.opciones.pais_socio; track v) { <option [value]="v">{{ v }}</option> }</select></label>
        <label class="field"><span>Categoría</span><select [(ngModel)]="f.categoria" (ngModelChange)="cargar()"><option value="">Todas</option>@for (v of d.opciones.categoria; track v) { <option [value]="v">{{ v }}</option> }</select></label>
        <label class="field"><span>Operación</span><select [(ngModel)]="f.flujo" (ngModelChange)="cargar()"><option value="">Ambas</option>@for (v of d.opciones.flujo; track v) { <option [value]="v">{{ v }}</option> }</select></label>
        <button class="btn" (click)="limpiar()">Restablecer</button>
      </section>
      <p role="status" class="sm muted">{{ cargando ? 'Actualizando indicadores…' : d.resumen.registros + ' registros válidos en la selección' }}</p>
      @if (f.flujo) { <p class="sm muted">Selección de un solo flujo: el saldo corresponde únicamente a las operaciones seleccionadas.</p> }
      <section class="kpis">
      @for (k of kpis; track k.campo) {
        <div class="kpi"><span class="l">{{ k.nombre }}</span><span class="v">{{ formato(d.resumen[k.campo], k.dec) }}</span><span class="d">{{ k.unidad }}</span></div>
      }
      <div class="kpi"><span class="l">Mayor movimiento en pares</span><span>{{ d.mayor || 'Sin datos' }}</span></div>
      <div class="kpi"><span class="l">Menor movimiento en pares</span><span>{{ d.menor || 'Sin datos' }}</span><span class="d">Entre categorías con registros seleccionados</span></div>
      </section>
      <section class="card filters"><label class="field"><span>Métrica para comparación, tendencias, socios y saldo</span><select [(ngModel)]="metrica" (ngModelChange)="tendencia()"><option value="">Valor comercial (USD)</option><option value="_pares">Volumen (pares)</option></select></label></section>
      <div class="cx-grid">
        <section class="card"><h2>Importaciones vs. exportaciones por categoría</h2><app-comex-chart [items]="d.por_categoria" [metrica]="metrica" [unidad]="unidad" /></section>
        <section class="card"><h2>Valor comercial promedio ponderado por par</h2><app-comex-chart [items]="d.por_categoria" metrica="_por_par" unidad="USD/par" /><p class="sm muted">Σ USD / Σ pares, por categoría y flujo. Las filas sin pares positivos se excluyen de este cociente.</p></section>
        <section class="card"><h2>Evolución temporal · {{ unidad }}</h2><p class="sm muted">Naranja: importaciones · Azul: exportaciones. Cero indica ausencia de registros válidos, no ausencia de comercio.</p><app-grafico-lineas [etiquetas]="anios" [series]="series" descripcion="Evolución del comercio exterior" /></section>
        <section class="card"><h2>Desequilibrio por categoría · {{ unidad }}</h2><app-comex-chart [items]="d.por_categoria" [metrica]="metrica" [unidad]="unidad" [saldo]="true" /><p class="sm muted">Exportaciones − importaciones. Un saldo negativo indica mayor valor o volumen importado en la selección.</p></section>
        <section class="card"><h2>Principales proveedores · {{ unidad }}</h2><app-comex-chart [items]="ranking('importaciones')" [metrica]="metrica" [unidad]="unidad" /></section>
        <section class="card"><h2>Principales destinos · {{ unidad }}</h2><app-comex-chart [items]="ranking('exportaciones')" [metrica]="metrica" [unidad]="unidad" /></section>
      </div>
      <section class="card"><h2>Calidad de la fuente completa</h2><p>{{ d.calidad.leidas }} filas leídas · {{ d.calidad.duplicadas }} duplicados exactos · {{ d.calidad.invalidas }} inválidas · {{ d.calidad.conflictos }} filas con claves conflictivas · {{ d.calidad.agregadas }} agregados separados.</p>
      <p class="sm muted">Los duplicados exactos se cuentan una vez. Todas las filas con la misma clave (reportante, socio, año, flujo y código SA6) e importes distintos se excluyen hasta revisión. Los agregados Mundo se conservan aparte y no se suman a los países.</p>
      <details><summary>Ver incidencias y agregados</summary><div class="tw"><table class="t"><thead><tr><th>Hoja</th><th>Fila Excel</th><th>Motivo</th></tr></thead><tbody>@for (r of d.incidencias; track $index) { <tr><td>{{ r.hoja }}</td><td>{{ r.fila }}</td><td>{{ r.motivo }}</td></tr> }</tbody></table></div>
      <p class="sm">Agregados separados: {{ d.agregados.length }}</p>@for (r of d.agregados; track $index) { <p class="sm">{{ r.anio }} · {{ r.flujo }} · {{ r.categoria }} · {{ formato(r.valor_comercial) }} USD · {{ formato(r.cantidad) }} pares</p> }</details></section>
      <section class="card"><h2>Registros de la selección</h2><div class="tw" style="max-height:400px;overflow:auto"><table class="t"><thead><tr><th>Año</th><th>Flujo</th><th>Socio</th><th>SA6</th><th>Categoría</th><th>USD</th><th>Pares</th></tr></thead><tbody>@for (r of d.registros; track $index) { <tr><td>{{ r.anio }}</td><td>{{ r.flujo }}</td><td>{{ r.pais_socio }}</td><td>{{ r.codigo }}</td><td>{{ r.categoria }}</td><td class="num">{{ formato(r.valor_comercial, true) }}</td><td class="num">{{ formato(r.cantidad) }}</td></tr> }</tbody></table></div></section>
    } @else if (cargando) { <p role="status">Leyendo el Excel de comercio exterior…</p> }
  `,
  styles: [`.cx-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.filters{flex-direction:row}details summary{cursor:pointer} @media(max-width:1000px){.cx-grid{grid-template-columns:1fr}}`]
})
export class ComexComponent implements OnInit {
  private api = inject(ApiService);
  d: any; error = ''; cargando = false; private solicitud = 0;
  f = { anio: '', pais: '', categoria: '', flujo: '' };
  metrica = ''; anios: string[] = []; series: Serie[] = [];
  kpis = [
    {campo:'importaciones',nombre:'Valor importado',unidad:'USD',dec:true},
    {campo:'exportaciones',nombre:'Valor exportado',unidad:'USD',dec:true},
    {campo:'importaciones_pares',nombre:'Pares importados',unidad:'pares',dec:false},
    {campo:'exportaciones_pares',nombre:'Pares exportados',unidad:'pares',dec:false},
    {campo:'saldo_usd',nombre:'Saldo comercial',unidad:'USD · exportaciones − importaciones',dec:true},
    {campo:'saldo_pares',nombre:'Saldo en volumen',unidad:'pares · exportaciones − importaciones',dec:false},
    {campo:'importaciones_por_par',nombre:'Valor unitario importado',unidad:'USD/par ponderado',dec:true},
    {campo:'exportaciones_por_par',nombre:'Valor unitario exportado',unidad:'USD/par ponderado',dec:true},
  ];
  get unidad() { return this.metrica ? 'pares' : 'USD'; }
  ngOnInit() { this.cargar(); }
  formato(v: number | null, dec = false) { return v === null ? '—' : new Intl.NumberFormat('es-BO',{minimumFractionDigits:dec?2:0,maximumFractionDigits:dec?2:0}).format(v); }
  async cargar() {
    const id = ++this.solicitud; this.cargando = true; this.error = '';
    try { const d = await this.api.get('/api/comex/mercado',this.f); if(id === this.solicitud) { this.d=d; this.tendencia(); } }
    catch { if(id === this.solicitud) { this.d=null; this.error='No se pudo cargar la fuente de comercio exterior. Revisa la conexión y el archivo configurado.'; } }
    finally { if(id === this.solicitud) this.cargando=false; }
  }
  limpiar() { this.f={anio:'',pais:'',categoria:'',flujo:''}; this.cargar(); }
  ranking(campo: string) { return [...this.d.por_pais].filter(r=>r[campo+this.metrica]>0).sort((a,b)=>b[campo+this.metrica]-a[campo+this.metrica]).slice(0,10); }
  tendencia() {
    if(!this.d) return;
    this.anios=this.d.por_anio.map((r:any)=>String(r.etiqueta));
    this.series=['importaciones','exportaciones'].map((s,i)=>({nombre:s,unidad:this.unidad,valores:this.d.por_anio.map((r:any)=>r[s+this.metrica]),color:i?'var(--info)':'var(--accent)',punto:true}));
  }
}
