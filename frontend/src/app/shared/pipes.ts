import { Pipe, PipeTransform } from '@angular/core';

const nf2 = new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const nf1 = new Intl.NumberFormat('es-BO', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const nf0 = new Intl.NumberFormat('es-BO', { maximumFractionDigits: 0 });

export const fmt = {
  bs: (n: any) => 'Bs ' + nf2.format(Number(n) || 0),
  bsc: (n: any) => {
    const x = Number(n) || 0;
    if (Math.abs(x) >= 1e6) return 'Bs ' + nf2.format(x / 1e6) + ' M';
    if (Math.abs(x) >= 1e4) return 'Bs ' + nf1.format(x / 1e3) + ' mil';
    return 'Bs ' + nf2.format(x);
  },
  num: (n: any) => nf0.format(Math.round(Number(n) || 0)),
  dec: (n: any) => nf2.format(Number(n) || 0),
  pct: (n: any) => (n === null || n === undefined || !isFinite(Number(n)) ? '—' : nf1.format(Number(n) * 100) + ' %'),
  eje: (v: number) => (v >= 1e6 ? nf1.format(v / 1e6) + 'M' : v >= 1e3 ? nf0.format(v / 1e3) + 'k' : nf0.format(v)),
  fecha: (s: any) => {
    if (!s) return '—';
    const d = new Date(s);
    if (isNaN(d.getTime())) return String(s);
    return d.toLocaleDateString('es-BO', { day: '2-digit', month: '2-digit', year: 'numeric' });
  },
  fechaHora: (s: any) => {
    if (!s) return '—';
    const d = new Date(s);
    return d.toLocaleDateString('es-BO', { day: '2-digit', month: '2-digit', year: 'numeric' }) + ' ' +
      d.toLocaleTimeString('es-BO', { hour: '2-digit', minute: '2-digit' });
  },
  mes: (s: any) => {
    if (!s) return '—';
    const [y, m] = String(s).split('-');
    return ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'][+m - 1] + ' ' + y.slice(2);
  },
};

@Pipe({ name: 'bs', standalone: true })
export class BsPipe implements PipeTransform { transform(v: any) { return fmt.bs(v); } }

@Pipe({ name: 'bsc', standalone: true })
export class BscPipe implements PipeTransform { transform(v: any) { return fmt.bsc(v); } }

@Pipe({ name: 'num', standalone: true })
export class NumPipe implements PipeTransform { transform(v: any) { return fmt.num(v); } }

@Pipe({ name: 'pct', standalone: true })
export class PctPipe implements PipeTransform { transform(v: any) { return fmt.pct(v); } }

@Pipe({ name: 'fecha', standalone: true })
export class FechaPipe implements PipeTransform { transform(v: any) { return fmt.fecha(v); } }

@Pipe({ name: 'fechaHora', standalone: true })
export class FechaHoraPipe implements PipeTransform { transform(v: any) { return fmt.fechaHora(v); } }

@Pipe({ name: 'mes', standalone: true })
export class MesPipe implements PipeTransform { transform(v: any) { return fmt.mes(v); } }

export const PIPES = [BsPipe, BscPipe, NumPipe, PctPipe, FechaPipe, FechaHoraPipe, MesPipe];
