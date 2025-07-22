# 🤖 Q&A Generator - Real-time Interview Question Scraper

A sophisticated web application that intelligently scrapes interview questions from multiple sources and converts them into structured JSON using AI. Features a real-time web interface with live monitoring.

## ✨ Features

- **🌐 Multi-source scraping**: InterviewBit, GeeksforGeeks, JavaTpoint
- **🤖 AI-powered structuring**: Uses Ollama with phi3 model for JSON generation
- **📱 Real-time web UI**: Live progress monitoring with WebSocket updates
- **🎯 Smart extraction**: Intelligent Q&A detection with fallback mechanisms
- **📊 Comprehensive output**: Rich JSON schema with categories, tags, and metadata
- **💾 Auto-save**: Automatic JSON file generation and download

## 🚀 Quick Start

### Prerequisites

1. **Ollama** installed and running:
   ```bash
   # Install Ollama from https://ollama.ai
   ollama pull phi3:latest
   ollama serve
   ```

2. **Python 3.9+** installed

### Setup

1. **Clone and setup**:
   ```bash
   git clone <your-repo>
   cd qa-generator
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Test setup**:
   ```bash
   python test_setup.py
   ```

4. **Run the application**:
   ```bash
   python app.py
   ```

5. **Open in browser**:
   ```
   http://localhost:5000
   ```

## 🎮 Usage

1. **Configure scraping parameters**:
   - Select topic (Angular, React, JavaScript, etc.)
   - Choose sources to scrape from
   - Set questions limit per source

2. **Start scraping**:
   - Click "Start Scraping" button
   - Watch real-time progress in the live feed
   - View processed questions in the data preview

3. **Download results**:
   - JSON files auto-saved to `data/` directory
   - Download via browser using "Download JSON" button

## 📊 Output Structure

Each question is converted to comprehensive JSON with:

```json
{
  "question-id": {
    "primaryQuestion": "What is Angular?",
    "alternativeQuestions": ["What do you know about Angular?", ...],
    "answerDescriptions": ["Brief summary points", ...],
    "answer": {
      "summary": "One-line summary",
      "detailed": "Comprehensive explanation with code examples",
      "whenToUse": "Usage scenarios",
      "realWorldContext": "Real-world applications"
    },
    "category": "Frontend",
    "subcategory": "Framework",
    "difficulty": "beginner",
    "tags": ["angular", "typescript", "spa"],
    "conceptTriggers": ["Related concepts", ...],
    "naturalFollowups": ["Follow-up questions", ...],
    "relatedQuestions": ["Similar questions", ...],
    "commonMistakes": [
      {"mistake": "Description", "explanation": "Why it's wrong"}
    ],
    "confidence": "high",
    "lastUpdated": "2025-06-26",
    "verified": false
  }
}
```

## 🏗️ Architecture

- **Backend**: Flask + SocketIO for real-time communication
- **Scraping**: BeautifulSoup with intelligent parsing strategies
- **AI Processing**: Ollama integration with phi3 model
- **Frontend**: Modern web UI with real-time updates
- **Storage**: JSON files with structured data

## 🛠️ Development

### Project Structure
```
qa-generator/
├── app.py                 # Main Flask application
├── src/
│   ├── scraper.py        # Web scraping logic
│   └── ollama_client.py  # Ollama integration
├── templates/
│   └── index.html        # Web UI template
├── static/
│   ├── css/style.css     # Styling
│   └── js/app.js         # Frontend JavaScript
├── data/                 # Generated JSON files
├── ollama/
│   └── prompt_template.txt # AI prompt template
└── test_setup.py         # Setup verification
```

### Available Commands

```bash
# Run web application
python app.py

# Test Ollama connection
python -c "from src.ollama_client import OllamaClient; print(OllamaClient().test_connection())"

# Test scraper directly
python -c "from src.scraper import InterviewScraper; print(len(InterviewScraper().scrape_interviewbit_angular(3)))"

# Run all tests
python test_setup.py
```

## 🔧 Configuration

- **Port**: Default 5000 (configurable in `app.py`)
- **Ollama Model**: phi3:latest (configurable in `src/ollama_client.py`)
- **Rate Limiting**: Built-in delays between requests
- **Output Directory**: `data/` (auto-created)

## 🐛 Troubleshooting

### Common Issues

1. **Ollama Connection Failed**:
   ```bash
   ollama serve  # Start Ollama service
   ollama pull phi3:latest  # Install model
   ```

2. **Import Errors**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Scraping Issues**:
   - Check internet connection
   - Websites may have changed structure
   - Try different sources

4. **WebSocket Connection Issues**:
   - Check browser console for errors
   - Ensure no firewall blocking port 5000

### Getting Help

- Check the live feed for real-time error messages
- Review browser console for JavaScript errors
- Verify Ollama is running: `ollama list`

## 📝 License

MIT License - feel free to use for your projects!

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Add more scraping sources
- Improve AI prompt templates
- Enhance UI/UX
- Add export formats (CSV, Excel, etc.)
- Add question deduplication
- Implement caching mechanisms