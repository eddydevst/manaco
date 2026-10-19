import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';
import { MENU } from './nav';

export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  return auth.autenticado() ? true : inject(Router).createUrlTree(['/login']);
};

/** Ruta protegida por permiso: data: { permiso: 'panel.ver' } */
export const permisoGuard: CanActivateFn = (route) => {
  const auth = inject(AuthService);
  return auth.puede(route.data['permiso']) ? true : inject(Router).createUrlTree(['/sin-acceso']);
};

/** Envía al primer módulo que el usuario tiene permitido. */
export const inicioGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  for (const g of MENU) for (const i of g.items) if (auth.puede(i.permiso)) return router.createUrlTree(['/', i.ruta]);
  return router.createUrlTree(['/sin-acceso']);
};
