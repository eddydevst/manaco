import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';

/** Acceso a la API REST. Devuelve promesas para usar async/await en los componentes.
 *  Los errores se muestran automáticamente (ver auth.interceptor.ts). */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private base = environment.apiUrl;

  private params(p?: Record<string, any>): HttpParams {
    let hp = new HttpParams();
    Object.entries(p || {}).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== '') hp = hp.set(k, String(v));
    });
    return hp;
  }

  get<T = any>(url: string, params?: Record<string, any>): Promise<T> {
    return firstValueFrom(this.http.get<T>(this.base + url, { params: this.params(params) }));
  }

  post<T = any>(url: string, body: any = {}): Promise<T> {
    return firstValueFrom(this.http.post<T>(this.base + url, body));
  }

  put<T = any>(url: string, body: any = {}): Promise<T> {
    return firstValueFrom(this.http.put<T>(this.base + url, body));
  }

  delete<T = any>(url: string): Promise<T> {
    return firstValueFrom(this.http.delete<T>(this.base + url));
  }

  upload<T = any>(url: string, archivo: File): Promise<T> {
    const fd = new FormData();
    fd.append('archivo', archivo, archivo.name);
    return firstValueFrom(this.http.post<T>(this.base + url, fd));
  }

  /** Descarga un archivo generado por la API (plantillas, reportes CSV). */
  async descargar(url: string, nombre: string, params?: Record<string, any>): Promise<void> {
    const blob = await firstValueFrom(this.http.get(this.base + url, { params: this.params(params), responseType: 'blob' }));
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = nombre;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
}
