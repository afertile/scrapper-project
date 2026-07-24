# Company Contact Scraper MVP

Минимальный Python-скрипт для проекта базы данных и веб-скраппинга. Он принимает список сайтов компаний и пытается найти:

- название компании;
- email;
- телефоны;
- страницу контактов;
- ссылки на соцсети.

## 1. Установка инструментов

Установи Python 3.11 или новее:

```bash
python --version
```

Создай виртуальное окружение:

```bash
python -m venv .venv
```

Активируй его:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

Установи библиотеки:

```bash
pip install -r requirements.txt
```

## 2. Подготовка входного файла

Вариант 1: простой `sites.txt`, по одному сайту на строку:

```text
https://example.com
https://some-company.ru
```

Вариант 2: CSV-файл с колонкой `url`:

```csv
url
https://example.com
https://some-company.ru
```

## 3. Запуск

```bash
python scraper.py --input sites.txt --output results.csv
```

После запуска появится файл `results.csv`.

## 4. Как дебажить

Запусти на одном сайте:

```bash
python scraper.py --input sites.txt --output results.csv --max-pages 1
```

Если сайт не парсится:

- проверь, открывается ли сайт в браузере;
- попробуй увеличить таймаут: `--timeout 30`;
- посмотри колонку `error` в `results.csv`;
- проверь, есть ли контакты прямо в HTML страницы, потому что этот MVP пока не исполняет JavaScript.

## 5. Следующий шаг

Когда CSV-результат станет стабильным, следующий логичный шаг - сохранять данные напрямую в PostgreSQL:

- таблица `companies`;
- таблица `company_contacts`;
- таблица `scrape_runs`;
- антидубли по `domain`, `email`, `phone`.

Пока CSV удобнее для дебага: можно быстро открыть результат и понять, что именно нашел скрипт.
