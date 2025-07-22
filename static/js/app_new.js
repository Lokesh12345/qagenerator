// Modern Q&A Generator Frontend JavaScript

class ModernQAGenerator {
    constructor() {
        // Check if Socket.IO is available
        if (typeof io === 'undefined') {
            console.error('Socket.IO not loaded. Please check your internet connection.');
            this.socket = null;
            this.socketError = true;
        } else {
            this.socket = io();
            this.socketError = false;
        }
        
        this.currentJobId = null;
        this.processedData = {};
        this.aiProviders = {};
        this.questions = [];
        this.questionProgress = new Map(); // Track individual question progress
        
        this.initializeEventListeners();
        if (this.socket) {
            this.initializeSocketListeners();
        }
        this.loadAiProviders();
        this.checkAiStatus();
        
        // Show socket error after DOM is ready
        if (this.socketError) {
            setTimeout(() => {
                this.addLogEntry('Socket.IO library failed to load. Real-time features disabled.', 'error');
            }, 100);
        }
    }

    initializeEventListeners() {
        // Form submission
        document.getElementById('scrapingForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.previewQuestions();
        });

        // Range slider
        const limitSlider = document.getElementById('limitPerSource');
        const limitValue = document.getElementById('limitValue');
        limitSlider.addEventListener('input', (e) => {
            limitValue.textContent = e.target.value;
        });

        // AI configuration toggle
        document.getElementById('aiConfigBtn').addEventListener('click', () => {
            this.toggleAiConfig();
        });

        // AI provider changes
        document.getElementById('aiProvider').addEventListener('change', () => {
            this.updateModelOptions();
        });

        document.getElementById('saveAiProvider').addEventListener('click', () => {
            this.saveAiProvider();
        });

        // Question selection buttons
        document.getElementById('selectAllBtn').addEventListener('click', () => {
            this.selectAllQuestions(true);
        });

        document.getElementById('deselectAllBtn').addEventListener('click', () => {
            this.selectAllQuestions(false);
        });

        // Process selected questions
        document.getElementById('processSelectedBtn').addEventListener('click', () => {
            this.processSelectedQuestions();
        });

        // Bulk processing
        document.getElementById('processBulkBtn').addEventListener('click', () => {
            this.processBulkQuestions();
        });

        // Utility buttons
        document.getElementById('clearLogBtn').addEventListener('click', () => {
            this.clearLog();
        });

        document.getElementById('downloadBtn').addEventListener('click', () => {
            this.downloadJSON();
        });

        // Cache stats refresh
        document.getElementById('refreshCacheStats').addEventListener('click', () => {
            this.refreshCacheStats();
        });
    }

    initializeSocketListeners() {
        if (!this.socket) {
            this.addLogEntry('WebSocket not available - real-time updates disabled', 'warning');
            return;
        }

        this.socket.on('connect', () => {
            this.addLogEntry('Connected to server', 'success');
        });

        this.socket.on('disconnect', () => {
            this.addLogEntry('Disconnected from server', 'warning');
        });

        this.socket.on('log_message', (data) => {
            this.addLogEntry(data.message, data.type, data.timestamp);
        });

        this.socket.on('job_status', (data) => {
            this.updateJobStatus(data);
        });

        this.socket.on('question_processed', (data) => {
            this.handleQuestionProcessed(data);
        });

        this.socket.on('job_completed', (data) => {
            this.handleJobCompleted(data);
        });

        this.socket.on('processing_step', (data) => {
            this.handleProcessingStep(data);
        });
    }

    async checkAiStatus() {
        try {
            const response = await fetch('/api/test-ai');
            const data = await response.json();
            
            const indicator = document.getElementById('aiStatusIndicator');
            const text = document.getElementById('aiStatusText');
            
            if (data.connected) {
                indicator.className = 'status-indicator status-connected';
                text.textContent = `${data.provider.toUpperCase()} Connected`;
                this.addLogEntry(`AI connected: ${data.provider}/${data.model}`, 'success');
                this.refreshCacheStats();
            } else {
                indicator.className = 'status-indicator status-disconnected';
                text.textContent = 'AI Disconnected';
                this.addLogEntry(`AI connection failed: ${data.error || 'Unknown error'}`, 'error');
            }
        } catch (error) {
            console.error('Error checking AI status:', error);
            this.addLogEntry('Error checking AI status', 'error');
        }
    }

    async refreshCacheStats() {
        try {
            const response = await fetch('/api/cache-stats');
            const data = await response.json();
            
            if (data.status === 'success') {
                this.updateCacheStatsDisplay(data.cache_stats);
                document.getElementById('cacheStatsCard').style.display = 'block';
            } else {
                document.getElementById('cacheStatsCard').style.display = 'none';
            }
        } catch (error) {
            console.error('Error fetching cache stats:', error);
            document.getElementById('cacheStatsCard').style.display = 'none';
        }
    }

    updateCacheStatsDisplay(stats) {
        document.getElementById('cacheHitRate').textContent = `${stats.hit_rate_percent}%`;
        document.getElementById('costSaved').textContent = `$${stats.estimated_cost_saved}`;
        document.getElementById('totalRequests').textContent = stats.total_requests;
        document.getElementById('cacheSize').textContent = stats.openai_cache_size + stats.claude_cache_size;
        
        if (stats.cache_hits > 0) {
            this.addLogEntry(`Cache: ${stats.cache_hits} hits, $${stats.estimated_cost_saved} saved`, 'success');
        }
    }

    toggleAiConfig() {
        const card = document.getElementById('aiConfigCard');
        card.style.display = card.style.display === 'none' ? 'block' : 'none';
    }

    async previewQuestions() {
        const formData = new FormData(document.getElementById('scrapingForm'));
        
        // Get selected sources
        const sources = [];
        document.querySelectorAll('input[name="sources"]:checked').forEach(checkbox => {
            sources.push(checkbox.value);
        });

        if (sources.length === 0) {
            this.addLogEntry('Please select at least one source', 'error');
            return;
        }

        const requestData = {
            topic: formData.get('topic'),
            sources: sources,
            limit_per_source: parseInt(formData.get('limitPerSource'))
        };

        this.addLogEntry(`Previewing questions for topic: ${requestData.topic}`, 'info');
        document.getElementById('startBtn').disabled = true;
        document.getElementById('startBtn').innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';

        try {
            const response = await fetch('/api/preview-questions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            });

            const data = await response.json();
            
            if (response.ok) {
                this.questions = data.questions;
                this.displayQuestionPreview(data.questions);
                this.addLogEntry(`Found ${data.questions.length} questions`, 'success');
                document.getElementById('questionPreviewCard').style.display = 'block';
            } else {
                this.addLogEntry(`Error: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Error previewing questions:', error);
            this.addLogEntry('Error loading questions', 'error');
        } finally {
            document.getElementById('startBtn').disabled = false;
            document.getElementById('startBtn').innerHTML = '<i class="fas fa-play"></i> Start Scraping';
        }
    }

    displayQuestionPreview(questions) {
        const container = document.getElementById('questionList');
        container.innerHTML = '';

        questions.forEach((q, index) => {
            const questionItem = document.createElement('div');
            questionItem.className = 'question-item';
            questionItem.innerHTML = `
                <div class="d-flex align-items-start">
                    <input type="checkbox" class="form-check-input me-3 mt-1" id="q_${index}" checked>
                    <div class="flex-grow-1">
                        <label class="form-check-label fw-medium" for="q_${index}">
                            ${q.question}
                        </label>
                        <div class="small text-muted mt-1">
                            <i class="fas fa-globe"></i> ${q.source} • ${q.url ? 'URL found' : 'No URL'}
                        </div>
                        <div class="progress-mini" style="display: none;">
                            <div class="progress-mini-bar" style="width: 0%"></div>
                        </div>
                    </div>
                </div>
            `;
            container.appendChild(questionItem);
        });
    }

    selectAllQuestions(checked) {
        document.querySelectorAll('#questionList input[type="checkbox"]').forEach(checkbox => {
            checkbox.checked = checked;
        });
    }

    async processSelectedQuestions() {
        const selectedQuestions = [];
        document.querySelectorAll('#questionList input[type="checkbox"]:checked').forEach((checkbox, index) => {
            const questionIndex = parseInt(checkbox.id.split('_')[1]);
            selectedQuestions.push(this.questions[questionIndex]);
        });

        if (selectedQuestions.length === 0) {
            this.addLogEntry('Please select at least one question', 'error');
            return;
        }

        this.startProcessing(selectedQuestions, 'selected');
    }

    async processBulkQuestions() {
        const bulkText = document.getElementById('bulkQuestions').value.trim();
        if (!bulkText) {
            this.addLogEntry('Please enter questions in the bulk textarea', 'error');
            return;
        }

        const questions = bulkText.split('\n').filter(q => q.trim()).map(q => ({
            question: q.trim(),
            source: 'bulk',
            url: null
        }));

        this.startProcessing(questions, 'bulk');
    }

    async startProcessing(questions, mode) {
        const requestData = {
            mode: mode,
            questions: questions
        };

        this.addLogEntry(`Starting processing of ${questions.length} questions`, 'info');
        this.initializeProgressTracking(questions);
        
        // Show progress panels
        document.getElementById('progressCard').style.display = 'block';
        document.getElementById('questionProgressCard').style.display = 'block';

        try {
            const response = await fetch('/api/start-scraping', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            });

            const data = await response.json();
            
            if (response.ok) {
                this.currentJobId = data.job_id;
                this.addLogEntry(`Job started: ${data.job_id}`, 'success');
                this.updateUIForJobStart();
            } else {
                this.addLogEntry(`Error: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Error starting processing:', error);
            this.addLogEntry('Error starting processing job', 'error');
        }
    }

    initializeProgressTracking(questions) {
        this.questionProgress.clear();
        const container = document.getElementById('questionProgressList');
        container.innerHTML = '';

        questions.forEach((q, index) => {
            const progressId = `progress_${index}`;
            this.questionProgress.set(q.question, {
                status: 'pending',
                progress: 0,
                element: progressId
            });

            const progressItem = document.createElement('div');
            progressItem.className = 'question-item';
            progressItem.id = progressId;
            progressItem.innerHTML = `
                <div class="d-flex align-items-center">
                    <div class="status-indicator" style="background: #6b7280;"></div>
                    <div class="flex-grow-1 ms-2">
                        <div class="fw-medium">${q.question.substring(0, 60)}${q.question.length > 60 ? '...' : ''}</div>
                        <div class="small text-muted">Pending</div>
                    </div>
                    <div class="text-end">
                        <span class="badge bg-secondary">0%</span>
                    </div>
                </div>
                <div class="progress-mini">
                    <div class="progress-mini-bar" style="width: 0%"></div>
                </div>
            `;
            container.appendChild(progressItem);
        });
    }

    updateQuestionProgress(question, status, progress = 0) {
        const questionData = this.questionProgress.get(question);
        if (!questionData) return;

        const element = document.getElementById(questionData.element);
        if (!element) return;

        const indicator = element.querySelector('.status-indicator');
        const statusText = element.querySelector('.small.text-muted');
        const badge = element.querySelector('.badge');
        const progressBar = element.querySelector('.progress-mini-bar');

        // Update status indicator
        switch (status) {
            case 'processing':
                indicator.style.background = '#f59e0b';
                element.className = 'question-item processing';
                statusText.textContent = 'Processing...';
                break;
            case 'completed':
                indicator.style.background = '#10b981';
                element.className = 'question-item completed';
                statusText.textContent = 'Completed';
                break;
            case 'error':
                indicator.style.background = '#ef4444';
                element.className = 'question-item error';
                statusText.textContent = 'Error';
                break;
        }

        // Update progress
        badge.textContent = `${progress}%`;
        progressBar.style.width = `${progress}%`;
        
        // Update badge color
        if (progress === 100) {
            badge.className = 'badge bg-success';
        } else if (progress > 0) {
            badge.className = 'badge bg-warning';
        }

        questionData.status = status;
        questionData.progress = progress;
    }

    updateJobStatus(data) {
        document.getElementById('progressCard').style.display = 'block';
        
        const statusElement = document.getElementById('jobStatus');
        statusElement.textContent = data.status.toUpperCase();
        statusElement.className = `badge ${this.getStatusBadgeClass(data.status)}`;
        
        // Update progress
        const progressBar = document.getElementById('progressBar');
        progressBar.style.width = `${data.progress}%`;
        
        document.getElementById('progressText').textContent = `${data.processed_questions}/${data.total_questions} questions`;
        document.getElementById('processedCount').textContent = data.processed_questions;
        document.getElementById('totalCount').textContent = data.total_questions;
        
        this.addLogEntry(`Job status: ${data.status} (${Math.round(data.progress)}%)`, 'info');
    }

    getStatusBadgeClass(status) {
        switch (status) {
            case 'completed': return 'bg-success';
            case 'processing': return 'bg-warning';
            case 'error': return 'bg-danger';
            default: return 'bg-secondary';
        }
    }

    handleProcessingStep(data) {
        if (data.question) {
            this.updateQuestionProgress(data.question, 'processing', 50);
        }
        this.addLogEntry(`Processing: ${data.step || data.question}`, 'info');
    }

    handleQuestionProcessed(data) {
        if (data.question) {
            this.updateQuestionProgress(data.question, 'completed', 100);
        }
        this.addLogEntry(`✓ Processed: ${data.question}`, 'success');
        this.updateDataPreview(data);
    }

    handleJobCompleted(data) {
        this.addLogEntry(`🎉 Job completed! Processed ${data.total_processed}/${data.total_scraped} questions`, 'success');
        this.addLogEntry(`📊 Added ${data.new_entries} new entries to: ${data.filename}`, 'info');
        
        // Show results
        document.getElementById('resultsCard').style.display = 'block';
        document.getElementById('successCount').textContent = data.total_processed;
        document.getElementById('downloadBtn').style.display = 'block';
        
        // Re-enable buttons
        document.getElementById('processSelectedBtn').disabled = false;
        document.getElementById('processBulkBtn').disabled = false;
        
        // Refresh cache stats
        this.refreshCacheStats();
    }

    updateUIForJobStart() {
        document.getElementById('processSelectedBtn').disabled = true;
        document.getElementById('processBulkBtn').disabled = true;
        document.getElementById('aiStatusIndicator').className = 'status-indicator status-processing';
    }

    updateDataPreview(data) {
        // Store processed data
        this.processedData[data.id] = data.data;
    }

    async downloadJSON() {
        try {
            const topic = document.getElementById('topic').value;
            const response = await fetch(`/api/download-json?topic=${topic}`);
            const data = await response.json();
            
            if (response.ok) {
                // Create download link
                const blob = new Blob([JSON.stringify(data.data, null, 2)], {
                    type: 'application/json'
                });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = data.filename;
                a.click();
                URL.revokeObjectURL(url);
                
                this.addLogEntry(`Downloaded: ${data.filename}`, 'success');
            } else {
                this.addLogEntry(`Download error: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Download error:', error);
            this.addLogEntry('Download failed', 'error');
        }
    }

    addLogEntry(message, type = 'info', timestamp = null) {
        const liveFeed = document.getElementById('liveFeed');
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        
        const time = timestamp ? new Date(timestamp) : new Date();
        const timeStr = time.toLocaleTimeString();
        
        entry.innerHTML = `
            <small class="text-muted">${timeStr}</small>
            <div>${message}</div>
        `;
        
        // Remove placeholder if present
        const placeholder = liveFeed.querySelector('.text-center');
        if (placeholder) {
            placeholder.remove();
        }
        
        liveFeed.appendChild(entry);
        liveFeed.scrollTop = liveFeed.scrollHeight;
    }

    clearLog() {
        const liveFeed = document.getElementById('liveFeed');
        liveFeed.innerHTML = `
            <div class="text-center text-muted py-4">
                <i class="fas fa-play-circle fa-3x mb-3 opacity-50"></i>
                <p>Ready to start processing...</p>
            </div>
        `;
    }

    async loadAiProviders() {
        try {
            const response = await fetch('/api/ai-providers');
            const data = await response.json();
            
            this.aiProviders = {};
            
            // Store provider models
            Object.entries(data.providers).forEach(([key, provider]) => {
                this.aiProviders[key] = provider.models;
            });
            
            // Set current provider if available
            if (data.current.provider && data.current.model) {
                document.getElementById('aiProvider').value = data.current.provider;
                this.updateModelOptions();
                document.getElementById('aiModel').value = data.current.model;
            } else {
                this.updateModelOptions();
            }
            
        } catch (error) {
            console.error('Failed to load AI providers:', error);
            // Fallback to hardcoded providers
            this.aiProviders = {
                openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'],
                claude: ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022'],
                ollama: ['phi3:mini', 'qwen:7b']
            };
            this.updateModelOptions();
        }
    }

    updateModelOptions() {
        const provider = document.getElementById('aiProvider').value;
        const modelSelect = document.getElementById('aiModel');
        modelSelect.innerHTML = '';
        
        if (this.aiProviders[provider]) {
            this.aiProviders[provider].forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                modelSelect.appendChild(option);
            });
        }
    }

    async saveAiProvider() {
        const provider = document.getElementById('aiProvider').value;
        const model = document.getElementById('aiModel').value;
        
        try {
            const response = await fetch('/api/set-ai-provider', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ provider, model })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.addLogEntry(`AI provider set: ${provider}/${model}`, 'success');
                this.checkAiStatus();
                document.getElementById('aiConfigCard').style.display = 'none';
            } else {
                this.addLogEntry(`Error setting AI provider: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Error saving AI provider:', error);
            this.addLogEntry('Error saving AI provider', 'error');
        }
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.qaGenerator = new ModernQAGenerator();
});