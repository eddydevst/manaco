import { Injectable, signal } from '@angular/core';

export interface Toast {
  id: number;
  texto: string;
  tipo: '' | 'ok' | 'warn' | 'bad';
}

@Injectable({ providedIn: 'root' })
export class ToastService {
  readonly lista = signal<Toast[]>([]);
  private n = 0;

  mostrar(texto: string, tipo: Toast['tipo'] = '') {
    const t = { id: ++this.n, texto, tipo };
    this.lista.update((l) => [...l, t]);
    setTimeout(() => this.lista.update((l) => l.filter((x) => x.id !== t.id)), tipo === 'bad' ? 6000 : 3500);
  }

  ok(texto: string) { this.mostrar(texto, 'ok'); }
  aviso(texto: string) { this.mostrar(texto, 'warn'); }
  error(texto: string) { this.mostrar(texto, 'bad'); }
}
