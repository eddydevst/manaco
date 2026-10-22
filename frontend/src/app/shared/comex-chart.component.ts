import { Component, Input } from '@angular/core';

/** Barras divergentes con valores accesibles por teclado y tooltip nativo. */
@Component({
  selector: 'app-comex-chart', standalone: true,
  template: `
    <p class="sm muted">{{ unidad }} · {{ saldo ? 'Exportaciones − importaciones' : 'Naranja: importaciones · Azul: exportaciones' }}</p>
    @if (!items.length) { <div class="empty">Sin datos para los filtros seleccionados</div> }
    <div class="plot">
    @for (r of items; track r.etiqueta) {
      <div class="group"><div class="label">{{ r.etiqueta }}</div>
      @for (s of campos; track s) {
        <div class="track" tabindex="0" [attr.title]="tooltip(r,s)" [attr.aria-label]="tooltip(r,s)">
          <div class="fill" [style.background]="s === 'importaciones' ? 'var(--accent)' : 'var(--info)'"
            [style.width.%]="width(r,s)" [style.left.%]="left(r,s)"></div>
          @if (saldo) { <span class="zero"></span> }
          <span class="value">{{ format(valor(r,s)) }}</span>
        </div>
      }
      </div>
    }
    </div>`,
  styles: [`:host{display:block}.plot{display:grid;gap:14px}.group{display:grid;gap:5px}.label{font-size:12px;overflow-wrap:anywhere}.track{position:relative;height:27px;background:var(--surface2);border-radius:4px}.fill{position:absolute;height:100%;border-radius:4px;opacity:.35;min-width:0}.value{position:relative;display:block;text-align:right;padding:4px 8px;font-size:12px;font-family:var(--mono)}.zero{position:absolute;left:50%;height:100%;border-left:1px solid var(--muted)}.track:hover .fill,.track:focus .fill{opacity:.65}`]
})
export class ComexChartComponent {
  @Input() items: any[] = [];
  @Input() metrica = '';
  @Input() unidad = 'USD';
  @Input() saldo = false;
  get campos() { return this.saldo ? ['saldo'] : ['importaciones', 'exportaciones']; }
  valor(r: any, s: string): number | null {
    return s === 'saldo' ? r[this.metrica === '_pares' ? 'saldo_pares' : 'saldo_usd'] : r[s + this.metrica];
  }
  format(v: number | null) { return v === null ? 'Sin cantidad válida' : new Intl.NumberFormat('es-BO', {maximumFractionDigits: this.metrica === '_por_par' ? 2 : 0}).format(v); }
  max() { return Math.max(1,...this.items.flatMap(r => this.campos.map(s => Math.abs(this.valor(r,s) || 0)))); }
  width(r: any,s: string) { return Math.abs(this.valor(r,s) || 0)/this.max()*(this.saldo ? 50 : 100); }
  left(r: any,s: string) { return this.saldo ? ((this.valor(r,s) || 0) < 0 ? 50-this.width(r,s) : 50) : 0; }
  tooltip(r: any,s: string) { return `${r.etiqueta} · ${s === 'saldo' ? 'Exportaciones − importaciones' : s} · ${this.format(this.valor(r,s))} ${this.unidad}`; }
}
