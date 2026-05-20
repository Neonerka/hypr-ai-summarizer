#!/usr/bin/env python3
import subprocess
import sys
import json
import requests
from ddgs import DDGS

MODEL = 'qwen2.5:3b-instruct'
OLLAMA_URL = 'http://localhost:11434/api/generate'
SYSTEM_PROMPT = (
    "Ты — подробный CLI-помощник сисадмина на Arch Linux. "
    "Отвечай на русском языке. Всегда на русском. Никогда не отвечай "
    "на английском, китайском или любом другом языке, только на русском.\n\n"
    "Если в предоставленной информации из интернета есть текст на иностранном "
    "языке — переведи его на русский и дай развёрнутый ответ. "
    "Не используй таблицы для переводов. Не используй ASCII-рисование. "
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

def get_selection():
    for cmd in [['wl-paste'], ['wl-paste', '-p']]:
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=1)
            if result.returncode == 0:
                text = result.stdout.decode('utf-8').strip()
                if text:
                    return text
        except:
            pass
    return None

def search_web(query):
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

def ask_ollama(query, context):
    prompt = f"Запрос пользователя: {query}\n\nИнформация из интернета:\n{context}"
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={'model': MODEL, 'system': SYSTEM_PROMPT, 'prompt': prompt, 'stream': True},
            stream=True, timeout=60
        )
        for line in resp.iter_lines():
            if line:
                data = json.loads(line)
                chunk = data.get('response', '')
                if chunk:
                    print(chunk, end='', flush=True)
        print()
    except requests.exceptions.ConnectionError:
        print("Ошибка: Ollama не запущен (http://localhost:11434)")
    except Exception as e:
        print(f"Ошибка Ollama: {e}")

def main():
    print("Читаю буфер...", end=' ', flush=True)
    query = get_selection()
    if not query:
        print("пусто")
        print("Нет выделенного текста")
        input()
        sys.exit(1)
    print("OK")
    print(f"--- {query[:80]}---")
    print()
    print("Ищу в интернете...", end=' ', flush=True)
    context = search_web(query)
    print("OK")
    print()
    ask_ollama(query, context)
    input()

if __name__ == '__main__':
    main()
