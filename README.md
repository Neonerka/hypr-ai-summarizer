# AI Assist — локальный ИИ-ассистент для Hyprland

Выпадающее окно с ИИ-помощником поверх рабочего стола.  
Читает выделенный текст, ищет в DuckDuckGo, генерирует ответ через локальный Ollama.

## Как это выглядит

- Нажимаете `Super+Shift+A`
- Если в буфере обмена есть текст — открывается терминал в верхней части экрана, в нём стримится ответ
- Если буфер пуст — уже открытое окно прячется/показывается (toggle)

## Зависимости

- `foot` — терминал
- `wl-clipboard` — чтение буфера обмена
- `python-requests` — http-запросы к Ollama
- `duckduckgo_search` (pip) — поиск в DuckDuckGo
- `Ollama` с моделью (например `qwen2.5:3b-instruct`)

Установка:
```bash
sudo pacman -S foot wl-clipboard python-requests
pip install duckduckgo_search
ollama pull qwen2.5:3b-instruct
```

## Файлы

| Файл | Назначение |
|---|---|
| `~/scripts/ai-assist.py` | Читает буфер, ищет в DDG, стримит ответ Ollama |
| `~/scripts/toggle-ai-assist.sh` | Управление окном: kill+launch или hide/show |

## Конфигурация Hyprland

### Window rules (`~/.config/hypr/hyprland/rules.conf`)
```conf
windowrule = float true, match:class ai-assist
windowrule = opacity 0.85, match:class ai-assist
windowrule = dim_around true, match:class ai-assist
windowrule = animation slide, match:class ai-assist
```

### Клавиша (`~/.config/hypr/hyprland/keybinds.conf`)
```conf
bind = Super+Shift, A, exec, /home/neonerka/scripts/toggle-ai-assist.sh
```

## Как работает

1. **ai-assist.py**: берёт текст из CLIPBOARD (Ctrl+C), если пусто — fallback PRIMARY (выделение мышью)
2. Ищет в DuckDuckGo (10 результатов)
3. Отправляет запрос + контекст в локальный Ollama (`localhost:11434`)
4. Стримит ответ посимвольно в stdout
5. В конце ждёт `Enter` (чтобы окно не закрылось сразу)

6. **toggle-ai-assist.sh**:
   - Если в буфере есть текст — убивает старое окно (если было) и запускает новое
   - Если буфер пуст — прячет окно в special workspace или возвращает обратно
   - Размер окна: 35% × 22% от разрешения активного монитора
   - Позиция: в верхней части экрана по центру
   - Поддерживает повёрнутые мониторы (portrait)

## Особенности

- Весь трафик локальный — ничего не уходит в интернет кроме поиска DuckDuckGo
- Модель Ollama запущена локально (не требует GPU)
- Промпт на русском, ответы всегда на русском
- В конце ответа — краткая сводка (не надо листать вверх)
