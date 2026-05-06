import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { finalize } from 'rxjs';
import { TranslateModule } from '@ngx-translate/core';
import { ChatbotApi } from '@features/chatbot-assistant/api/chatbot-api';

type ChatRole = 'user' | 'assistant';

type ChatMessage = {
  role: ChatRole;
  content: string;
};

@Component({
  selector: 'app-chatbot-widget',
  standalone: true,
  imports: [CommonModule, FormsModule, TranslateModule],
  templateUrl: './chatbot-widget.html',
})
export class ChatbotWidgetComponent {
  private api = inject(ChatbotApi);
  private sanitizer = inject(DomSanitizer);

  /** Escape HTML: bold lines before the first bullet (headline) and each bullet line (- / •). */
  assistantHtml(text: string): SafeHtml {
    const esc = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    const lines = esc.split('\n');
    const firstBullet = lines.findIndex((line) => /^\s*[-•]\s+/.test(line));
    const boldBullet = (line: string) =>
      /^\s*[-•]\s+/.test(line) ? `<strong>${line}</strong>` : line;

    if (firstBullet > 0) {
      const head = lines.slice(0, firstBullet).join('<br>');
      const rest = lines.slice(firstBullet).map(boldBullet).join('<br>');
      const headHtml = head.trim() ? `<strong>${head}</strong><br>` : '';
      return this.sanitizer.bypassSecurityTrustHtml(headHtml + rest);
    }
    const body = lines.map(boldBullet).join('<br>');
    return this.sanitizer.bypassSecurityTrustHtml(body);
  }

  isOpen = signal(false);
  loading = signal(false);
  inputText = signal('');
  messages = signal<ChatMessage[]>([
    { role: 'assistant', content: 'Ask about CSR Insight: plans, activities, or what you see on screen.' },
  ]);

  canSend = computed(() => this.inputText().trim().length > 0 && !this.loading());

  toggle(): void {
    this.isOpen.update((v) => !v);
  }

  sendMessage(): void {
    const prompt = this.inputText().trim();
    if (!prompt || this.loading()) return;
    this.inputText.set('');
    this.messages.update((list) => [...list, { role: 'user', content: prompt }]);
    this.loading.set(true);

    this.api
      .chat({ prompt })
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (res) => {
          const answer = (res?.response || '').trim() || 'No response.';
          this.messages.update((list) => [...list, { role: 'assistant', content: answer }]);
        },
        error: (err: unknown) => {
          let text = 'Error: cannot reach local assistant.';
          if (err instanceof HttpErrorResponse) {
            const body = err.error as { message?: string } | null | undefined;
            if (body && typeof body.message === 'string' && body.message.trim()) {
              text = `Error: ${body.message.trim()}`;
            } else if (err.status === 0) {
              text = 'Error: cannot reach the API (network or server down).';
            }
          }
          this.messages.update((list) => [...list, { role: 'assistant', content: text }]);
        },
      });
  }

  onInputKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }
}
