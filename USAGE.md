# Q&A Generator - OpenAI/Claude Edition

A clean, professional Q&A generator for interview preparation using OpenAI and Claude AI.

## ✅ What's Cleaned Up

- ❌ Removed Ollama (unreliable local processing)
- ❌ Removed complex fallback generation methods  
- ❌ Removed unused test files and clutter
- ✅ Clean OpenAI + Claude integration only
- ✅ Simple bulk question processing
- ✅ Professional AI-generated answers

## 🔑 Setup

### 1. API Keys (in .env file)
```bash
# OpenAI API Key (already set)
OPENAI_API_KEY=sk-proj-iAAA...

# Claude API Key (already set)  
ANTHROPIC_API_KEY=sk-ant-api03-Nck...
```

### 2. Run the App
```bash
python app.py
```

### 3. Access
- Web UI: http://localhost:8080
- The app automatically uses OpenAI (detected your key)

## 🚀 How to Use

### Bulk Question Processing
1. Go to "Bulk Questions Processing" section
2. Enter questions one per line:
   ```
   What is Angular and why is it used?
   How does dependency injection work in Angular?
   What are Angular directives and their types?
   ```
3. Click "Process with AI"
4. Watch real-time processing with OpenAI
5. Download comprehensive JSON results

### Features
- ✅ **AI-Generated Answers**: No need to provide answers, just questions
- ✅ **Professional Quality**: Uses OpenAI GPT-4o-mini for best results
- ✅ **Comprehensive JSON**: 20 alternative questions, detailed answers, code examples
- ✅ **Real-time Monitoring**: Live progress updates
- ✅ **Master File System**: Accumulates all data in single files
- ✅ **Clean Interface**: No clutter, just what you need

## 📁 File Structure (Cleaned)
```
qa-generator/
├── app.py                 # Main Flask app
├── .env                   # API keys (configured)
├── src/
│   ├── ai_client.py      # Clean OpenAI/Claude client
│   └── scraper.py        # Web scraping (optional)
├── templates/
│   └── index.html        # Web interface
├── static/
│   └── js/app.js         # Frontend logic
├── ollama/
│   └── prompt_template.txt # AI prompt template
└── data/                 # Generated JSON files
```

## 🎯 Perfect For
- Training semantic LLMs with high-quality Q&A data
- Interview preparation systems
- Technical knowledge bases
- Educational content generation

No more unreliable Ollama, no more dummy content - just professional AI-powered Q&A generation! 🚀