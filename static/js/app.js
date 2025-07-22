// Q&A Generator Frontend JavaScript

class QAGenerator {
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
            this.startScraping();
        });

        // Range slider
        const limitSlider = document.getElementById('limitPerSource');
        const limitValue = document.getElementById('limitValue');
        limitSlider.addEventListener('input', (e) => {
            limitValue.textContent = e.target.value;
        });

        // Clear log button
        document.getElementById('clearLogBtn').addEventListener('click', () => {
            this.clearLog();
        });

        // Download button
        document.getElementById('downloadBtn').addEventListener('click', () => {
            this.downloadJSON();
        });

        // Preview button
        document.getElementById('previewBtn').addEventListener('click', () => {
            this.previewQuestions();
        });

        // Preview modal buttons
        document.getElementById('selectAllBtn').addEventListener('click', () => {
            this.selectAllQuestions(true);
        });

        document.getElementById('deselectAllBtn').addEventListener('click', () => {
            this.selectAllQuestions(false);
        });

        document.getElementById('selectAllCheckbox').addEventListener('change', (e) => {
            this.selectAllQuestions(e.target.checked);
        });

        document.getElementById('processSelectedBtn').addEventListener('click', () => {
            this.processSelectedQuestions();
        });

        // AI Provider modal events
        document.getElementById('aiProvider').addEventListener('change', () => {
            this.updateModelOptions();
        });

        document.getElementById('saveAiProvider').addEventListener('click', () => {
            this.saveAiProvider();
        });

        // Bulk processing button
        document.getElementById('processBulkBtn').addEventListener('click', () => {
            this.processBulkQuestions();
        });

        // Cache stats refresh button
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
            this.updateConnectionStatus(true);
        });

        this.socket.on('disconnect', () => {
            this.addLogEntry('Disconnected from server', 'error');
            this.updateConnectionStatus(false);
        });

        this.socket.on('job_update', (data) => {
            this.updateJobStatus(data);
        });

        this.socket.on('scraping_progress', (data) => {
            this.updateScrapingProgress(data);
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
            
            const statusElement = document.getElementById('aiStatus');
            if (data.connected) {
                statusElement.innerHTML = `<i class="fas fa-circle"></i> ${data.provider.toUpperCase()} Connected`;
                statusElement.className = 'badge bg-success me-2';
                this.addLogEntry(`AI connected: ${data.provider}/${data.model}`, 'success');
                
                // Load cache stats when AI is connected
                this.refreshCacheStats();
            } else {
                statusElement.innerHTML = '<i class="fas fa-exclamation-circle"></i> AI Disconnected';
                statusElement.className = 'badge bg-danger me-2';
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
                console.error('Cache stats error:', data.error);
                document.getElementById('cacheStatsCard').style.display = 'none';
            }
        } catch (error) {
            console.error('Error fetching cache stats:', error);
            document.getElementById('cacheStatsCard').style.display = 'none';
        }
    }

    updateCacheStatsDisplay(stats) {
        // Update hit rate with color coding
        const hitRate = stats.hit_rate_percent;
        const hitRateElement = document.getElementById('cacheHitRate');
        hitRateElement.textContent = `${hitRate}%`;
        
        if (hitRate >= 70) {
            hitRateElement.className = 'badge bg-success';
        } else if (hitRate >= 40) {
            hitRateElement.className = 'badge bg-warning text-dark';
        } else {
            hitRateElement.className = 'badge bg-danger';
        }
        
        // Update other stats
        document.getElementById('totalRequests').textContent = stats.total_requests;
        document.getElementById('costSaved').textContent = `$${stats.estimated_cost_saved}`;
        
        // Update cache size (sum of both providers)
        const totalCacheSize = stats.openai_cache_size + stats.claude_cache_size;
        document.getElementById('cacheSize').textContent = `${totalCacheSize} entries`;
        
        // Add log entry if there are cache hits
        if (stats.cache_hits > 0) {
            this.addLogEntry(`Cache: ${stats.cache_hits} hits, $${stats.estimated_cost_saved} saved`, 'success');
        }
    }

    async startScraping() {
        const formData = new FormData(document.getElementById('scrapingForm'));
        
        // Get selected sources
        const sources = [];
        document.querySelectorAll('input[name="sources"]:checked').forEach(checkbox => {
            sources.push(checkbox.value);
        });

        if (sources.length === 0) {
            alert('Please select at least one source');
            return;
        }

        const requestData = {
            topic: formData.get('topic'),
            sources: sources,
            limit_per_source: parseInt(formData.get('limitPerSource'))
        };

        this.addLogEntry(`Starting scraping job for topic: ${requestData.topic}`, 'info');
        this.addLogEntry(`Sources: ${sources.join(', ')}`, 'info');
        this.addLogEntry(`Questions per source: ${requestData.limit_per_source}`, 'info');

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
            console.error('Error starting scraping:', error);
            this.addLogEntry('Error starting scraping job', 'error');
        }
    }

    updateJobStatus(data) {
        document.getElementById('statusCard').style.display = 'block';
        
        const statusElement = document.getElementById('jobStatus');
        statusElement.textContent = data.status.toUpperCase();
        statusElement.className = `badge status-${data.status}`;
        
        // Update progress
        const progressBar = document.getElementById('progressBar');
        const progressText = document.getElementById('progressText');
        
        progressBar.style.width = `${data.progress}%`;
        progressText.textContent = `${data.processed_questions}/${data.total_questions} questions`;
        
        // Update errors
        if (data.errors && data.errors.length > 0) {
            document.getElementById('errorContainer').style.display = 'block';
            document.getElementById('errorList').innerHTML = data.errors.map(error => 
                `<div>• ${error}</div>`
            ).join('');
        }
        
        this.addLogEntry(`Job status: ${data.status} (${Math.round(data.progress)}%)`, 'info');
    }

    updateScrapingProgress(data) {
        document.getElementById('currentQuestion').textContent = data.current_question;
        this.addLogEntry(`Processing: ${data.current_question}`, 'processing');
    }

    handleQuestionProcessed(data) {
        this.processedData[data.question_id] = data.processed_data;
        
        this.addLogEntry(`✓ Processed: ${data.question}`, 'success');
        this.updateDataPreview(data);
    }

    handleJobCompleted(data) {
        this.addLogEntry(`🎉 Job completed! Processed ${data.total_processed}/${data.total_scraped} questions`, 'success');
        this.addLogEntry(`📊 Added ${data.new_entries} new entries to: ${data.filename}`, 'info');
        this.addLogEntry(`📈 Total entries in master file: ${data.total_entries}`, 'success');
        this.addLogEntry(`💾 Backup saved to: ${data.backup_filename}`, 'info');
        
        document.getElementById('downloadBtn').style.display = 'block';
        document.getElementById('startBtn').disabled = false;
        
        // Re-enable bulk processing button
        document.getElementById('processBulkBtn').disabled = false;
        
        // Refresh cache stats to show any cost savings
        this.refreshCacheStats();
        document.getElementById('processBulkBtn').innerHTML = '<i class="fas fa-robot"></i> Process with AI';
    }

    updateDataPreview(data) {
        document.getElementById('dataPreviewCard').style.display = 'block';
        
        const tableBody = document.getElementById('dataPreviewTable');
        const processedItem = Object.values(data.processed_data)[0]; // Get the first (and only) item
        
        if (processedItem) {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><code>${data.question_id}</code></td>
                <td class="question-preview" title="${processedItem.primaryQuestion}">
                    ${processedItem.primaryQuestion}
                </td>
                <td><span class="badge bg-info">${processedItem.category || 'N/A'}</span></td>
                <td><span class="badge bg-secondary">${processedItem.difficulty || 'N/A'}</span></td>
                <td>
                    <button class="btn btn-sm btn-outline-primary" onclick="qaGenerator.showQuestionDetails('${data.question_id}')">
                        <i class="fas fa-eye"></i> View
                    </button>
                </td>
            `;
            
            tableBody.appendChild(row);
        }
    }

    showQuestionDetails(questionId) {
        const data = this.processedData[questionId];
        if (!data) return;
        
        const processedItem = Object.values(data)[0];
        
        const modalContent = `
            <div class="mb-3">
                <h6>Primary Question</h6>
                <p>${processedItem.primaryQuestion}</p>
            </div>
            
            <div class="mb-3">
                <h6>Category & Difficulty</h6>
                <span class="badge bg-info me-2">${processedItem.category}</span>
                <span class="badge bg-secondary">${processedItem.difficulty}</span>
            </div>
            
            <div class="mb-3">
                <h6>Summary</h6>
                <p>${processedItem.answer?.summary || 'N/A'}</p>
            </div>
            
            <div class="mb-3">
                <h6>Tags</h6>
                ${processedItem.tags ? processedItem.tags.map(tag => 
                    `<span class="badge bg-light text-dark me-1">${tag}</span>`
                ).join('') : 'N/A'}
            </div>
            
            <div class="mb-3">
                <h6>Alternative Questions</h6>
                <ul class="list-unstyled">
                    ${processedItem.alternativeQuestions ? processedItem.alternativeQuestions.slice(0, 5).map(q => 
                        `<li>• ${q}</li>`
                    ).join('') : '<li>N/A</li>'}
                </ul>
            </div>
            
            <div class="mb-3">
                <h6>Raw JSON</h6>
                <pre><code>${JSON.stringify(processedItem, null, 2)}</code></pre>
            </div>
        `;
        
        document.getElementById('questionDetails').innerHTML = modalContent;
        new bootstrap.Modal(document.getElementById('questionModal')).show();
    }

    updateUIForJobStart() {
        document.getElementById('startBtn').disabled = true;
        document.getElementById('startBtn').innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
        document.getElementById('downloadBtn').style.display = 'none';
        
        // Clear previous data
        document.getElementById('dataPreviewTable').innerHTML = '';
        this.processedData = {};
    }

    addLogEntry(message, type = 'info') {
        const liveFeed = document.getElementById('liveFeed');
        
        // Clear initial message if it exists
        if (liveFeed.children.length === 1 && liveFeed.children[0].classList.contains('text-muted')) {
            liveFeed.innerHTML = '';
        }
        
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry ${type} new`;
        
        let icon = '';
        switch (type) {
            case 'success': icon = '✓'; break;
            case 'error': icon = '✗'; break;
            case 'warning': icon = '⚠'; break;
            case 'processing': icon = '⟳'; break;
            default: icon = 'ℹ'; break;
        }
        
        logEntry.innerHTML = `
            <span class="timestamp">[${timestamp}]</span> 
            <span class="icon">${icon}</span> 
            ${message}
        `;
        
        liveFeed.appendChild(logEntry);
        liveFeed.scrollTop = liveFeed.scrollHeight;
        
        // Remove 'new' class after animation
        setTimeout(() => {
            logEntry.classList.remove('new');
        }, 300);
    }

    clearLog() {
        const liveFeed = document.getElementById('liveFeed');
        liveFeed.innerHTML = `
            <div class="text-muted text-center p-4">
                <i class="fas fa-play-circle fa-3x mb-3"></i>
                <p>Log cleared. Click "Start Scraping" to begin processing</p>
            </div>
        `;
    }

    async downloadJSON() {
        try {
            // Get the current topic
            const topic = document.getElementById('topic').value;
            const response = await fetch(`/api/download-json?topic=${topic}`);
            const data = await response.json();
            
            if (response.ok) {
                this.addLogEntry(`Master file loaded: ${data.filename}`, 'success');
                this.addLogEntry(`Total entries: ${data.total_entries}`, 'info');
                
                // Offer browser download of master file
                const jsonBlob = new Blob([JSON.stringify(data.data, null, 2)], {
                    type: 'application/json'
                });
                const url = URL.createObjectURL(jsonBlob);
                const a = document.createElement('a');
                a.href = url;
                a.download = data.filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                
                // Also show stats
                this.showMasterStats();
            } else {
                this.addLogEntry(`Download error: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Error downloading JSON:', error);
            this.addLogEntry('Error downloading JSON file', 'error');
        }
    }
    
    async showMasterStats() {
        try {
            const response = await fetch('/api/master-stats');
            const data = await response.json();
            
            if (response.ok && data.stats) {
                this.addLogEntry('📊 Master Files Statistics:', 'info');
                for (const [topic, stats] of Object.entries(data.stats)) {
                    this.addLogEntry(`  • ${topic}: ${stats.total_entries} entries (${(stats.file_size / 1024).toFixed(2)} KB)`, 'info');
                }
            }
        } catch (error) {
            console.error('Error fetching stats:', error);
        }
    }

    updateConnectionStatus(connected) {
        let statusDiv = document.getElementById('connectionStatus');
        if (!statusDiv) {
            statusDiv = document.createElement('div');
            statusDiv.id = 'connectionStatus';
            statusDiv.className = 'connection-status';
            document.body.appendChild(statusDiv);
        }
        
        if (connected) {
            statusDiv.textContent = '🟢 Connected';
            statusDiv.className = 'connection-status connected';
        } else {
            statusDiv.textContent = '🔴 Disconnected';
            statusDiv.className = 'connection-status disconnected';
        }
    }

    async previewQuestions() {
        const formData = new FormData(document.getElementById('scrapingForm'));
        
        // Get selected sources
        const sources = [];
        document.querySelectorAll('input[name="sources"]:checked').forEach(checkbox => {
            sources.push(checkbox.value);
        });

        // Get custom URLs
        const customUrlsText = document.getElementById('customUrls').value;
        const customUrls = customUrlsText.split('\n').map(url => url.trim()).filter(url => url);

        if (sources.length === 0 && customUrls.length === 0) {
            alert('Please select at least one source or add a custom URL');
            return;
        }

        const requestData = {
            topic: formData.get('topic'),
            sources: sources,
            custom_urls: customUrls,
            limit_per_source: parseInt(formData.get('limitPerSource'))
        };

        // Show loading
        document.getElementById('previewLoading').style.display = 'block';
        document.getElementById('previewContent').style.display = 'none';
        new bootstrap.Modal(document.getElementById('previewModal')).show();

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
                this.displayPreviewQuestions(data);
            } else {
                this.addLogEntry(`Preview error: ${data.error}`, 'error');
                alert(`Error: ${data.error}`);
            }
        } catch (error) {
            console.error('Error previewing questions:', error);
            this.addLogEntry('Error loading preview', 'error');
            alert('Error loading question preview');
        } finally {
            document.getElementById('previewLoading').style.display = 'none';
            document.getElementById('previewContent').style.display = 'block';
        }
    }

    displayPreviewQuestions(data) {
        const { questions, total_found, unique_count, duplicates_removed } = data;
        
        // Update stats
        document.getElementById('previewStats').textContent = 
            `${unique_count} unique (${duplicates_removed} duplicates removed)`;
        
        // Clear table
        const tableBody = document.getElementById('previewTableBody');
        tableBody.innerHTML = '';
        
        this.previewedQuestions = questions;
        
        questions.forEach((question, index) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>
                    <input type="checkbox" class="form-check-input question-checkbox" 
                           data-index="${index}" checked>
                </td>
                <td>
                    <div class="question-text" title="${question.question}">
                        ${question.question.length > 80 ? question.question.substring(0, 80) + '...' : question.question}
                    </div>
                </td>
                <td>
                    <span class="badge bg-secondary">${question.source.split('/')[2] || 'Custom'}</span>
                </td>
                <td>
                    <div class="answer-preview" title="${question.answer}">
                        ${question.answer.length > 100 ? question.answer.substring(0, 100) + '...' : question.answer}
                    </div>
                </td>
                <td>
                    <button class="btn btn-sm btn-outline-info" onclick="qaGenerator.showFullQuestion(${index})">
                        <i class="fas fa-eye"></i>
                    </button>
                </td>
            `;
            tableBody.appendChild(row);
        });
        
        this.addLogEntry(`Preview loaded: ${unique_count} questions found`, 'success');
        if (duplicates_removed > 0) {
            this.addLogEntry(`Removed ${duplicates_removed} duplicate questions`, 'info');
        }
    }

    selectAllQuestions(checked) {
        document.querySelectorAll('.question-checkbox').forEach(checkbox => {
            checkbox.checked = checked;
        });
        document.getElementById('selectAllCheckbox').checked = checked;
    }

    showFullQuestion(index) {
        const question = this.previewedQuestions[index];
        const modalContent = `
            <div class="mb-3">
                <h6>Question</h6>
                <p>${question.question}</p>
            </div>
            
            <div class="mb-3">
                <h6>Source</h6>
                <p><a href="${question.source}" target="_blank">${question.source}</a></p>
            </div>
            
            <div class="mb-3">
                <h6>Answer</h6>
                <div class="border p-3 bg-light">
                    ${question.answer}
                </div>
            </div>
        `;
        
        document.getElementById('questionDetails').innerHTML = modalContent;
        new bootstrap.Modal(document.getElementById('questionModal')).show();
    }

    processSelectedQuestions() {
        const selectedQuestions = [];
        document.querySelectorAll('.question-checkbox:checked').forEach(checkbox => {
            const index = parseInt(checkbox.dataset.index);
            selectedQuestions.push(this.previewedQuestions[index]);
        });

        if (selectedQuestions.length === 0) {
            alert('Please select at least one question to process');
            return;
        }

        // Close preview modal
        bootstrap.Modal.getInstance(document.getElementById('previewModal')).hide();

        // Start processing with selected questions
        this.startProcessingWithQuestions(selectedQuestions);
    }

    async startProcessingWithQuestions(questions) {
        this.addLogEntry(`Starting processing of ${questions.length} selected questions`, 'info');
        
        // Create a custom job data structure
        const requestData = {
            selected_questions: questions,
            mode: 'selected'
        };

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
                this.addLogEntry(`Processing job started: ${data.job_id}`, 'success');
                this.updateUIForJobStart();
            } else {
                this.addLogEntry(`Error: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Error starting processing:', error);
            this.addLogEntry('Error starting processing job', 'error');
        }
    }

    async loadAiProviders() {
        try {
            const response = await fetch('/api/ai-providers');
            const data = await response.json();
            
            this.aiProviders = data.providers;
            
            // Populate provider dropdown
            const providerSelect = document.getElementById('aiProvider');
            providerSelect.innerHTML = '';
            
            for (const [key, provider] of Object.entries(this.aiProviders)) {
                const option = document.createElement('option');
                option.value = key;
                option.textContent = provider.name;
                if (data.current.provider === key) {
                    option.selected = true;
                }
                providerSelect.appendChild(option);
            }
            
            this.updateModelOptions();
            
        } catch (error) {
            console.error('Error loading AI providers:', error);
        }
    }
    
    updateModelOptions() {
        const provider = document.getElementById('aiProvider').value;
        const modelSelect = document.getElementById('aiModel');
        
        modelSelect.innerHTML = '';
        
        if (this.aiProviders[provider]) {
            this.aiProviders[provider].models.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                if (model === this.aiProviders[provider].default) {
                    option.selected = true;
                }
                modelSelect.appendChild(option);
            });
        }
    }
    
    async saveAiProvider() {
        const provider = document.getElementById('aiProvider').value;
        const model = document.getElementById('aiModel').value;
        const statusDiv = document.getElementById('aiProviderStatus');
        
        try {
            const response = await fetch('/api/set-ai-provider', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    provider: provider,
                    model: model
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                statusDiv.className = `alert alert-${data.status === 'success' ? 'success' : 'warning'}`;
                statusDiv.textContent = data.message;
                statusDiv.style.display = 'block';
                
                // Update status and close modal after delay
                setTimeout(() => {
                    this.checkAiStatus();
                    bootstrap.Modal.getInstance(document.getElementById('aiProviderModal')).hide();
                }, 1500);
                
            } else {
                statusDiv.className = 'alert alert-danger';
                statusDiv.textContent = data.error;
                statusDiv.style.display = 'block';
            }
            
        } catch (error) {
            console.error('Error saving AI provider:', error);
            statusDiv.className = 'alert alert-danger';
            statusDiv.textContent = 'Error saving AI provider settings';
            statusDiv.style.display = 'block';
        }
    }

    async processBulkQuestions() {
        const questions = document.getElementById('bulkQuestions').value.trim();
        const topic = document.getElementById('bulkTopic').value;
        
        if (!questions) {
            alert('Please enter some questions to process');
            return;
        }
        
        const questionLines = questions.split('\n').filter(q => q.trim());
        
        if (questionLines.length === 0) {
            alert('No valid questions found');
            return;
        }
        
        if (questionLines.length > 20) {
            if (!confirm(`You have ${questionLines.length} questions. This might take a while. Continue?`)) {
                return;
            }
        }
        
        this.addLogEntry(`Starting bulk processing of ${questionLines.length} questions`, 'info');
        this.addLogEntry(`Topic: ${topic}`, 'info');
        
        try {
            const response = await fetch('/api/process-bulk-questions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    questions: questions,
                    topic: topic
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.currentJobId = data.job_id;
                this.addLogEntry(`Bulk processing started: ${data.message}`, 'success');
                this.updateUIForJobStart();
                
                // Disable bulk button
                document.getElementById('processBulkBtn').disabled = true;
                document.getElementById('processBulkBtn').innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
            } else {
                this.addLogEntry(`Error: ${data.error}`, 'error');
                alert(`Error: ${data.error}`);
            }
        } catch (error) {
            console.error('Error starting bulk processing:', error);
            this.addLogEntry('Error starting bulk processing', 'error');
            alert('Error starting bulk processing');
        }
    }

    handleProcessingStep(data) {
        const { step, question_id, timestamp, processing_time } = data;
        
        switch (step) {
            case 'ai_start':
                this.addLogEntry(`🔄 Starting ${data.ai_provider.toUpperCase()} processing: ${data.question}`, 'processing');
                this.addLogEntry(`📄 ${data.answer_preview}`, 'info');
                break;
                
            case 'ai_success':
                this.addLogEntry(`✅ ${data.ai_provider.toUpperCase()} completed (${processing_time}s): ${question_id}`, 'success');
                break;
                
            case 'ai_failed':
                this.addLogEntry(`❌ ${data.ai_provider.toUpperCase()} failed (${processing_time}s): ${data.error}`, 'error');
                break;
        }
    }
}

// Initialize the application when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.qaGenerator = new QAGenerator();
});