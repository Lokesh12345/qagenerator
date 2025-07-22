// Elite Q&A Generator Dashboard

class EliteDashboard {
    constructor() {
        // Initialize Socket.IO
        if (typeof io === 'undefined') {
            console.error('Socket.IO not loaded');
            this.socket = null;
        } else {
            this.socket = io();
        }
        
        this.currentJobId = null;
        this.currentTopic = null; // Track current job topic
        this.questions = [];
        this.questionProgress = new Map();
        this.processedCount = 0;
        this.errorCount = 0;
        this.fetchedQuestions = [];
        
        this.init();
    }

    init() {
        this.bindEvents();
        if (this.socket) {
            this.bindSocketEvents();
        }
        this.loadAiProviders();
        this.checkAiStatus();
        this.refreshCacheStats();
    }

    bindEvents() {
        // Form submission
        document.getElementById('scrapingForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.previewSelectedQuestions();
        });

        // Range slider
        const slider = document.getElementById('limitPerSource');
        const valueDisplay = document.getElementById('limitValue');
        slider.addEventListener('input', (e) => {
            valueDisplay.textContent = e.target.value;
            this.updatePreviewButton();
        });

        // Fetch questions button
        document.getElementById('fetchQuestionsBtn').addEventListener('click', () => {
            this.fetchQuestionsFromUrl();
        });

        // Website URL input
        document.getElementById('websiteUrl').addEventListener('input', () => {
            this.validateUrl();
        });

        // Config toggle
        document.getElementById('configBtn').addEventListener('click', () => {
            this.toggleConfig();
        });

        // AI provider events
        document.getElementById('aiProvider').addEventListener('change', () => {
            this.updateModelOptions();
        });

        document.getElementById('saveAiProvider').addEventListener('click', () => {
            this.saveAiProvider();
        });

        // Question selection
        document.getElementById('selectAllBtn').addEventListener('click', () => {
            this.selectAllQuestions(true);
        });

        document.getElementById('deselectAllBtn').addEventListener('click', () => {
            this.selectAllQuestions(false);
        });

        // Processing buttons
        document.getElementById('processSelectedBtn').addEventListener('click', () => {
            this.processSelectedQuestions();
        });

        document.getElementById('processBulkBtn').addEventListener('click', () => {
            this.processBulkQuestions();
        });

        // Utility buttons
        document.getElementById('clearLogBtn').addEventListener('click', () => {
            this.clearLog();
        });

        document.getElementById('downloadBtn').addEventListener('click', () => {
            this.downloadResults();
        });

        document.getElementById('refreshCacheStats').addEventListener('click', () => {
            this.refreshCacheStats();
        });
    }

    bindSocketEvents() {
        this.socket.on('connect', () => {
            this.log('Connected to server', 'success');
        });

        this.socket.on('disconnect', () => {
            this.log('Disconnected from server', 'warning');
        });

        this.socket.on('log_message', (data) => {
            this.log(data.message, data.type, data.timestamp);
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
            
            const dot = document.getElementById('aiStatusDot');
            const text = document.getElementById('aiStatusText');
            
            if (data.connected) {
                dot.className = 'status-dot status-connected';
                text.textContent = `${data.provider.toUpperCase()} Connected`;
                this.log(`AI connected: ${data.provider}/${data.model}`, 'success');
            } else {
                dot.className = 'status-dot status-error';
                text.textContent = 'AI Disconnected';
                this.log(`AI connection failed: ${data.error || 'Unknown error'}`, 'error');
            }
        } catch (error) {
            console.error('Error checking AI status:', error);
            this.log('Error checking AI status', 'error');
        }
    }

    async refreshCacheStats() {
        try {
            const response = await fetch('/api/cache-stats');
            const data = await response.json();
            
            if (data.status === 'success') {
                this.updateCacheDisplay(data.cache_stats);
            }
        } catch (error) {
            console.error('Error fetching cache stats:', error);
        }
    }

    updateCacheDisplay(stats) {
        document.getElementById('cacheHitRate').textContent = `${stats.hit_rate_percent}%`;
        document.getElementById('costSaved').textContent = `$${stats.estimated_cost_saved}`;
        document.getElementById('totalRequests').textContent = stats.total_requests;
        document.getElementById('cacheSize').textContent = stats.openai_cache_size + stats.claude_cache_size;
    }

    validateUrl() {
        const urlInput = document.getElementById('websiteUrl');
        const fetchBtn = document.getElementById('fetchQuestionsBtn');
        const status = document.getElementById('urlStatus');
        
        const url = urlInput.value.trim();
        
        if (!url) {
            status.textContent = 'Enter a website URL to scrape questions from';
            status.className = 'mt-2 text-xs text-gray-500';
            fetchBtn.disabled = true;
            return;
        }
        
        try {
            new URL(url);
            status.textContent = 'Valid URL - click Fetch to scrape questions';
            status.className = 'mt-2 text-xs text-green-600';
            fetchBtn.disabled = false;
        } catch (e) {
            status.textContent = 'Please enter a valid URL (e.g., https://example.com)';
            status.className = 'mt-2 text-xs text-red-600';
            fetchBtn.disabled = true;
        }
    }

    async fetchQuestionsFromUrl() {
        const urlInput = document.getElementById('websiteUrl');
        const url = urlInput.value.trim();
        
        if (!url) {
            this.log('Please enter a URL', 'error');
            return;
        }

        this.log(`Fetching questions from: ${url}`, 'info');
        this.setFetchButtonLoading(true);

        try {
            const response = await fetch('/api/scrape-url', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url })
            });

            const data = await response.json();
            
            if (response.ok) {
                this.fetchedQuestions = data.questions || [];
                this.log(`Found ${this.fetchedQuestions.length} questions`, 'success');
                this.updateSliderForFetchedQuestions();
                this.enablePreviewButton();
            } else {
                this.log(`Error: ${data.error}`, 'error');
                this.resetSlider();
            }
        } catch (error) {
            console.error('Error fetching questions:', error);
            this.log('Error fetching questions from URL', 'error');
            this.resetSlider();
        } finally {
            this.setFetchButtonLoading(false);
        }
    }

    setFetchButtonLoading(loading) {
        const btn = document.getElementById('fetchQuestionsBtn');
        if (loading) {
            btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Fetching...';
            btn.disabled = true;
        } else {
            btn.innerHTML = '<i class="fas fa-search mr-1"></i>Fetch';
            btn.disabled = false;
        }
    }

    updateSliderForFetchedQuestions() {
        const slider = document.getElementById('limitPerSource');
        const maxAvailableSpan = document.getElementById('maxAvailable');
        const maxLimitSpan = document.getElementById('maxLimit');
        const limitSection = document.getElementById('limitSection');
        const limitHint = document.getElementById('limitHint');
        
        const questionCount = this.fetchedQuestions.length;
        
        if (questionCount === 0) {
            this.resetSlider();
            return;
        }
        
        // Show the limit section
        limitSection.style.display = 'block';
        
        // Update slider max to match found questions
        slider.max = questionCount;
        slider.min = 1;
        slider.value = Math.min(10, questionCount);
        slider.disabled = false;
        
        // Update displays
        maxAvailableSpan.textContent = questionCount;
        maxLimitSpan.textContent = questionCount;
        document.getElementById('limitValue').textContent = slider.value;
        
        // Update hint
        limitHint.textContent = `${questionCount} questions found - select how many to process`;
        limitHint.className = 'mt-1 text-xs text-green-600';
    }

    resetSlider() {
        const limitSection = document.getElementById('limitSection');
        const slider = document.getElementById('limitPerSource');
        
        limitSection.style.display = 'none';
        slider.disabled = true;
        this.fetchedQuestions = [];
        
        const previewBtn = document.getElementById('previewBtn');
        previewBtn.disabled = true;
    }

    enablePreviewButton() {
        const previewBtn = document.getElementById('previewBtn');
        previewBtn.disabled = false;
    }

    updatePreviewButton() {
        // This can be expanded to update button text based on selection
    }

    toggleConfig() {
        const card = document.getElementById('aiConfigCard');
        card.style.display = card.style.display === 'none' ? 'block' : 'none';
    }

    async previewSelectedQuestions() {
        if (this.fetchedQuestions.length === 0) {
            this.log('Please fetch questions first by entering a URL and clicking Fetch', 'error');
            return;
        }

        const limitPerSource = parseInt(document.getElementById('limitPerSource').value) || 10;
        
        // Select the first N questions based on slider value
        const selectedQuestions = this.fetchedQuestions.slice(0, limitPerSource);
        
        this.log(`Previewing ${selectedQuestions.length} selected questions`, 'info');
        
        // Store the selected questions for processing
        this.questions = selectedQuestions;
        this.displayQuestions(selectedQuestions);
    }

    displayQuestions(questions) {
        const container = document.getElementById('questionList');
        const placeholder = document.getElementById('questionListPlaceholder');
        
        // Hide placeholder
        if (placeholder) {
            placeholder.style.display = 'none';
        }
        
        container.innerHTML = '';

        questions.forEach((q, index) => {
            const item = document.createElement('div');
            item.className = 'flex items-start space-x-2 p-2 hover:bg-gray-50 rounded-md transition-colors border border-transparent hover:border-primary-200';
            item.innerHTML = `
                <input type="checkbox" class="w-3 h-3 text-primary-500 border-gray-300 rounded mt-0.5 question-checkbox" id="q_${index}" checked data-index="${index}">
                <div class="flex-1 min-w-0">
                    <label class="text-xs font-medium text-gray-800 cursor-pointer block leading-relaxed" for="q_${index}">
                        ${q.question}
                    </label>
                    <div class="text-xs text-gray-500 mt-1 flex items-center space-x-3">
                        <span><i class="fas fa-globe w-3 text-primary-400"></i> ${q.source}</span>
                        ${q.url ? `<span><i class="fas fa-link w-3 text-green-400"></i> URL Available</span>` : ''}
                        ${q.answer ? `<span><i class="fas fa-check w-3 text-blue-400"></i> Answer Found</span>` : ''}
                    </div>
                </div>
            `;
            container.appendChild(item);
            
            // Add event listener for selection changes
            const checkbox = item.querySelector('.question-checkbox');
            checkbox.addEventListener('change', () => {
                this.updateSelectionCount();
            });
        });
        
        // Update question count and selection
        this.updateQuestionCount(questions.length);
        this.updateSelectionCount();
    }

    updateQuestionCount(total) {
        document.getElementById('questionCount').textContent = `${total} questions found - select which ones to process`;
    }

    updateSelectionCount() {
        const checkboxes = document.querySelectorAll('.question-checkbox');
        const selected = document.querySelectorAll('.question-checkbox:checked');
        const count = selected.length;
        
        // Update counter
        document.getElementById('selectedCount').textContent = count;
        
        // Enable/disable process button
        const processBtn = document.getElementById('processSelectedBtn');
        processBtn.disabled = count === 0;
        
        if (count === 0) {
            processBtn.className = processBtn.className.replace('from-green-500 to-green-600', 'from-gray-400 to-gray-500');
        } else {
            processBtn.className = processBtn.className.replace('from-gray-400 to-gray-500', 'from-green-500 to-green-600');
        }
    }

    selectAllQuestions(checked) {
        document.querySelectorAll('.question-checkbox').forEach(cb => {
            cb.checked = checked;
        });
        this.updateSelectionCount();
    }

    async processSelectedQuestions() {
        const selected = [];
        document.querySelectorAll('.question-checkbox:checked').forEach((cb) => {
            const questionIndex = parseInt(cb.getAttribute('data-index'));
            if (this.questions[questionIndex]) {
                selected.push(this.questions[questionIndex]);
            }
        });

        if (selected.length === 0) {
            this.log('Please select at least one question', 'error');
            return;
        }

        // Get topic from input field and clean it up
        const topicInput = document.getElementById('topic');
        const rawTopic = topicInput.value.trim() || 'selected';
        this.currentTopic = this.cleanTopicName(rawTopic);
        
        this.log(`Processing ${selected.length} selected questions with topic: ${this.currentTopic}`, 'info');
        this.startProcessing(selected, 'selected');
    }

    async processBulkQuestions() {
        const text = document.getElementById('bulkQuestions').value.trim();
        if (!text) {
            this.log('Please enter questions in the bulk textarea', 'error');
            return;
        }

        const questions = text.split('\n').filter(q => q.trim()).map(q => ({
            question: q.trim(),
            source: 'bulk',
            url: null
        }));

        // Get topic from input field and clean it up
        const topicInput = document.getElementById('topic');
        const rawTopic = topicInput.value.trim() || 'selected';
        this.currentTopic = this.cleanTopicName(rawTopic);
        
        this.log(`Processing ${questions.length} bulk questions with topic: ${this.currentTopic}`, 'info');
        this.startProcessing(questions, 'bulk');
    }

    async startProcessing(questions, mode) {
        this.log(`Starting processing of ${questions.length} questions`, 'info');
        this.initializeProgress(questions);
        
        // Show progress panels
        document.getElementById('progressCard').style.display = 'block';
        document.getElementById('questionProgressCard').style.display = 'block';

        try {
            const response = await fetch('/api/start-scraping', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    mode, 
                    topic: this.currentTopic, // Pass the topic to backend
                    questions,
                    selected_questions: questions  // Backend expects this key name
                })
            });

            const data = await response.json();
            
            if (response.ok) {
                this.currentJobId = data.job_id;
                this.log(`Job started: ${data.job_id}`, 'success');
                this.disableProcessingButtons();
                document.getElementById('aiStatusDot').className = 'status-dot status-processing';
            } else {
                this.log(`Error: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Error starting processing:', error);
            this.log('Error starting processing', 'error');
        }
    }

    initializeProgress(questions) {
        this.questionProgress.clear();
        this.processedCount = 0;
        this.errorCount = 0;
        
        const container = document.getElementById('questionProgressList');
        container.innerHTML = '';

        questions.forEach((q, index) => {
            const item = document.createElement('div');
            item.className = 'flex items-center space-x-2 p-2 rounded-md border border-gray-100 mb-2 fade-in';
            item.id = `progress_${index}`;
            item.innerHTML = `
                <span class="status-dot" style="background: #9ca3af;"></span>
                <div class="flex-1 min-w-0">
                    <div class="text-xs font-medium text-gray-800 truncate">
                        ${q.question.length > 50 ? q.question.substring(0, 50) + '...' : q.question}
                    </div>
                    <div class="text-xs text-gray-500">Pending</div>
                    <div class="mini-progress mt-1">
                        <div class="mini-progress-bar" style="width: 0%"></div>
                    </div>
                </div>
                <span class="text-xs text-gray-400">0%</span>
            `;
            container.appendChild(item);
            
            this.questionProgress.set(q.question, {
                element: item,
                status: 'pending',
                progress: 0
            });
        });
    }

    updateQuestionProgress(question, status, progress = 0) {
        const data = this.questionProgress.get(question);
        if (!data) return;

        const dot = data.element.querySelector('.status-dot');
        const statusText = data.element.querySelector('.text-gray-500');
        const progressBar = data.element.querySelector('.mini-progress-bar');
        const percentage = data.element.querySelector('.text-gray-400');

        switch (status) {
            case 'processing':
                dot.style.background = '#f59e0b';
                statusText.textContent = 'Processing...';
                data.element.className = data.element.className.replace('border-gray-100', 'border-amber-200 bg-amber-50');
                break;
            case 'completed':
                dot.style.background = '#10b981';
                statusText.textContent = 'Completed';
                data.element.className = data.element.className.replace('border-gray-100', 'border-green-200 bg-green-50');
                this.processedCount++;
                break;
            case 'error':
                dot.style.background = '#ef4444';
                statusText.textContent = 'Error';
                data.element.className = data.element.className.replace('border-gray-100', 'border-red-200 bg-red-50');
                this.errorCount++;
                break;
        }

        progressBar.style.width = `${progress}%`;
        percentage.textContent = `${progress}%`;
        
        // Update counters
        document.getElementById('processedCount').textContent = this.processedCount;
        document.getElementById('errorCount').textContent = this.errorCount;
    }

    updateJobStatus(data) {
        const statusBadge = document.getElementById('jobStatus');
        const progressBar = document.getElementById('progressBar');
        const progressText = document.getElementById('progressText');

        statusBadge.textContent = data.status.toUpperCase();
        statusBadge.className = `px-2 py-1 text-xs rounded-full ${this.getStatusClass(data.status)}`;
        
        progressBar.style.width = `${data.progress}%`;
        progressText.textContent = `${data.processed_questions}/${data.total_questions}`;
        
        this.log(`Progress: ${Math.round(data.progress)}%`, 'info');
    }

    getStatusClass(status) {
        switch (status) {
            case 'completed': return 'bg-green-100 text-green-700';
            case 'processing': return 'bg-amber-100 text-amber-700';
            case 'error': return 'bg-red-100 text-red-700';
            default: return 'bg-gray-100 text-gray-700';
        }
    }

    handleProcessingStep(data) {
        if (data.question) {
            this.updateQuestionProgress(data.question, 'processing', 50);
        }
        this.log(`Processing: ${data.step || data.question}`, 'info');
    }

    handleQuestionProcessed(data) {
        if (data.question) {
            this.updateQuestionProgress(data.question, 'completed', 100);
        }
        this.log(`✓ Completed: ${data.question}`, 'success');
    }

    handleJobCompleted(data) {
        this.log(`🎉 Job completed! Processed ${data.total_processed} questions`, 'success');
        this.log(`📁 Saved to: ${data.filename}`, 'info');
        
        // Show results
        document.getElementById('resultsCard').style.display = 'block';
        document.getElementById('totalProcessed').textContent = data.total_processed;
        document.getElementById('newEntries').textContent = data.new_entries;
        document.getElementById('downloadBtn').style.display = 'block';
        
        // Re-enable buttons
        this.enableProcessingButtons();
        document.getElementById('aiStatusDot').className = 'status-dot status-connected';
        
        // Refresh cache stats
        this.refreshCacheStats();
    }

    disableProcessingButtons() {
        document.getElementById('processSelectedBtn').disabled = true;
        document.getElementById('processBulkBtn').disabled = true;
    }

    enableProcessingButtons() {
        document.getElementById('processSelectedBtn').disabled = false;
        document.getElementById('processBulkBtn').disabled = false;
    }

    setButtonLoading(buttonId, loading) {
        const btn = document.getElementById(buttonId);
        if (loading) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Loading...';
        } else {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-play mr-1"></i>Start Scraping';
        }
    }

    async downloadResults() {
        try {
            // Get topic from input field, fallback to current topic, then 'selected'
            const topicInput = document.getElementById('topic');
            const inputTopic = topicInput.value.trim();
            const topic = inputTopic || this.currentTopic || 'selected';
            
            this.log(`Attempting to download results for topic: ${topic}`, 'info');
            
            const response = await fetch(`/api/download-json?topic=${topic}`);
            const data = await response.json();
            
            if (response.ok) {
                const blob = new Blob([JSON.stringify(data.data, null, 2)], {
                    type: 'application/json'
                });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = data.filename;
                a.click();
                URL.revokeObjectURL(url);
                
                this.log(`Downloaded: ${data.filename} (${data.total_entries} entries)`, 'success');
            } else {
                // If the specified topic doesn't work, try fallback topics
                if (inputTopic && topic !== 'selected') {
                    this.log(`Topic '${topic}' not found, trying 'selected'...`, 'warning');
                    // Temporarily clear input to try fallback
                    const originalValue = topicInput.value;
                    topicInput.value = 'selected';
                    const result = await this.downloadResults();
                    topicInput.value = originalValue; // Restore original value
                    return result;
                } else if (topic !== 'angular') {
                    this.log(`Topic 'selected' not found, trying 'angular'...`, 'warning');
                    const originalValue = topicInput.value;
                    topicInput.value = 'angular';
                    const result = await this.downloadResults();
                    topicInput.value = originalValue; // Restore original value
                    return result;
                } else {
                    this.log(`Download error: ${data.error}`, 'error');
                    this.log('Try processing some questions first to generate data', 'info');
                }
            }
        } catch (error) {
            console.error('Download error:', error);
            this.log('Download failed', 'error');
        }
    }

    cleanTopicName(topic) {
        // Clean topic name to be filesystem-safe
        return topic
            .toLowerCase()
            .replace(/[^a-z0-9_-]/g, '_')  // Replace non-alphanumeric with underscore
            .replace(/_+/g, '_')           // Replace multiple underscores with single
            .replace(/^_|_$/g, '')         // Remove leading/trailing underscores
            .slice(0, 30)                  // Limit length
            || 'selected';                 // Fallback if empty after cleaning
    }

    log(message, type = 'info', timestamp = null) {
        const feed = document.getElementById('liveFeed');
        const entry = document.createElement('div');
        entry.className = `log-entry log-${type}`;
        
        const time = timestamp ? new Date(timestamp) : new Date();
        const timeStr = time.toLocaleTimeString('en-US', { 
            hour12: false, 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit' 
        });
        
        entry.innerHTML = `
            <span class="opacity-60">${timeStr}</span> ${message}
        `;
        
        // Remove placeholder
        const placeholder = feed.querySelector('.text-center');
        if (placeholder) placeholder.remove();
        
        feed.appendChild(entry);
        feed.scrollTop = feed.scrollHeight;
    }

    clearLog() {
        const feed = document.getElementById('liveFeed');
        feed.innerHTML = `
            <div class="text-center text-gray-400 py-8">
                <i class="fas fa-play-circle text-2xl mb-2 opacity-50"></i>
                <p class="text-xs">Ready to start processing...</p>
            </div>
        `;
    }

    loadAiProviders() {
        // Load available providers and models
        const providers = {
            openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'],
            claude: ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022']
        };
        
        this.aiProviders = providers;
        this.updateModelOptions();
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
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider, model })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.log(`AI provider set: ${provider}/${model}`, 'success');
                this.checkAiStatus();
                document.getElementById('aiConfigCard').style.display = 'none';
            } else {
                this.log(`Error: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Error saving AI provider:', error);
            this.log('Error saving AI provider', 'error');
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new EliteDashboard();
});