# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a real-time Q&A scraper and generator that intelligently extracts interview questions from multiple websites and uses AI (OpenAI or Claude) to convert them into structured JSON format. Features multiple web interfaces with real-time monitoring via WebSockets and intelligent caching.

## Development Setup

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install additional AI provider dependencies if missing
pip install openai anthropic python-dotenv

# Set up AI provider API keys (at least one required)
export OPENAI_API_KEY="your-key-here"
export ANTHROPIC_API_KEY="your-key-here"
```

## Common Commands

```bash
# Run the web application (auto-finds free port)
python start_app.py

# Run directly on specific port
python app.py

# Test AI connection
python -c "from src.ai_client import AIClient; client = AIClient(); print(client.test_connection())"

# Test scraper directly
python -c "from src.scraper import InterviewScraper; print(len(InterviewScraper().scrape_interviewbit_angular(5)))"

# Test cache system
python test_cache.py

# Test preview functionality
python test_preview_fix.py
```

## Architecture

### Core Components

- **app.py**: Main Flask application with WebSocket support and multiple UI routes
- **start_app.py**: Smart port management script that finds free ports and kills existing instances
- **src/ai_client.py**: Unified AI client supporting OpenAI and Claude APIs
- **src/cache_manager.py**: Intelligent caching system to reduce API costs
- **src/scraper.py**: Multi-source web scraper with fallback mechanisms
- **templates/**: Multiple web interfaces (elite_dashboard, index, index_new)
- **static/**: CSS and JavaScript assets for different UI variants

### Data Flow

1. User configures AI provider (OpenAI/Claude) and model
2. User either:
   - Configures scraping parameters and sources
   - Inputs custom URLs for scraping
   - Provides bulk questions via textarea
3. Background job starts scraping/processing
4. Raw Q&A pairs are processed through selected AI model
5. Responses are cached to avoid duplicate API calls
6. Structured JSON is generated following prompt template
7. Real-time updates sent via WebSocket
8. Master JSON files saved with automatic backups

### Web Interface Features

- **Multiple UIs**: Elite dashboard (default), original, and modern interfaces
- **AI Provider Selection**: Switch between OpenAI and Claude with different models
- **Smart Caching**: Automatic response caching with similarity matching
- **Real-time monitoring**: Live feed of scraping and processing progress
- **Multi-source scraping**: InterviewBit, GeeksforGeeks, JavaTpoint + custom URLs
- **Bulk processing**: Process questions directly from textarea input
- **Preview mode**: View scraped questions before processing
- **Master file management**: Accumulative data storage with backups
- **Background job management**: Track and monitor processing jobs

### AI Client System

The `AIClient` class provides:
- Support for OpenAI models: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo
- Support for Claude models: claude-3-5-sonnet, claude-3-5-haiku, claude-3-opus, claude-3-sonnet, claude-3-haiku
- Default models: OpenAI (gpt-4o-mini), Claude (claude-3-5-haiku-20241022)
- Automatic caching with intelligent similarity matching
- Cost estimation and cache statistics
- Fallback prompt templates

### Caching Intelligence

The caching system features:
- Question normalization for better cache hits
- Similarity matching (80% threshold)
- Cost estimation and savings tracking
- Provider-specific cache files
- Automatic cache cleanup and optimization
- 24-hour cache expiration

## Configuration

- **Port**: Auto-detects free port starting from 8080 (configurable in start_app.py)
- **AI Models**: Configurable via web UI or AI client initialization
- **Cache**: Located in `cache/` directory with separate files per provider
- **Data**: Master files in `data/` with timestamped backups in `data/backups/`
- **Prompt Template**: Located in `ollama/prompt_template.txt`
- **Topics**: Support for multiple topics (angular, sap, selected)

## Web Interface Routes

- `/` - Elite dashboard (primary interface)
- `/old` - Original interface
- `/modern` - Modern interface variant
- API endpoints for provider management, scraping, and processing

## Troubleshooting

- **AI Connection**: Ensure API keys are set: `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`
- **Port Conflicts**: Use `start_app.py` to auto-find free ports
- **Cache Issues**: Check `cache/` directory permissions and file corruption
- **Scraping Issues**: Verify network connectivity and website structure changes
- **WebSocket**: Check browser console for connection errors
- **Missing Dependencies**: Install `openai`, `anthropic`, and `python-dotenv` if not in requirements.txt