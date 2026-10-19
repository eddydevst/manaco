import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { TOKEN_KEY } from './auth.service';
import { ToastService } from './toast.service';

export function mensajeError(err: HttpErrorResponse): string {
  if (err.status === 0) return 'No se pudo conectar con la API. Revisa que el backend esté en ejecución.';
  const d = err.error?.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) {
    return d.map((x: any) => `${(x.loc || []).filter((l: any) => l !== 'body').join(' › ')}: ${x.msg}`).join(' · ');
  }
  return `Error ${err.status}: no se pudo completar la operación.`;
}

/** Agrega el token a cada petición, muestra los errores y redirige al login si la sesión expiró. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const toast = inject(ToastService);
  const router = inject(Router);
  const token = localStorage.getItem(TOKEN_KEY);
  const peticion = token ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req;
  return next(peticion).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status === 401 && !req.url.endsWith('/api/auth/login')) {
        localStorage.removeItem(TOKEN_KEY);
        router.navigate(['/login']);
      }
      toast.error(mensajeError(err));
      return throwError(() => err);
    }),
  );
};
