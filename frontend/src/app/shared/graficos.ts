import { Component, EventEmitter, HostListener, Input, OnChanges, Output, inject } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { fmt } from './pipes';

export interface Serie {
  nombre?: string;
  unidad?: string;
  valores: (number | null)[];
  color: string;
  discontinua?: boolean;
  area?: boolean;
  punto?: boolean;
  grosor?: number;
}

const esc = (s: any) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!));

function maxRedondo(v: number): number {
  if (v <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const f = v / p;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
}

/** Gráfico de líneas en SVG (sin librerías externas). */
@Component({
  selector: 'app-grafico-lineas',
  standalone: true,
  template: `<div [innerHTML]="svg"></div>`,
})
export class GraficoLineasComponent implements OnChanges {
  @Input() etiquetas: string[] = [];
  @Input() series: Serie[] = [];
  @Input() alto = 240;
  @Input() descripcion = 'Gráfico';
  svg: SafeHtml = '';
  private san = inject(DomSanitizer);

  ngOnChanges() {
    const W = 660, H = this.alto, L = 48, R = 14, T = 12, B = 26;
    const todos = this.series.flatMap((s) => s.valores.filter((v) => v !== null && v !== undefined) as number[]);
    const max = maxRedondo(Math.max(0, ...todos));
    const n = this.etiquetas.length;
    const x = (i: number) => L + (n < 2 ? 0 : (i * (W - L - R)) / (n - 1));
    const y = (v: number) => T + (H - T - B) * (1 - v / max);
    let g = '';
    for (let k = 0; k <= 4; k++) {
      const v = (max * k) / 4;
      g += `<line class="gl" x1="${L}" x2="${W - R}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/>` +
        `<text class="tk" x="${L - 6}" y="${(y(v) + 3.5).toFixed(1)}" text-anchor="end">${fmt.eje(v)}</text>`;
    }
    const paso = Math.ceil(n / 12);
    this.etiquetas.forEach((l, i) => {
      if (i % paso === 0) g += `<text class="tk" x="${x(i).toFixed(1)}" y="${H - 7}" text-anchor="middle">${esc(l)}</text>`;
    });
    for (const s of this.series) {
      let d = '', lapiz = false, primero = -1, ultimo = -1;
      s.valores.forEach((v, i) => {
        if (v === null || v === undefined) { lapiz = false; return; }
        d += (lapiz ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(v).toFixed(1) + ' ';
        lapiz = true;
        if (primero < 0) primero = i;
        ultimo = i;
      });
      if (!d) continue;
      s.valores.forEach((v, i) => {
        if (v !== null && v !== undefined) g += `<circle tabindex="0" cx="${x(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="5" style="fill:${s.color}"><title>${esc(s.nombre || this.descripcion)} - ${esc(this.etiquetas[i])}: ${esc(new Intl.NumberFormat('es-BO', {maximumFractionDigits: 2}).format(v))} ${esc(s.unidad || '')}</title></circle>`;
      });
      if (s.area) g += `<path d="${d}L${x(ultimo).toFixed(1)} ${y(0)} L${x(primero).toFixed(1)} ${y(0)} Z" style="fill:${s.color};opacity:.08;stroke:none"/>`;
      g += `<path d="${d}" fill="none" style="stroke:${s.color}" stroke-width="${s.grosor || 2.5}" ${s.discontinua ? 'stroke-dasharray="4 5"' : ''} stroke-linecap="round" stroke-linejoin="round"/>`;
      if (s.punto && ultimo >= 0) g += `<circle cx="${x(ultimo).toFixed(1)}" cy="${y(s.valores[ultimo] as number).toFixed(1)}" r="4" style="fill:${s.color}"/>`;
    }
    this.svg = this.san.bypassSecurityTrustHtml(
      `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(this.descripcion)}">${g}</svg>`,
    );
  }
}

/** Barras horizontales simples. formato: bs | bsc | pct | num */
@Component({
  selector: 'app-barras',
  standalone: true,
  template: `
    @if (!items?.length) { <div class="empty">Sin datos para el período</div> }
    <div class="bars">
      @for (i of items; track $index) {
        <div style="display:flex;flex-direction:column;gap:5px">
          <div class="bar-h"><span>{{ i.etiqueta }}</span><span class="mono">{{ f(i.valor) }} @if (i.extra) {<span class="muted">{{ i.extra }}</span>}</span></div>
          <div class="bar-t"><div class="bar-f" [style.width.%]="ancho(i.valor)"></div></div>
        </div>
      }
    </div>`,
})
export class BarrasComponent {
  @Input() items: { etiqueta: string; valor: number; extra?: string }[] = [];
  @Input() formato: 'bs' | 'bsc' | 'pct' | 'num' = 'bsc';
  f(v: any) { return (fmt as any)[this.formato](v); }
  ancho(v: number) {
    const max = Math.max(0, ...this.items.map((i) => Number(i.valor) || 0)) || 1;
    return Math.max(1, ((Number(v) || 0) / max) * 100);
  }
}

/** Ventana modal con contenido proyectado. */
@Component({
  selector: 'app-modal',
  standalone: true,
  template: `
    <div class="modal-bg" (click)="fondo($event)">
      <div class="modal" [class.wide]="ancho" role="dialog" aria-modal="true" [attr.aria-label]="titulo">
        <div class="modal-h"><h2>{{ titulo }}</h2><button class="x" type="button" (click)="cerrar.emit()" aria-label="Cerrar">×</button></div>
        <div class="modal-b"><ng-content></ng-content></div>
      </div>
    </div>`,
})
export class ModalComponent {
  @Input() titulo = '';
  @Input() ancho = false;
  @Output() cerrar = new EventEmitter<void>();
  @HostListener('document:keydown.escape') esc() { this.cerrar.emit(); }
  fondo(e: MouseEvent) { if (e.target === e.currentTarget) this.cerrar.emit(); }
}
