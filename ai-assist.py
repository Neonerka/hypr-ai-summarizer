#!/usr/bin/env python3
import sys
import os
import re
import json
import subprocess
import threading
import requests
from ddgs import DDGS

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Pango, Gdk

MODEL = 'qwen2.5-coder:3b-instruct'
OLLAMA_URL = 'http://localhost:11434/api/generate'
SYSTEM_PROMPT = (
    "Ты — подробный CLI-помощник сисадмина на Arch Linux. "
    "Отвечай на русском языке. Всегда на русском. Никогда не отвечай "
    "на английском, китайском или любом другом языке, только на русском.\n\n"
    "Если в предоставленной информации из интернета есть текст на иностранном "
    "языке — переведи его на русский и дай развёрнутый ответ. "
    "Не используй таблицы для переводов. Не используй ASCII-рисование. Не используй *"
    "Просто пиши сплошным текстом на русском.\n\n"
    "Дай максимально полный и подробный ответ по теме запроса. "
    "Используй всю предоставленную информацию из интернета. "
    "Факты, инструкции, команды, объяснения — всё на русском.\n\n"
    "Структура ответа:\n"
    "1. Сначала развёрнутая информация, детали, инструкции, команды — всё, "
    "что есть по теме.\n"
    "2. В самом конце ответа, после всей информации, добавь блок "
    "「Общая сводка」— краткое резюме самого главного на 3-5 строк. "
    "Сводка должна быть в самом низу, чтобы я видел её сразу после "
    "генерации, не листая вверх."
)

FOCUS_COLOR = '#e91e63'  # pink focus ring — меняй на любой цвет

_CSS = """
/* Focus ring color: FOCUS_CT — меняй FOCUS_COLOR в коде выше */
window.ai-assist-window {
    background-color: rgba(255, 255, 255, 0.90);
    border-radius: 10px;
}
textview {
    background-color: transparent;
    color: #000000;
    font-family: JetBrainsMono Nerd Font;
    font-size: 11pt;
}
textview text {
    background-color: transparent;
    color: #000000;
}
textview text.dim {
    color: #555555;
}
entry {
    background-color: rgba(255, 255, 255, 0.95);
    color: #000000;
    border: 1px solid #555555;
    border-radius: 6px;
    padding: 6px 10px;
    font-family: JetBrainsMono Nerd Font;
    font-size: 11pt;
    caret-color: #000000;
}
entry:focus {
    border-color: #000000;
}
radio, radio * {
    font-family: JetBrainsMono Nerd Font;
    font-size: 10pt;
    color: #000000;
    background-color: transparent;
}
radio:focus {
    outline-color: FOCUS_CT;
    -gtk-outline-radius: 4px;
}
entry:focus {
    border-color: #000000;
    outline-color: FOCUS_CT;
}
button:focus {
    outline-color: FOCUS_CT;
}
frame {
    border: 1px solid #555555;
    border-radius: 6px;
}
frame label {
    font-family: JetBrainsMono Nerd Font;
    font-size: 9pt;
    color: #555555;
}
button {
    font-family: JetBrainsMono Nerd Font;
    font-size: 11pt;
    color: #000000;
    background-color: rgba(255, 255, 255, 0.95);
    border: 1px solid #555555;
    border-radius: 6px;
    padding: 4px 12px;
}
button:hover {
    border-color: #000000;
}
label.prompt-label {
    font-family: JetBrainsMono Nerd Font;
    font-size: 11pt;
    color: #555555;
}
label.auth-label {
    font-family: JetBrainsMono Nerd Font;
    font-size: 11pt;
    color: #000000;
}
scrollbar {
    background-color: transparent;
    border: none;
    opacity: 0;
}
scrollbar slider {
    background-color: transparent;
    border: none;
}
"""

CSS = _CSS.replace('FOCUS_CT', FOCUS_COLOR)


class AIAssistWindow(Gtk.Window):
    MODE_CLIPBOARD = 0
    MODE_SEARCH = 1
    MODE_DOCS = 2

    def __init__(self, width, height, initial_query=None, initial_docs=None, pos_x=None, pos_y=None):
        super().__init__()
        self.pos_x = pos_x
        self.pos_y = pos_y
        self.set_title("ai-assist")
        self.set_default_size(width, height)
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_accept_focus(True)
        self.set_resizable(False)
        self.get_style_context().add_class("ai-assist-window")
        GLib.set_prgname("ai-assist")
        self.connect("map-event", self._on_map_event)

        geom = Gdk.Geometry()
        geom.min_width = width
        geom.min_height = height
        geom.max_width = width
        geom.max_height = height
        self.set_geometry_hints(None, geom, Gdk.WindowHints.MIN_SIZE | Gdk.WindowHints.MAX_SIZE)

        self.context = None
        self.first_web = None
        self.processing = False
        self.cancelled = False

        self._in_init = True

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)
        self.add(vbox)

        # === Radio buttons (mode selector) ===
        radio_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        radio_hbox.set_margin_bottom(4)

        self.rb_clipboard = Gtk.RadioButton(label="Буфер")
        self.rb_search = Gtk.RadioButton(group=self.rb_clipboard, label="Поиск")
        self.rb_docs = Gtk.RadioButton(group=self.rb_clipboard, label="Доки")

        radio_hbox.pack_start(self.rb_clipboard, False, False, 0)
        radio_hbox.pack_start(self.rb_search, False, False, 0)
        radio_hbox.pack_start(self.rb_docs, False, False, 0)

        vbox.pack_start(radio_hbox, False, False, 0)

        # === Query entry + Go button ===
        query_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        self.query_entry = Gtk.Entry()
        self.query_entry.set_hexpand(True)
        self.query_entry.connect("activate", self.on_go)

        self.go_button = Gtk.Button(label="▶")
        self.go_button.connect("clicked", self.on_go)

        self.stop_button = Gtk.Button(label="■")
        self.stop_button.connect("clicked", self.on_stop)
        self.stop_button.set_no_show_all(True)

        query_hbox.pack_start(self.query_entry, True, True, 0)
        query_hbox.pack_start(self.go_button, False, False, 0)
        query_hbox.pack_start(self.stop_button, False, False, 0)

        vbox.pack_start(query_hbox, False, False, 0)

        # === Documentation sources (visible only in DOCS mode) ===
        self.docs_frame = Gtk.Frame(label="Источники документации")
        self.docs_frame.set_margin_top(4)

        docs_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.docs_textview = Gtk.TextView()
        self.docs_textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.docs_textview.set_size_request(-1, 60)
        self.docs_textview.set_top_margin(4)
        self.docs_textview.set_left_margin(4)
        self.docs_textview.set_right_margin(4)
        self.docs_textview.set_accepts_tab(False)
        self.docs_buffer = self.docs_textview.get_buffer()

        docs_scrolled = Gtk.ScrolledWindow()
        docs_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        docs_scrolled.add(self.docs_textview)

        docs_vbox.pack_start(docs_scrolled, True, True, 0)
        self.docs_frame.add(docs_vbox)

        vbox.pack_start(self.docs_frame, False, False, 0)

        # === Response area ===
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.textview.set_editable(False)
        self.textview.set_cursor_visible(False)
        self.buffer = self.textview.get_buffer()
        self.scrolled.add(self.textview)

        vbox.pack_start(self.scrolled, True, True, 0)

        # === Follow-up entry ===
        follow_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        follow_hbox.set_margin_top(4)

        self.follow_label = Gtk.Label(label=">>> ")
        self.follow_label.get_style_context().add_class("prompt-label")
        follow_hbox.pack_start(self.follow_label, False, False, 0)

        self.follow_entry = Gtk.Entry()
        self.follow_entry.set_hexpand(True)
        self.follow_entry.connect("activate", self.on_follow_activate)
        follow_hbox.pack_start(self.follow_entry, True, True, 0)

        vbox.pack_start(follow_hbox, False, False, 0)

        # === Key events ===
        self.connect("key-press-event", self.on_key_press)

        # === Connect mode signals ===
        self.rb_clipboard.connect("toggled", self.on_mode_changed)
        self.rb_search.connect("toggled", self.on_mode_changed)
        self.rb_docs.connect("toggled", self.on_mode_changed)

        # === Determine initial mode ===
        if initial_query and initial_docs:
            self.rb_docs.set_active(True)
            self.query_entry.set_text(initial_query)
            self.docs_buffer.set_text('\n'.join(initial_docs))
            self.mode = self.MODE_DOCS
        elif initial_docs:
            self.rb_docs.set_active(True)
            self.docs_buffer.set_text('\n'.join(initial_docs))
            self.mode = self.MODE_DOCS
        elif initial_query:
            self.rb_clipboard.set_active(True)
            self.query_entry.set_text(initial_query)
            self.mode = self.MODE_CLIPBOARD
        else:
            self.rb_search.set_active(True)
            self.mode = self.MODE_SEARCH

        self._apply_mode()
        self._in_init = False

        self.show_all()
        self.resize(width, height)

        if self.mode == self.MODE_DOCS:
            self.docs_frame.show_all()
        else:
            self.docs_frame.hide()

    def _on_map_event(self, widget, event):
        if self.pos_x is not None and self.pos_y is not None:
            for _ in range(10):
                r = subprocess.run(
                    ['hyprctl', 'dispatch', 'movewindowpixel', 'exact',
                     f'{self.pos_x} {self.pos_y}, class:^(ai-assist)$'],
                    capture_output=True, timeout=2)
                if r.returncode == 0:
                    break
                time.sleep(0.002)
        return False

    def _apply_mode(self):
        if self.mode == self.MODE_CLIPBOARD:
            self.query_entry.set_editable(False)
        else:
            self.query_entry.set_editable(True)

    def on_mode_changed(self, widget):
        if self._in_init:
            return
        if not widget.get_active():
            return
        if self.processing:
            return

        if widget == self.rb_clipboard:
            self.mode = self.MODE_CLIPBOARD
            if self.docs_frame.get_visible():
                self.docs_frame.hide()
            self.query_entry.set_editable(False)
            self.query_entry.set_text("")
            clipboard = self.get_clipboard()
            if clipboard:
                self.query_entry.set_text(clipboard)
            self.query_entry.grab_focus()
        elif widget == self.rb_search:
            self.mode = self.MODE_SEARCH
            if self.docs_frame.get_visible():
                self.docs_frame.hide()
            self.query_entry.set_editable(True)
            self.query_entry.set_text("")
            self.query_entry.grab_focus()
        elif widget == self.rb_docs:
            self.mode = self.MODE_DOCS
            self.docs_frame.show_all()
            self.query_entry.set_editable(True)
            self.query_entry.set_text("")
            self.query_entry.grab_focus()

    def add_css(self, text, style=None):
        if style == "bold":
            tag = self.buffer.create_tag(None, weight=Pango.Weight.BOLD)
            self.buffer.insert_with_tags(self.buffer.get_end_iter(), text, tag)
        elif style == "dim":
            tag = self.buffer.create_tag(None, foreground="#555555")
            self.buffer.insert_with_tags(self.buffer.get_end_iter(), text, tag)
        else:
            self.buffer.insert(self.buffer.get_end_iter(), text)

    def append_text(self, text, style=None):
        def closure(t, s):
            self.add_css(t, s)
            adj = self.scrolled.get_vadjustment()
            adj.set_value(adj.get_upper())
        GLib.idle_add(closure, text, style)

    def on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            Gtk.main_quit()
            return True
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            if event.keyval == Gdk.KEY_1:
                self.rb_clipboard.set_active(True)
                return True
            elif event.keyval == Gdk.KEY_2:
                self.rb_search.set_active(True)
                return True
            elif event.keyval == Gdk.KEY_3:
                self.rb_docs.set_active(True)
                return True
        return False

    def get_clipboard(self):
        for cmd in [['wl-paste'], ['wl-paste', '-p']]:
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=1)
                if result.returncode == 0:
                    text = result.stdout.decode('utf-8').strip()
                    if text:
                        return text
            except Exception:
                pass
        return None

    def search_web(self, query):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=10))
            if not results:
                return "Нет результатов поиска"
            snippets = []
            for i, r in enumerate(results, 1):
                title = r.get('title', '').strip()
                body = r.get('body', '').strip()
                href = r.get('href', '').strip()
                entry = f"{i}. {title}" if title else f"{i}."
                if body:
                    entry += f": {body}"
                if href:
                    entry += f" [{href}]"
                snippets.append(entry)
            return "\n".join(snippets)
        except Exception as e:
            return f"Ошибка поиска: {e}"

    def on_go(self, widget=None):
        if self.processing:
            return

        if self.mode == self.MODE_CLIPBOARD:
            query = self.get_clipboard()
            if not query:
                self.append_text("Буфер обмена пуст\n", style="dim")
                return
        elif self.mode == self.MODE_SEARCH:
            query = self.query_entry.get_text().strip()
            if not query:
                return
        elif self.mode == self.MODE_DOCS:
            query = self.query_entry.get_text().strip()
            if not query:
                return
            doc_start = self.docs_buffer.get_start_iter()
            doc_end = self.docs_buffer.get_end_iter()
            doc_sources = self.docs_buffer.get_text(doc_start, doc_end, False).strip()
            if not doc_sources:
                self.append_text("Укажите источники документации\n", style="dim")
                return

        self.processing = True
        self.cancelled = False
        self.stop_button.show()
        self.query_entry.set_sensitive(False)
        self.go_button.set_sensitive(False)
        self.follow_entry.set_sensitive(False)

        if self.mode == self.MODE_DOCS:
            self.append_text(f"▶ {query} (по документации)\n\n", style="bold")
            threading.Thread(target=self.answer_with_docs, args=(query, doc_sources), daemon=True).start()
        else:
            self.append_text(f"▶ {query}\n\n", style="bold")
            threading.Thread(target=self.answer_with_search, args=(query,), daemon=True).start()

    def answer_with_search(self, text):
        self.append_text("Поиск... ", style="dim")
        web = self.search_web(text)
        self.first_web = web
        self.append_text("OK\n\n", style="dim")

        prompt = f"Запрос пользователя: {text}\n\n"
        if web:
            prompt += f"Информация из интернета:\n{web}\n\n"
        prompt += "Ответ:"

        self._stream_answer(prompt)

    def answer_with_docs(self, text, doc_sources):
        self.append_text("Загрузка документации...\n", style="dim")
        doc_content = self.load_documentation(doc_sources)
        if not doc_content or doc_content.startswith("Ошибка"):
            if doc_content:
                self.append_text(f"{doc_content}\n", style="dim")
            GLib.idle_add(self.done)
            return
        self.append_text(f"OK (всего {len(doc_content)} символов)\n\n", style="dim")

        prompt = f"Запрос пользователя: {text}\n\n"
        prompt += f"Документация:\n{doc_content}\n\n"
        prompt += "Ответ:"

        self._stream_answer(prompt)

    def on_stop(self, widget=None):
        self.cancelled = True

    def _stream_ollama(self, payload):
        try:
            resp = requests.post(OLLAMA_URL, json=payload, stream=True, timeout=60)
            full = ""
            for line in resp.iter_lines():
                if self.cancelled:
                    resp.close()
                    break
                if line:
                    data = json.loads(line)
                    chunk = data.get('response', '')
                    if chunk:
                        full += chunk
                        self.append_text(chunk)
                    if 'context' in data:
                        self.context = data['context']
            if full.strip() and not self.cancelled:
                self.append_text("\n\n")
        except requests.exceptions.ConnectionError:
            self.append_text("Ошибка: Ollama не запущен\n", style="dim")
        except Exception as e:
            self.append_text(f"Ошибка: {e}\n", style="dim")
        GLib.idle_add(self.done)

    def _stream_answer(self, prompt):
        payload = {
            'model': MODEL,
            'system': SYSTEM_PROMPT,
            'prompt': prompt,
            'stream': True,
            'num_ctx': 32768,
            'num_predict': 8192,
        }
        self._stream_ollama(payload)

    def on_follow_activate(self, entry):
        text = entry.get_text().strip()
        if not text or self.processing:
            return
        entry.set_text("")

        if text.startswith('/doc '):
            doc_src = text[5:].strip()
            self.append_text(f"⏳ Загрузка документации: {doc_src}\n", style="dim")
            self.follow_entry.set_sensitive(False)
            self.processing = True
            self.cancelled = False
            self.stop_button.show()
            threading.Thread(target=self.load_doc_and_answer, args=(doc_src,), daemon=True).start()
            return

        self.append_text(f"\n▶ {text}\n", style="bold")
        self.follow_entry.set_sensitive(False)
        self.processing = True
        self.cancelled = False
        self.stop_button.show()
        threading.Thread(target=self.answer_followup, args=(text,), daemon=True).start()

    def answer_followup(self, text):
        web = None
        if self.context:
            self.append_text("Отвечаю по контексту...\n\n", style="dim")
        else:
            self.append_text("Поиск... ", style="dim")
            web = self.search_web(text)
            self.first_web = web
            self.append_text("OK\n\n", style="dim")

        prompt = f"Запрос пользователя: {text}\n\n"
        if self.first_web:
            prompt += f"Информация из интернета:\n{self.first_web}\n\n"
        prompt += "Ответ:"

        payload = {
            'model': MODEL,
            'system': SYSTEM_PROMPT,
            'prompt': prompt,
            'stream': True,
            'num_ctx': 32768,
            'num_predict': 8192,
        }
        if self.context:
            del payload['system']
            payload['context'] = self.context
        self._stream_ollama(payload)

    def load_doc_and_answer(self, doc_src):
        doc_content = self.load_documentation(doc_src)
        if not doc_content or doc_content.startswith("Ошибка"):
            if doc_content:
                self.append_text(f"{doc_content}\n", style="dim")
            GLib.idle_add(self.done)
            return
        self.append_text(f"OK (всего {len(doc_content)} символов)\n\n", style="dim")
        self.context = None

        prompt = f"Ответь на основе предоставленной документации:\n{doc_content}\n\nОтвет:"

        payload = {
            'model': MODEL,
            'system': SYSTEM_PROMPT,
            'prompt': prompt,
            'stream': True,
            'num_ctx': 32768,
            'num_predict': 8192,
        }
        self._stream_ollama(payload)

    def load_documentation(self, sources_text):
        sources = [s.strip() for s in sources_text.split('\n') if s.strip()]
        if not sources:
            return "Ошибка: не указаны источники документации"

        contents = []
        for src in sources:
            self.append_text(f"  {src}... ", style="dim")
            content = self._load_single_doc(src)
            if content and not content.startswith("Ошибка"):
                self.append_text(f"OK ({len(content)} символов)\n", style="dim")
                contents.append(f"--- {src} ---\n{content}")
            else:
                self.append_text(f"ОШИБКА\n", style="dim")
                if content:
                    contents.append(f"--- {src} ---\n{content}")

        if not contents:
            return "Ошибка: не удалось загрузить ни одного источника"

        return "\n\n".join(contents)

    def _load_single_doc(self, source):
        if source.startswith('http://') or source.startswith('https://'):
            return self._fetch_url(source)
        elif source.startswith('man:'):
            return self._fetch_man(source[4:])
        elif source.startswith('arch:'):
            page = source[5:].strip()
            url = f'https://wiki.archlinux.org/title/{page.replace(" ", "_")}'
            return self._fetch_url(url)
        elif source.startswith('gh:'):
            repo = source[3:].strip()
            url = f'https://raw.githubusercontent.com/{repo}/master/README.md'
            return self._fetch_url(url)
        elif source.startswith('file:'):
            return self._read_file(source[5:])
        elif source.startswith('~/') or source.startswith('/'):
            return self._read_file(source)
        else:
            return self._fetch_url(f'https://{source}')

    def _fetch_url(self, url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:134.0) Gecko/20100101 Firefox/134.0'}
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            text = resp.text
            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'&[a-zA-Z]+;', ' ', text)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()[:15000]
        except Exception as e:
            return f"Ошибка загрузки {url}: {e}"

    def _fetch_man(self, name):
        try:
            env = os.environ.copy()
            env['MANWIDTH'] = '120'
            result = subprocess.run(['man', name], capture_output=True, timeout=10, env=env)
            if result.returncode != 0:
                return f"Man-страница '{name}' не найдена (код {result.returncode})"
            col = subprocess.run(
                ['col', '-b'],
                input=result.stdout,
                capture_output=True, timeout=5
            )
            text = col.stdout.decode('utf-8', errors='replace')
            return text.strip()[:15000]
        except FileNotFoundError:
            return f"Man-страница '{name}' не найдена (man не установлен)"
        except subprocess.TimeoutExpired:
            return f"Man-страница '{name}' слишком долго грузится"
        except Exception as e:
            return f"Ошибка man {name}: {e}"

    def _read_file(self, path):
        path = os.path.expanduser(path)
        try:
            with open(path, 'r') as f:
                return f.read()[:15000]
        except Exception as e:
            return f"Ошибка чтения файла {path}: {e}"

    def done(self):
        self.query_entry.set_sensitive(True)
        self.go_button.set_sensitive(True)
        self.follow_entry.set_sensitive(True)
        self.follow_entry.grab_focus()
        self.processing = False
        self.cancelled = False
        self.stop_button.hide()


def main():
    width = 896
    height = 240
    initial_query = None
    initial_docs = []
    pos_x = None
    pos_y = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--width' and i + 1 < len(args):
            width = int(args[i + 1])
            i += 2
        elif args[i] == '--height' and i + 1 < len(args):
            height = int(args[i + 1])
            i += 2
        elif args[i] == '--query' and i + 1 < len(args):
            initial_query = args[i + 1]
            i += 2
        elif args[i] == '--doc' and i + 1 < len(args):
            initial_docs.append(args[i + 1])
            i += 2
        elif args[i] == '--x' and i + 1 < len(args):
            pos_x = int(args[i + 1])
            i += 2
        elif args[i] == '--y' and i + 1 < len(args):
            pos_y = int(args[i + 1])
            i += 2
        else:
            i += 1

    style_provider = Gtk.CssProvider()
    style_provider.load_from_data(CSS.encode())
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        style_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    win = AIAssistWindow(width, height, initial_query, initial_docs, pos_x, pos_y)
    Gtk.main()


if __name__ == '__main__':
    main()
