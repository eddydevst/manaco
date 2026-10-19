import { Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ToastService } from './core/toast.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: `
    <router-outlet></router-outlet>
    <div class="toasts" aria-live="polite">
      @for (t of toast.lista(); track t.id) { <div class="toast {{ t.tipo }}">{{ t.texto }}</div> }
    </div>`,
})
export class AppComponent {
  toast = inject(ToastService);
}
