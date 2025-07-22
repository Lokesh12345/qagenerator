"""
Main Flask application with real-time web scraping and JSON generation
"""
import os
import json
import time
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import logging

from src.scraper import InterviewScraper
from src.ai_client import AIClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables
scraper = InterviewScraper()
# AI clients - will be set based on user selection
current_ai_client = None
current_job = None
processed_data = {}

# Ensure data directory exists
os.makedirs('data', exist_ok=True)

class ScrapingJob:
    def __init__(self, job_id, topic, sources, limit_per_source):
        self.job_id = job_id
        self.topic = topic
        self.sources = sources
        self.limit_per_source = limit_per_source
        self.status = 'starting'
        self.progress = 0
        self.total_questions = 0
        self.processed_questions = 0
        self.scraped_data = []
        self.processed_data = {}
        self.errors = []
        self.start_time = datetime.now()

@app.route('/')
def index():
    """Serve the elite dashboard"""
    return render_template('elite_dashboard.html')

@app.route('/old')
def old_index():
    """Original UI"""
    return render_template('index.html')

@app.route('/modern')
def modern_index():
    """Modern UI"""
    return render_template('index_new.html')

@app.route('/api/set-ai-provider', methods=['POST'])
def set_ai_provider():
    """Set AI provider and model"""
    global current_ai_client
    
    try:
        data = request.json
        provider = data.get('provider', 'openai')
        model = data.get('model')
        
        # Create new AI client
        current_ai_client = AIClient(provider=provider, model=model)
        
        # Test connection
        if current_ai_client.test_connection():
            logger.info(f"AI provider set: {provider}/{model}")
            return jsonify({
                'status': 'success',
                'message': f'AI provider set to {provider}/{model}',
                'provider': provider,
                'model': model
            })
        else:
            return jsonify({
                'status': 'error',
                'error': 'Failed to connect to AI provider'
            }), 400
            
    except Exception as e:
        logger.error(f"Error setting AI provider: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/api/ai-providers')
def get_ai_providers():
    """Get available AI providers and models"""
    providers = {
        'openai': {
            'name': 'OpenAI',
            'models': [
                'gpt-4o',
                'gpt-4o-mini',
                'gpt-4-turbo',
                'gpt-3.5-turbo'
            ],
            'default': 'gpt-4o-mini'
        },
        'claude': {
            'name': 'Claude (Anthropic)',
            'models': [
                'claude-3-5-sonnet-20241022',
                'claude-3-5-haiku-20241022',
                'claude-3-opus-20240229',
                'claude-3-sonnet-20240229',
                'claude-3-haiku-20240307'
            ],
            'default': 'claude-3-5-haiku-20241022'
        }
    }
    
    return jsonify({
        'providers': providers,
        'current': {
            'provider': current_ai_client.provider if current_ai_client else None,
            'model': current_ai_client.model if current_ai_client else None
        }
    })

@app.route('/api/process-bulk-questions', methods=['POST'])
def process_bulk_questions():
    """Process bulk questions from textarea"""
    global current_job, current_ai_client
    
    if current_job and current_job.status in ['scraping', 'processing']:
        return jsonify({'error': 'Job already running'}), 400
    
    # Ensure we have an AI client
    if not current_ai_client:
        return jsonify({'error': 'No AI provider configured. Please set up OpenAI or Claude first.'}), 400
    
    data = request.json
    questions_text = data.get('questions', '').strip()
    topic = data.get('topic', 'angular')
    
    if not questions_text:
        return jsonify({'error': 'No questions provided'}), 400
    
    # Parse questions from textarea (one per line)
    questions = [q.strip() for q in questions_text.split('\n') if q.strip()]
    
    if not questions:
        return jsonify({'error': 'No valid questions found'}), 400
    
    # Create job
    job_id = f"bulk_job_{int(time.time())}"
    current_job = ScrapingJob(job_id, topic, [], 0)
    
    # Convert questions to Q&A format for processing
    current_job.scraped_data = []
    for i, question in enumerate(questions, 1):
        current_job.scraped_data.append({
            'id': f"{topic}-bulk-q{i}",
            'question': question,
            'answer': None,  # Will be generated by AI
            'source': 'bulk_input'
        })
    
    current_job.total_questions = len(questions)
    
    logger.info(f"Starting bulk questions job with {len(questions)} questions")
    
    # Start processing directly
    thread = threading.Thread(target=run_bulk_processing_job, args=(current_job,))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'job_id': job_id,
        'status': 'started',
        'message': f'Processing {len(questions)} questions with {current_ai_client.provider}'
    })

@app.route('/api/start-scraping', methods=['POST'])
def start_scraping():
    """Start scraping job"""
    global current_job
    
    if current_job and current_job.status in ['scraping', 'processing']:
        return jsonify({'error': 'Job already running'}), 400
    
    # Ensure we have an AI client
    global current_ai_client
    if not current_ai_client:
        # Default to OpenAI
        current_ai_client = AIClient(provider='openai')
    
    data = request.json
    
    # Check if this is a selected questions job
    if data.get('mode') == 'selected':
        selected_questions = data.get('selected_questions', [])
        topic = data.get('topic', 'selected')  # Use topic from frontend
        job_id = f"job_{int(time.time())}"
        current_job = ScrapingJob(job_id, topic, [], 0)
        current_job.scraped_data = selected_questions
        current_job.total_questions = len(selected_questions)
        
        logger.info(f"Starting selected questions job with {len(selected_questions)} questions")
        
        # Start processing directly (skip scraping)
        thread = threading.Thread(target=run_processing_job, args=(current_job,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'job_id': job_id,
            'status': 'started',
            'message': f'Processing {len(selected_questions)} selected questions'
        })
    
    # Regular scraping job
    topic = data.get('topic', 'angular')
    sources = data.get('sources', ['interviewbit', 'geeksforgeeks', 'javatpoint'])
    limit_per_source = data.get('limit_per_source', 10)
    
    job_id = f"job_{int(time.time())}"
    current_job = ScrapingJob(job_id, topic, sources, limit_per_source)
    
    # Start scraping in background thread
    thread = threading.Thread(target=run_scraping_job, args=(current_job,))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'job_id': job_id,
        'status': 'started',
        'message': 'Scraping job started'
    })

@app.route('/api/job-status')
def job_status():
    """Get current job status"""
    if not current_job:
        return jsonify({'status': 'no_job'})
    
    return jsonify({
        'job_id': current_job.job_id,
        'status': current_job.status,
        'progress': current_job.progress,
        'total_questions': current_job.total_questions,
        'processed_questions': current_job.processed_questions,
        'errors': current_job.errors,
        'start_time': current_job.start_time.isoformat()
    })

@app.route('/api/processed-data')
def get_processed_data():
    """Get processed data"""
    if not current_job:
        return jsonify({})
    
    return jsonify(current_job.processed_data)

@app.route('/api/download-json')
def download_json():
    """Download master JSON data"""
    topic = request.args.get('topic', 'angular')
    master_filename = f"qa_master_{topic}.json"
    master_filepath = os.path.join('data', master_filename)
    
    if not os.path.exists(master_filepath):
        return jsonify({'error': 'No master file found'}), 404
    
    try:
        with open(master_filepath, 'r') as f:
            master_data = json.load(f)
        
        return jsonify({
            'message': 'Master file loaded successfully',
            'filename': master_filename,
            'filepath': master_filepath,
            'total_entries': len(master_data),
            'data': master_data  # Include the actual data for download
        })
    except Exception as e:
        return jsonify({'error': f'Error loading master file: {str(e)}'}), 500

@app.route('/api/master-stats')
def master_stats():
    """Get statistics about master files"""
    stats = {}
    data_dir = 'data'
    
    try:
        for filename in os.listdir(data_dir):
            if filename.startswith('qa_master_') and filename.endswith('.json'):
                filepath = os.path.join(data_dir, filename)
                topic = filename.replace('qa_master_', '').replace('.json', '')
                
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                    
                    stats[topic] = {
                        'filename': filename,
                        'total_entries': len(data),
                        'file_size': os.path.getsize(filepath),
                        'last_modified': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
                    }
                except Exception as e:
                    logger.error(f"Error reading {filename}: {e}")
        
        return jsonify({
            'stats': stats,
            'total_files': len(stats)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/test-ai')
def test_ai():
    """Test current AI connection"""
    try:
        if not current_ai_client:
            return jsonify({
                'connected': False,
                'provider': None,
                'model': None,
                'status': 'error',
                'error': 'No AI provider selected'
            })
        
        is_connected = current_ai_client.test_connection()
        return jsonify({
            'connected': is_connected,
            'provider': current_ai_client.provider,
            'model': current_ai_client.model,
            'status': 'success'
        })
    except Exception as e:
        logger.error(f"Error testing AI: {e}")
        return jsonify({
            'connected': False,
            'provider': current_ai_client.provider if current_ai_client else None,
            'model': current_ai_client.model if current_ai_client else None,
            'status': 'error',
            'error': str(e)
        })

@app.route('/api/cache-stats')
def cache_stats():
    """Get AI cache statistics"""
    try:
        if not current_ai_client:
            return jsonify({
                'error': 'No AI provider selected',
                'status': 'error'
            })
        
        stats = current_ai_client.get_cache_stats()
        return jsonify({
            'status': 'success',
            'cache_stats': stats,
            'provider': current_ai_client.provider,
            'model': current_ai_client.model
        })
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        })

@app.route('/api/discover-questions', methods=['POST'])
def discover_questions():
    """Discover how many questions are available per source without full scraping"""
    try:
        data = request.json
        topic = data.get('topic', 'angular')
        sources = data.get('sources', [])
        
        if not sources:
            return jsonify({'error': 'No sources selected'}), 400
        
        logger.info(f"Discovering questions for topic: {topic}, sources: {sources}")
        
        discovery_results = {}
        total_available = 0
        
        for source in sources:
            try:
                # Get available question count for this source
                available_count = scraper.discover_question_count(topic, source)
                discovery_results[source] = {
                    'available': available_count,
                    'source_name': source.title()
                }
                total_available += available_count
                logger.info(f"Found {available_count} questions from {source}")
                
            except Exception as e:
                logger.error(f"Error discovering questions from {source}: {e}")
                discovery_results[source] = {
                    'available': 0,
                    'error': str(e),
                    'source_name': source.title()
                }
        
        return jsonify({
            'status': 'success',
            'topic': topic,
            'sources': discovery_results,
            'total_available': total_available
        })
        
    except Exception as e:
        logger.error(f"Error in discover_questions: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/scrape-url', methods=['POST'])
def scrape_url():
    """Scrape questions from a single URL"""
    try:
        data = request.json
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        if not url.startswith(('http://', 'https://')):
            return jsonify({'error': 'URL must start with http:// or https://'}), 400
        
        logger.info(f"Scraping URL: {url}")
        
        # Use the scraper to get questions from the URL
        questions = scraper.scrape_custom_url(url, limit=500)  # Get up to 500 questions
        
        logger.info(f"Found {len(questions)} questions from {url}")
        
        return jsonify({
            'questions': questions,
            'url': url,
            'count': len(questions)
        })
        
    except Exception as e:
        logger.error(f"Error scraping URL: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/preview-questions', methods=['POST'])
def preview_questions():
    """Preview questions before processing"""
    data = request.json
    topic = data.get('topic', 'angular') or 'angular'  # Ensure topic is never None
    sources = data.get('sources', [])
    custom_urls = data.get('custom_urls', [])
    limit_per_source = data.get('limit_per_source', 10)
    
    # Ensure topic is a string
    if not isinstance(topic, str):
        topic = 'angular'
    
    logger.info(f"Previewing questions - Topic: {topic}, Sources: {sources}, Custom URLs: {len(custom_urls)}")
    
    try:
        preview_data = []
        
        # Scrape from standard sources
        if 'interviewbit' in sources:
            try:
                if topic.lower() == 'angular':
                    logger.info(f"Scraping InterviewBit for {topic}")
                    questions = scraper.scrape_interviewbit_angular(limit_per_source)
                    preview_data.extend(questions)
                    logger.info(f"Found {len(questions)} questions from InterviewBit")
                else:
                    logger.info(f"InterviewBit scraping not implemented for topic: {topic}")
            except Exception as e:
                logger.error(f"Error scraping InterviewBit: {e}")
        
        if 'geeksforgeeks' in sources:
            try:
                logger.info(f"Scraping GeeksforGeeks for {topic}")
                questions = scraper.scrape_geeksforgeeks(topic, limit_per_source)
                preview_data.extend(questions)
                logger.info(f"Found {len(questions)} questions from GeeksforGeeks")
            except Exception as e:
                logger.error(f"Error scraping GeeksforGeeks: {e}")
        
        if 'javatpoint' in sources:
            try:
                logger.info(f"Scraping JavaTpoint for {topic}")
                questions = scraper.scrape_javatpoint(topic, limit_per_source)
                preview_data.extend(questions)
                logger.info(f"Found {len(questions)} questions from JavaTpoint")
            except Exception as e:
                logger.error(f"Error scraping JavaTpoint: {e}")
        
        # Handle custom URLs
        for url in custom_urls:
            if url.strip():
                try:
                    logger.info(f"Scraping custom URL: {url}")
                    custom_questions = scraper.scrape_custom_url(url.strip(), limit_per_source)
                    preview_data.extend(custom_questions)
                    logger.info(f"Found {len(custom_questions)} questions from custom URL")
                except Exception as e:
                    logger.error(f"Error scraping custom URL {url}: {e}")
        
        logger.info(f"Total questions found: {len(preview_data)}")
        
        # Remove duplicates
        unique_questions = remove_duplicates(preview_data)
        
        logger.info(f"After deduplication: {len(unique_questions)} unique questions")
        
        return jsonify({
            'questions': unique_questions,
            'total_found': len(preview_data),
            'unique_count': len(unique_questions),
            'duplicates_removed': len(preview_data) - len(unique_questions)
        })
        
    except Exception as e:
        logger.error(f"Error previewing questions: {e}")
        return jsonify({'error': str(e)}), 500

def remove_duplicates(questions):
    """Remove duplicate questions based on similarity"""
    unique_questions = []
    seen_questions = set()
    
    for q in questions:
        # Normalize question for comparison
        normalized = q['question'].lower().strip()
        normalized = ''.join(c for c in normalized if c.isalnum() or c.isspace())
        normalized = ' '.join(normalized.split())
        
        if normalized not in seen_questions:
            seen_questions.add(normalized)
            unique_questions.append(q)
        else:
            logger.info(f"Duplicate removed: {q['question'][:50]}...")
    
    return unique_questions

def run_scraping_job(job):
    """Run the scraping job in background"""
    try:
        job.status = 'checking_ai'
        emit_job_update(job)
        
        # Test AI connection
        if not current_ai_client.test_connection():
            job.status = 'error'
            job.errors.append(f'AI connection failed for {current_ai_client.provider}')
            emit_job_update(job)
            return
        
        job.status = 'scraping'
        emit_job_update(job)
        
        # Scrape questions based on topic and sources
        if job.topic.lower() == 'angular' and 'interviewbit' in job.sources:
            scraped_data = scraper.scrape_interviewbit_angular(job.limit_per_source)
            job.scraped_data.extend(scraped_data)
        
        if 'geeksforgeeks' in job.sources:
            scraped_data = scraper.scrape_geeksforgeeks(job.topic, job.limit_per_source)
            job.scraped_data.extend(scraped_data)
        
        if 'javatpoint' in job.sources:
            scraped_data = scraper.scrape_javatpoint(job.topic, job.limit_per_source)
            job.scraped_data.extend(scraped_data)
        
        job.total_questions = len(job.scraped_data)
        
        if job.total_questions == 0:
            job.status = 'error'
            job.errors.append('No questions scraped')
            emit_job_update(job)
            return
        
        # Continue with processing
        run_processing_job(job)
        
    except Exception as e:
        job.status = 'error'
        job.errors.append(f"Job failed: {str(e)}")
        emit_job_update(job)
        logger.error(f"Scraping job failed: {e}")

def run_bulk_processing_job(job):
    """Run bulk question processing job using only questions"""
    try:
        job.status = 'checking_ai'
        emit_job_update(job)
        
        # Test AI connection
        if not current_ai_client.test_connection():
            job.status = 'error'
            job.errors.append(f'AI connection failed for {current_ai_client.provider}')
            emit_job_update(job)
            return
        
        job.status = 'processing'
        emit_job_update(job)
        
        logger.info(f"Starting to process {job.total_questions} questions with {current_ai_client.provider}")
        
        # Process each question with AI
        for i, qa_item in enumerate(job.scraped_data):
            try:
                logger.info(f"Processing question {i+1}/{job.total_questions}: {qa_item['question'][:50]}...")
                
                # Emit detailed progress update
                socketio.emit('scraping_progress', {
                    'job_id': job.job_id,
                    'current_question': qa_item['question'][:100] + '...',
                    'current_answer_length': 0,
                    'progress': (i / job.total_questions) * 100,
                    'processed': i,
                    'total': job.total_questions,
                    'step': 'processing_with_ai',
                    'source': qa_item.get('source', 'bulk_input')
                })
                
                # Emit detailed step info
                socketio.emit('processing_step', {
                    'job_id': job.job_id,
                    'step': 'ai_start',
                    'question_id': qa_item['id'],
                    'question': qa_item['question'],
                    'answer_preview': 'Generating answer with AI...',
                    'timestamp': datetime.now().isoformat(),
                    'ai_provider': current_ai_client.provider
                })
                
                # Process with AI client (question only)
                start_time = time.time()
                try:
                    processed_item = current_ai_client.format_question_to_json(
                        qa_item['question'],
                        qa_item['id']
                    )
                except Exception as ai_error:
                    logger.error(f"AI processing error: {ai_error}")
                    processed_item = None
                
                processing_time = time.time() - start_time
                
                if processed_item:
                    job.processed_data.update(processed_item)
                    job.processed_questions += 1
                    
                    # Emit successful processing
                    socketio.emit('processing_step', {
                        'job_id': job.job_id,
                        'step': 'ai_success',
                        'question_id': qa_item['id'],
                        'processing_time': round(processing_time, 2),
                        'timestamp': datetime.now().isoformat(),
                        'ai_provider': current_ai_client.provider
                    })
                    
                    # Emit processed item
                    socketio.emit('question_processed', {
                        'job_id': job.job_id,
                        'question_id': qa_item['id'],
                        'question': qa_item['question'],
                        'processed_data': processed_item,
                        'processing_time': processing_time
                    })
                else:
                    error_msg = f"Failed to process: {qa_item['question'][:50]}..."
                    job.errors.append(error_msg)
                    
                    # Emit failure details
                    socketio.emit('processing_step', {
                        'job_id': job.job_id,
                        'step': 'ai_failed',
                        'question_id': qa_item['id'],
                        'error': error_msg,
                        'processing_time': round(processing_time, 2),
                        'timestamp': datetime.now().isoformat(),
                        'ai_provider': current_ai_client.provider
                    })
                
                job.progress = ((i + 1) / job.total_questions) * 100
                emit_job_update(job)
                
                # Small delay to prevent overwhelming
                time.sleep(0.5)
                
            except Exception as e:
                error_msg = f"Error processing question {i+1}: {str(e)}"
                job.errors.append(error_msg)
                logger.error(error_msg)
        
        job.status = 'completed'
        emit_job_update(job)
        
        # Save to accumulated file
        if job.processed_data:
            # Use a single master file for all Q&A data
            master_filename = f"qa_master_{job.topic}.json"
            master_filepath = os.path.join('data', master_filename)
            
            # Load existing data if file exists
            existing_data = {}
            if os.path.exists(master_filepath):
                try:
                    with open(master_filepath, 'r') as f:
                        existing_data = json.load(f)
                    logger.info(f"Loaded existing data with {len(existing_data)} entries")
                except Exception as e:
                    logger.error(f"Error loading existing data: {e}")
                    existing_data = {}
            
            # Merge new data with existing data
            merged_data = existing_data.copy()
            merged_data.update(job.processed_data)
            
            # Save the merged data
            with open(master_filepath, 'w') as f:
                json.dump(merged_data, f, indent=2)
            
            logger.info(f"Saved {len(job.processed_data)} new entries to {master_filename}")
            logger.info(f"Total entries in master file: {len(merged_data)}")
            
            # Also create a backup with timestamp
            backup_filename = f"qa_backup_{job.topic}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            backup_filepath = os.path.join('data', 'backups', backup_filename)
            os.makedirs(os.path.join('data', 'backups'), exist_ok=True)
            
            with open(backup_filepath, 'w') as f:
                json.dump(merged_data, f, indent=2)
            
            socketio.emit('job_completed', {
                'job_id': job.job_id,
                'filename': master_filename,
                'new_entries': len(job.processed_data),
                'total_entries': len(merged_data),
                'backup_filename': backup_filename,
                'total_processed': job.processed_questions,
                'total_scraped': job.total_questions
            })
        
    except Exception as e:
        job.status = 'error'
        job.errors.append(f"Processing failed: {str(e)}")
        emit_job_update(job)
        logger.error(f"Bulk processing job failed: {e}")

def run_processing_job(job):
    """Run the processing job for scraped or selected questions"""
    try:
        job.status = 'processing'
        emit_job_update(job)
        
        logger.info(f"Starting to process {job.total_questions} questions")
        
        # Process each question with Ollama
        for i, qa_item in enumerate(job.scraped_data):
            try:
                logger.info(f"Processing question {i+1}/{job.total_questions}: {qa_item['question'][:50]}...")
                
                # Emit detailed progress update
                socketio.emit('scraping_progress', {
                    'job_id': job.job_id,
                    'current_question': qa_item['question'][:100] + '...',
                    'current_answer_length': len(qa_item['answer']),
                    'progress': (i / job.total_questions) * 100,
                    'processed': i,
                    'total': job.total_questions,
                    'step': 'processing_with_ollama',
                    'source': qa_item.get('source', 'unknown')
                })
                
                # Emit detailed step info
                socketio.emit('processing_step', {
                    'job_id': job.job_id,
                    'step': 'ai_start',
                    'question_id': qa_item['id'],
                    'question': qa_item['question'],
                    'answer_preview': qa_item['answer'][:200] + '...' if len(qa_item['answer']) > 200 else qa_item['answer'],
                    'timestamp': datetime.now().isoformat(),
                    'ai_provider': current_ai_client.provider
                })
                
                # Process with AI client with better error handling
                start_time = time.time()
                try:
                    processed_item = current_ai_client.format_qa_to_json(
                        qa_item['question'],
                        qa_item['answer'],
                        qa_item['id']
                    )
                except Exception as ai_error:
                    logger.error(f"AI processing error: {ai_error}")
                    processed_item = None
                
                processing_time = time.time() - start_time
                
                if processed_item:
                    job.processed_data.update(processed_item)
                    job.processed_questions += 1
                    
                    # Emit successful processing
                    socketio.emit('processing_step', {
                        'job_id': job.job_id,
                        'step': 'ai_success',
                        'question_id': qa_item['id'],
                        'processing_time': round(processing_time, 2),
                        'timestamp': datetime.now().isoformat(),
                        'ai_provider': current_ai_client.provider
                    })
                    
                    # Emit processed item
                    socketio.emit('question_processed', {
                        'job_id': job.job_id,
                        'question_id': qa_item['id'],
                        'question': qa_item['question'],
                        'processed_data': processed_item,
                        'processing_time': processing_time
                    })
                else:
                    error_msg = f"Failed to process: {qa_item['question'][:50]}..."
                    job.errors.append(error_msg)
                    
                    # Emit failure details
                    socketio.emit('processing_step', {
                        'job_id': job.job_id,
                        'step': 'ai_failed',
                        'question_id': qa_item['id'],
                        'error': error_msg,
                        'processing_time': round(processing_time, 2),
                        'timestamp': datetime.now().isoformat(),
                        'ai_provider': current_ai_client.provider
                    })
                
                job.progress = ((i + 1) / job.total_questions) * 100
                emit_job_update(job)
                
                # Small delay to prevent overwhelming
                time.sleep(0.5)
                
            except Exception as e:
                error_msg = f"Error processing question {i+1}: {str(e)}"
                job.errors.append(error_msg)
                logger.error(error_msg)
        
        job.status = 'completed'
        emit_job_update(job)
        
        # Save to accumulated file
        if job.processed_data:
            # Use a single master file for all Q&A data
            master_filename = f"qa_master_{job.topic}.json"
            master_filepath = os.path.join('data', master_filename)
            
            # Load existing data if file exists
            existing_data = {}
            if os.path.exists(master_filepath):
                try:
                    with open(master_filepath, 'r') as f:
                        existing_data = json.load(f)
                    logger.info(f"Loaded existing data with {len(existing_data)} entries")
                except Exception as e:
                    logger.error(f"Error loading existing data: {e}")
                    existing_data = {}
            
            # Merge new data with existing data
            merged_data = existing_data.copy()
            merged_data.update(job.processed_data)
            
            # Save the merged data
            with open(master_filepath, 'w') as f:
                json.dump(merged_data, f, indent=2)
            
            logger.info(f"Saved {len(job.processed_data)} new entries to {master_filename}")
            logger.info(f"Total entries in master file: {len(merged_data)}")
            
            # Also create a backup with timestamp
            backup_filename = f"qa_backup_{job.topic}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            backup_filepath = os.path.join('data', 'backups', backup_filename)
            os.makedirs(os.path.join('data', 'backups'), exist_ok=True)
            
            with open(backup_filepath, 'w') as f:
                json.dump(merged_data, f, indent=2)
            
            socketio.emit('job_completed', {
                'job_id': job.job_id,
                'filename': master_filename,
                'new_entries': len(job.processed_data),
                'total_entries': len(merged_data),
                'backup_filename': backup_filename,
                'total_processed': job.processed_questions,
                'total_scraped': job.total_questions
            })
        
    except Exception as e:
        job.status = 'error'
        job.errors.append(f"Processing failed: {str(e)}")
        emit_job_update(job)
        logger.error(f"Processing job failed: {e}")

def emit_job_update(job):
    """Emit job status update via WebSocket"""
    socketio.emit('job_update', {
        'job_id': job.job_id,
        'status': job.status,
        'progress': job.progress,
        'total_questions': job.total_questions,
        'processed_questions': job.processed_questions,
        'errors': job.errors
    })

@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')
    if current_job:
        emit('job_update', {
            'job_id': current_job.job_id,
            'status': current_job.status,
            'progress': current_job.progress,
            'total_questions': current_job.total_questions,
            'processed_questions': current_job.processed_questions,
            'errors': current_job.errors
        })

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

def find_free_port(start_port=8080):
    """Find an available port starting from start_port"""
    import socket
    port = start_port
    while port < 9000:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('', port))
            sock.close()
            return port
        except OSError:
            port += 1
    raise RuntimeError("No free ports available")

if __name__ == '__main__':
    logger.info("Starting Q&A Generator Web App...")
    logger.info("AI providers: OpenAI, Claude")
    logger.info("Set your API keys: OPENAI_API_KEY, ANTHROPIC_API_KEY")
    
    # Try to initialize with available provider
    openai_key = os.getenv('OPENAI_API_KEY')
    claude_key = os.getenv('ANTHROPIC_API_KEY')
    
    if openai_key:
        try:
            current_ai_client = AIClient(provider='openai')
            logger.info("✅ Initialized with OpenAI")
        except Exception as e:
            logger.warning(f"OpenAI initialization failed: {e}")
            current_ai_client = None
    elif claude_key:
        try:
            current_ai_client = AIClient(provider='claude')
            logger.info("✅ Initialized with Claude")
        except Exception as e:
            logger.warning(f"Claude initialization failed: {e}")
            current_ai_client = None
    else:
        logger.warning("⚠️  No API keys found. Please set OPENAI_API_KEY or ANTHROPIC_API_KEY")
        current_ai_client = None
    
    # Find available port
    port = find_free_port()
    logger.info(f"🚀 Starting server on port {port}")
    logger.info(f"🌐 Access the app at: http://localhost:{port}")
    
    socketio.run(app, debug=True, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)