import { Component, OnInit, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { ToastService } from '../core/toast.service';
import { PIPES } from '../shared/pipes';

const COLUMNAS = [
  ['SKU', 'Identificador único de la variante'], ['Categoría', 'Nombre o código de una categoría existente'], ['Marca', 'Marca comercial'],
  ['Modelo', 'Modelo del producto'], ['Talla', 'Talla del calzado'], ['Color', 'Color'], ['Descripción', 'Opcional'],
  ['Precio de venta', 'Número mayor a 0'], ['Costo', 'Costo de referencia'], ['Proveedor', 'Código, ej. PRV01 (opcional)'],
  ['Sucursal', 'Código, ej. SCZ01 (requerido si hay stock inicial)'], ['Stock inicial', 'Entero; solo para SKU nuevos'],
];

@Component({
  selector: 'app-importador',
  standalone: true,
  imports: [RouterLink, ...PIPES],
  template: `
    <header class="ph">
      <div><div class="ph-t"><h1>Importador de productos</h1></div>
        <p>Carga masiva desde Excel (.xlsx) o CSV. Los productos existentes se actualizan por SKU; el stock inicial entra como movimiento de inventario.</p></div>
      <div class="ph-a"><button class="btn" type="button" (click)="plantilla()">Descargar plantilla modelo</button></div>
    </header>

    <ol class="steps">
      @for (s of pasos; track $index; let i = $index) {
        <li [class.done]="i + 1 < paso() || (paso() === 5 && i === 4)" [class.cur]="i + 1 === paso() && paso() !== 5" [attr.aria-current]="i + 1 === paso() ? 'step' : null">
          <span class="n">{{ i + 1 < paso() || (paso() === 5 && i === 4) ? '✓' : i + 1 }}</span>{{ s }}</li>
      }
    </ol>

    @if (resultado) {
      <section class="card"><h2>Importación completada · {{ resultado.referencia }}</h2>
        <div class="kpis">
          <div class="kpi"><span class="l">Productos nuevos</span><span class="v">{{ resultado.productos_nuevos | num }}</span></div>
          <div class="kpi"><span class="l">Variantes creadas</span><span class="v">{{ resultado.variantes | num }}</span></div>
          <div class="kpi info"><span class="l">Actualizaciones</span><span class="v">{{ resultado.actualizaciones | num }}</span></div>
          <div class="kpi" [class.bad]="resultado.errores > 0"><span class="l">Filas con error</span><span class="v">{{ resultado.errores | num }}</span></div>
          <div class="kpi"><span class="l">Pares ingresados</span><span class="v">{{ resultado.pares | num }}</span></div>
        </div>
        <div class="modal-f" style="justify-content:flex-start">
          @if (resultado.errores) { <button class="btn" type="button" (click)="reporteErrores(resultado.id_importacion)">Descargar reporte de errores</button> }
          <button class="btn btn-p" type="button" (click)="reiniciar()">Nueva importación</button>
          @if (auth.puede('productos.ver')) { <a class="btn" routerLink="/productos">Ver productos</a> }
        </div>
      </section>
    }

    @if (!val && !resultado) {
      <div class="row">
        <section class="card c2"><h2>1. Prepara la planilla</h2>
          <div class="tw"><table class="t"><thead><tr><th>Columna</th><th>Contenido</th></tr></thead>
            <tbody>@for (c of columnas; track c[0]) { <tr><td class="b">{{ c[0] }}</td><td class="muted">{{ c[1] }}</td></tr> }</tbody></table></div>
          <p class="sm muted">La primera fila debe tener los nombres de columna. En CSV se acepta separador «;» o «,».</p>
        </section>
        <section class="card c1"><h2>2. Sube el archivo</h2>
          <label class="drop" [class.over]="sobre" for="imp-f" (dragover)="$event.preventDefault(); sobre = true" (dragleave)="sobre = false" (drop)="soltar($event)">
            <span class="b">Arrastra aquí tu .xlsx o .csv</span><span class="sm muted">o haz clic para elegirlo</span>
            <input id="imp-f" type="file" accept=".csv,.xlsx" (change)="elegir($event)" style="max-width:100%">
          </label>
          @if (validando) { <p class="muted"><span class="spin"></span> Validando…</p> }
        </section>
      </div>
    }

    @if (val && !resultado) {
      <section class="kpis">
        <div class="kpi"><span class="l">Archivo</span><span class="v" style="font-size:15px">{{ val.archivo }}</span><span class="d">{{ val.resumen.filas }} filas</span></div>
        <div class="kpi"><span class="l">Nuevos</span><span class="v">{{ val.resumen.nuevos | num }}</span><span class="d">variantes a crear</span></div>
        <div class="kpi info"><span class="l">Actualizaciones</span><span class="v">{{ val.resumen.actualizaciones | num }}</span><span class="d">precio, costo y descripción</span></div>
        <div class="kpi" [class.bad]="val.resumen.errores > 0"><span class="l">Con error</span><span class="v">{{ val.resumen.errores | num }}</span><span class="d">no se importarán</span></div>
      </section>
      <section class="card">
        <div class="card-h"><h2>Previsualización</h2>
          <div class="chips">
            @for (x of filtros; track x[0]) { <button class="chip" type="button" [attr.aria-pressed]="filtro === x[0]" (click)="filtro = x[0]">{{ x[1] }}</button> }
          </div></div>
        <div class="tw"><table class="t">
          <thead><tr><th>Fila</th><th>SKU</th><th>Categoría</th><th>Modelo</th><th>Talla / color</th><th class="num">Precio</th><th class="num">Costo</th><th class="num">Stock</th><th>Resultado</th></tr></thead>
          <tbody>@for (r of visibles(); track r.fila) {
            <tr [class.err]="r.estado === 'ERROR'" [class.warnrow]="r.estado !== 'ERROR' && r.avisos.length">
              <td class="mono">{{ r.fila }}</td><td class="mono sm">{{ r.datos.sku }}</td><td>{{ r.datos.categoria }}</td><td>{{ r.datos.modelo }}</td>
              <td>{{ r.datos.talla }} · {{ r.datos.color }}</td><td class="num">{{ r.datos.precio }}</td><td class="num">{{ r.datos.costo }}</td><td class="num">{{ r.datos.stock || '—' }}</td>
              <td>@if (r.estado === 'ERROR') { <span class="b" style="color:var(--bad)">{{ r.errores.join('; ') }}</span> }
                  @else { <span class="badge {{ r.estado === 'NUEVO' ? 'b-ok' : 'b-info' }}">{{ r.estado === 'NUEVO' ? 'Nuevo' : 'Actualiza' }}</span> }
                  @if (r.avisos.length) { <div class="sm" style="color:var(--warn)">{{ r.avisos.join('; ') }}</div> }</td></tr>
          } @empty { <tr><td colspan="9"><div class="empty">Sin filas en este filtro.</div></td></tr> }</tbody></table></div>
      </section>
      <div class="card" style="flex-direction:row;flex-wrap:wrap;justify-content:space-between;align-items:center">
        <span>Se importarán <b>{{ val.resumen.nuevos + val.resumen.actualizaciones }} filas válidas</b>@if (val.resumen.errores) {; las {{ val.resumen.errores }} con error quedan en el reporte}.</span>
        <span style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" type="button" (click)="reiniciar()">Cancelar</button>
          <button class="btn btn-p" type="button" (click)="confirmar()" [disabled]="ocupado || !(val.resumen.nuevos + val.resumen.actualizaciones)">
            @if (ocupado) { <span class="spin"></span> } Confirmar importación</button></span>
      </div>
    }

    <section class="card"><h2>Historial de importaciones</h2>
      <div class="tw"><table class="t"><thead><tr><th>Fecha</th><th>Archivo</th><th>Usuario</th><th class="num">Correctos</th><th class="num">Con error</th><th>Estado</th><th></th></tr></thead>
        <tbody>@for (h of historial; track h.id_importacion) {
          <tr><td class="sm">{{ h.fecha | fechaHora }}</td><td class="mono sm">{{ h.archivo }}</td><td>{{ h.usuario }}</td><td class="num">{{ h.registros_correctos }}</td><td class="num">{{ h.registros_error }}</td>
            <td><span class="badge {{ h.registros_error ? 'b-warn' : 'b-ok' }}">{{ h.registros_error ? 'Con observaciones' : 'Completa' }}</span></td>
            <td>@if (h.registros_error) { <button class="btn btn-sm" type="button" (click)="reporteErrores(h.id_importacion)">Errores</button> }</td></tr>
        } @empty { <tr><td colspan="7"><div class="empty">Aún no hay importaciones.</div></td></tr> }</tbody></table></div>
    </section>`,
})
export class ImportadorComponent implements OnInit {
  private api = inject(ApiService);
  private toast = inject(ToastService);
  auth = inject(AuthService);
  columnas = COLUMNAS;
  pasos = ['Plantilla', 'Subir archivo', 'Validación', 'Previsualizar', 'Confirmar'];
  filtros = [['todas', 'Todas'], ['validas', 'Válidas'], ['errores', 'Solo errores']];
  filtro = 'todas';
  archivo: File | null = null;
  val: any = null;
  resultado: any = null;
  historial: any[] = [];
  validando = false;
  ocupado = false;
  sobre = false;

  ngOnInit() { this.cargarHistorial(); }
  async cargarHistorial() { this.historial = await this.api.get('/api/importador/historial'); }
  paso() { return this.resultado ? 5 : this.val ? 4 : 2; }
  visibles() {
    const f = this.val?.filas || [];
    return this.filtro === 'errores' ? f.filter((r: any) => r.estado === 'ERROR') : this.filtro === 'validas' ? f.filter((r: any) => r.estado !== 'ERROR') : f;
  }

  plantilla() { this.api.descargar('/api/importador/plantilla', 'plantilla_productos_manaco.xlsx'); }
  reporteErrores(id: number) { this.api.descargar(`/api/importador/${id}/errores`, `errores_importacion_${id}.csv`); }

  elegir(e: Event) { const f = (e.target as HTMLInputElement).files?.[0]; if (f) this.validar(f); }
  soltar(e: DragEvent) { e.preventDefault(); this.sobre = false; const f = e.dataTransfer?.files?.[0]; if (f) this.validar(f); }

  async validar(f: File) {
    this.archivo = f;
    this.validando = true;
    try { this.val = await this.api.upload('/api/importador/validar', f); this.filtro = 'todas'; } catch {} finally { this.validando = false; }
  }

  async confirmar() {
    if (!this.archivo) return;
    this.ocupado = true;
    try {
      this.resultado = await this.api.upload('/api/importador/confirmar', this.archivo);
      this.toast.ok('Importación completada.');
      this.cargarHistorial();
    } catch {} finally { this.ocupado = false; }
  }

  reiniciar() { this.val = null; this.resultado = null; this.archivo = null; }
}
