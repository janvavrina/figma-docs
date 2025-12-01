# Figma Documentation Generator

Nástroj pro automatickou generaci user/dev dokumentace z Figma designů pomocí lokálních LLM modelů (Ollama).

## Funkce

- **Figma integrace** - Načítání designů přes Figma REST API
- **Automatická detekce změn** - Polling pro sledování změn ve Figma souborech
- **Generování dokumentace** - LLM generuje Markdown/HTML dokumentaci z designů
- **RAG Chatbot** - Dotazování nad vygenerovanou dokumentací
- **Code Agent** - Analýza zdrojového kódu a generování technické dokumentace
- **App Agent** - Analýza běžící aplikace a generování uživatelské dokumentace

## Požadavky

- Python 3.11+
- Node.js 20+
- Ollama s nainstalovanými modely:
  - `gemma3:27b` (dokumentace)
  - `granite3.1-dense:8b` (chatbot)
  - `Phi-4-mini-instruct:latest` (analýza kódu)

## Instalace

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# nebo: venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

## Konfigurace

1. Zkopírujte `.env.example` do `.env` a nastavte:
   ```
   FIGMA_API_TOKEN=váš_figma_api_token
   ```

2. Upravte `config.yaml` podle potřeby:
   - Modely pro různé úlohy
   - Polling interval
   - Sledované Figma soubory

## Spuštění

### Ollama

Ujistěte se, že Ollama běží:
```bash
ollama serve
```

Stáhněte potřebné modely:
```bash
ollama pull gemma3:27b
ollama pull granite3.1-dense:8b
ollama pull nomic-embed-text
```

### Backend

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm run dev
```

Aplikace bude dostupná na http://localhost:3000

## API Endpoints

### Figma Files
- `GET /api/figma/files` - Seznam sledovaných souborů
- `POST /api/figma/files` - Přidání souboru ke sledování
- `DELETE /api/figma/files/{file_key}` - Odebrání souboru

### Documentation
- `GET /api/docs` - Seznam vygenerované dokumentace
- `POST /api/docs/generate` - Generování dokumentace
- `GET /api/docs/{doc_id}` - Detail dokumentace

### Chat
- `POST /api/chat` - Chat s dokumentací

### Analysis
- `POST /api/analyze/code` - Analýza zdrojového kódu
- `POST /api/analyze/app` - Analýza aplikace

### Detection Control
- `POST /api/detection/start` - Spuštění detekce změn
- `POST /api/detection/stop` - Zastavení detekce změn

## Struktura projektu

```
figma-docs/
├── backend/
│   ├── app/
│   │   ├── api/           # REST API endpoints
│   │   ├── core/          # Konfigurace
│   │   ├── models/        # Pydantic modely
│   │   └── services/
│   │       ├── figma/     # Figma API + change detection
│   │       ├── llm/       # LangChain + Ollama
│   │       ├── docs/      # Generování dokumentace + chatbot
│   │       └── agents/    # Code/App agenti
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── views/         # Stránky
│       ├── components/    # UI komponenty
│       └── stores/        # Pinia stores
├── docs/                  # Vygenerovaná dokumentace
├── config.yaml           # Konfigurace
└── docker-compose.yml
```

## Docker

Pro spuštění s Dockerem:

```bash
docker-compose up -d
```

**Poznámka:** Ollama by měla běžet na hostitelském stroji pro přístup k GPU.

## Licence

MIT

