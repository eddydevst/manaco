import { Component, OnInit, inject } from '@angular/core';
import { ApiService } from '../core/api.service';
import { ToastService } from '../core/toast.service';
import { BarrasComponent, ModalComponent } from '../shared/graficos';
import { PIPES } from '../shared/pipes';

@Component({
  selector: 'app-comex',
  standalone: true,
  imports: [BarrasComponent, ModalComponent, ...PIPES],
  template: `
    <header class="ph">
      <div><div class="ph-t"><h1>Comercio exterior de calzado</h1></div><p>Información externa del mercado para el análisis gerencial. No son ventas de MANACO.</p></div>
      <div class="ph-a"><button class="btn" type="button" (click)="plantilla()">Descargar plantilla CSV</button></div>
    </header>

    @if (d && !d.resumen.registros) {
      <section class="card"><div class="empty"><h2>Todavía no hay datos de comercio exterior</h2>
        <p style="max-width:56ch">Carga el Excel con estadísticas de importaciones y exportaciones de calzado. El sistema calcula valores por país socio, por categoría y el valor aproximado por par.</p></div></section>
    }
    @if (d?.resumen.registros) {
      <section class="kpis">
        <div class="kpi"><span class="l">Registros</span><span class="v">{{ d.resumen.registros | num }}</span></div>
        <div class="kpi"><span class="l">Importaciones (valor)</span><span class="v">{{ d.resumen.importaciones | num }}</span></div>
        <div class="kpi"><span class="l">Exportaciones (valor)</span><span class="v">{{ d.resumen.exportaciones | num }}</span></div>
        <div class="kpi"><span class="l">Valor aprox. por par importado</span><span class="v">{{ d.resumen.valor_por_par === null ? '—' : (d.resumen.valor_por_par | bs) }}</span><span class="d">en la moneda del archivo</span></div>
      </section>
      <div class="row">
        <section class="card c1"><h2>Importaciones por país de origen</h2><app-barras [items]="porPais" formato="num"></app-barras></section>
        <section class="card c1"><h2>Valor por categoría</h2><app-barras [items]="porCategoria" formato="num"></app-barras></section>
        <section class="card c1"><h2>Por año</h2><div class="tw"><table class="t">
          <thead><tr><th>Año</th><th class="num">Importaciones</th><th class="num">Exportaciones</th><th class="num">Balanza</th></tr></thead>
          <tbody>@for (a of d.por_anio; track a.anio) {
            <tr><td>{{ a.anio }}</td><td class="num">{{ a.importaciones | num }}</td><td class="num">{{ a.exportaciones | num }}</td>
              <td class="num" [style.color]="a.exportaciones - a.importaciones >= 0 ? 'var(--ok)' : 'var(--bad)'">{{ a.exportaciones - a.importaciones | num }}</td></tr>
          }</tbody></table></div></section>
      </div>
      <section class="card"><h2>Registros (primeros 300)</h2><div class="tw" style="max-height:380px;overflow:auto"><table class="t">
        <thead><tr><th>Año</th><th>Flujo</th><th>País reportante</th><th>País socio</th><th>Categoría</th><th class="num">Valor</th><th class="num">Cantidad</th><th>Unidad</th></tr></thead>
        <tbody>@for (r of d.registros; track $index) {
          <tr><td>{{ r.anio }}</td><td>{{ r.flujo }}</td><td>{{ r.pais_reportante }}</td><td>{{ r.pais_socio }}</td><td>{{ r.categoria }}</td>
            <td class="num">{{ r.valor_comercial | num }}</td><td class="num">{{ r.cantidad | num }}</td><td>{{ r.unidad }}</td></tr>
        }</tbody></table></div></section>
    }

    <section class="card"><h2>Cargar datos</h2>
      <p class="sm muted">Columnas: anio, flujo, pais_reportante, pais_socio, categoria, valor_comercial, cantidad, unidad. Flujo: Importación o Exportación. Acepta .xlsx o .csv.</p>
      <div class="filters">
        <label class="field w2" for="cx-f"><span>Archivo</span><input id="cx-f" type="file" accept=".csv,.xlsx" (change)="subir($event)"></label>
        @if (d?.resumen.registros) { <button class="btn btn-bad" type="button" (click)="confirmar = true">Borrar datos cargados</button> }
      </div>
    </section>

    @if (confirmar) {
      <app-modal titulo="Borrar datos de comercio exterior" (cerrar)="confirmar = false">
        <p>Se eliminan los {{ d.resumen.registros }} registros cargados. Las ventas y compras no cambian.</p>
        <div class="modal-f"><button class="btn" type="button" (click)="confirmar = false">Cancelar</button><button class="btn btn-bad" type="button" (click)="borrar()">Borrar</button></div>
      </app-modal>
    }`,
})
export class ComexComponent implements OnInit {
  private api = inject(ApiService);
  private toast = inject(ToastService);
  d: any = null;
  porPais: any[] = [];
  porCategoria: any[] = [];
  confirmar = false;

  ngOnInit() { this.cargar(); }

  async cargar() {
    this.d = await this.api.get('/api/comex');
    this.porPais = this.d.por_pais.map((x: any) => ({ etiqueta: x.etiqueta || '—', valor: +x.valor }));
    this.porCategoria = this.d.por_categoria.map((x: any) => ({ etiqueta: x.etiqueta || '—', valor: +x.valor }));
  }

  plantilla() { this.api.descargar('/api/comex/plantilla', 'plantilla_comercio_exterior.csv'); }

  async subir(e: Event) {
    const input = e.target as HTMLInputElement;
    const f = input.files?.[0];
    if (!f) return;
    try {
      const r = await this.api.upload('/api/comex/importar', f);
      this.toast.ok(`${r.registros} registros cargados${r.rechazadas ? `, ${r.rechazadas} filas rechazadas` : ''}.`);
      this.cargar();
    } catch {} finally { input.value = ''; }
  }

  async borrar() {
    await this.api.delete('/api/comex');
    this.confirmar = false;
    this.toast.ok('Datos borrados.');
    this.cargar();
  }
}
