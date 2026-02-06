/**
 * Agent Platform Frontend
 * Handles WebSocket communication and UI updates
 */

class AgentPlatform {
    constructor() {
        this.sessionId = 'session_' + Date.now();
        this.ws = null;
        this.isConnected = false;
        this.isProcessing = false;
        this.subagents = new Map();
        this.currentProvider = 'gemini';

        this.init();
    }

    init() {
        // DOM Elements
        this.elements = {
            messages: document.getElementById('messages'),
            chatForm: document.getElementById('chatForm'),
            messageInput: document.getElementById('messageInput'),
            sendBtn: document.getElementById('sendBtn'),
            clearBtn: document.getElementById('clearBtn'),
            connectionStatus: document.getElementById('connectionStatus'),
            thinkingIndicator: document.getElementById('thinkingIndicator'),
            thinkingText: document.getElementById('thinkingText'),
            subagentList: document.getElementById('subagentList'),
            subagentCount: document.getElementById('subagentCount'),
            activeCount: document.getElementById('activeCount'),
            queuedCount: document.getElementById('queuedCount'),
            providerSelect: document.getElementById('providerSelect'),
        };

        // Event Listeners
        this.elements.chatForm.addEventListener('submit', (e) => this.handleSubmit(e));
        this.elements.clearBtn.addEventListener('click', () => this.clearChat());
        this.elements.messageInput.addEventListener('input', () => this.autoResize());
        this.elements.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.handleSubmit(e);
            }
        });

        // Provider selector
        this.elements.providerSelect.addEventListener('change', (e) => {
            this.changeProvider(e.target.value);
        });

        // Load config from backend to sync provider
        this.loadConfig();

        // Connect WebSocket
        this.connectWebSocket();

        // Poll status periodically
        setInterval(() => this.fetchStatus(), 5000);
    }

    async loadConfig() {
        try {
            const response = await fetch('/api/config');
            const data = await response.json();

            // Set provider from config
            if (data.llm && data.llm.default_provider) {
                this.currentProvider = data.llm.default_provider;
                this.elements.providerSelect.value = data.llm.default_provider;
                console.log(`Loaded provider from config: ${data.llm.default_provider}`);
            }
        } catch (error) {
            console.error('Failed to load config:', error);
        }
    }

    connectWebSocket() {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/api/ws/${this.sessionId}`;

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                this.isConnected = true;
                this.updateConnectionStatus('connected');
                console.log('WebSocket connected');
            };

            this.ws.onclose = () => {
                this.isConnected = false;
                this.updateConnectionStatus('disconnected');
                console.log('WebSocket disconnected');
                // Attempt reconnect after 3 seconds
                setTimeout(() => this.connectWebSocket(), 3000);
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus('error');
            };

            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };
        } catch (error) {
            console.error('Failed to connect WebSocket:', error);
            this.updateConnectionStatus('error');
        }
    }

    handleWebSocketMessage(data) {
        console.log('WS message:', data);

        switch (data.type) {
            case 'init':
                this.updateSubagents(data.data.subagents || []);
                break;
            case 'thinking':
                this.showThinking(data.data.status);
                break;
            case 'tool_calls':
                this.showToolCalls(data.data.tools);
                break;
            case 'tool_result':
                this.showToolResult(data.data);
                break;
            case 'complete':
                this.hideThinking();
                break;
            case 'registered':
            case 'updated':
                this.updateSubagentCard(data.data);
                break;
            default:
                console.log('Unknown message type:', data.type);
        }
    }

    updateConnectionStatus(status) {
        const dot = this.elements.connectionStatus.querySelector('.status-dot');
        const text = this.elements.connectionStatus.querySelector('.status-text');

        dot.className = 'status-dot';

        switch (status) {
            case 'connected':
                dot.classList.add('connected');
                text.textContent = 'Connected';
                break;
            case 'disconnected':
                text.textContent = 'Disconnected';
                break;
            case 'error':
                dot.classList.add('error');
                text.textContent = 'Error';
                break;
        }
    }

    async handleSubmit(e) {
        e.preventDefault();

        const message = this.elements.messageInput.value.trim();
        if (!message || this.isProcessing) return;

        // Clear input
        this.elements.messageInput.value = '';
        this.autoResize();

        // Hide welcome message
        const welcome = this.elements.messages.querySelector('.welcome-message');
        if (welcome) welcome.remove();

        // Add user message
        this.addMessage('user', message);

        // Show thinking
        this.isProcessing = true;
        this.showThinking('Processing your message...');
        this.elements.sendBtn.disabled = true;

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    session_id: this.sessionId,
                    provider: this.currentProvider
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error: ${response.status}`);
            }

            const data = await response.json();

            // Add assistant message
            this.hideThinking();
            this.addMessage('assistant', data.response);

        } catch (error) {
            console.error('Chat error:', error);
            this.hideThinking();
            this.addMessage('assistant', `Error: ${error.message}. Please try again.`);
        } finally {
            this.isProcessing = false;
            this.elements.sendBtn.disabled = false;
            this.elements.messageInput.focus();
        }
    }

    addMessage(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = this.formatContent(content);

        messageDiv.appendChild(contentDiv);
        this.elements.messages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    formatContent(content) {
        // Basic markdown-like formatting
        return content
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>')
            .replace(/```(\w+)?\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
    }

    showThinking(text) {
        this.elements.thinkingIndicator.style.display = 'flex';
        this.elements.thinkingText.textContent = text || 'Thinking...';
        this.scrollToBottom();
    }

    hideThinking() {
        this.elements.thinkingIndicator.style.display = 'none';
    }

    showToolCalls(tools) {
        tools.forEach(tool => {
            const eventDiv = document.createElement('div');
            eventDiv.className = 'tool-event';
            eventDiv.innerHTML = `
                <span>🔧</span>
                <span>Calling tool: <span class="tool-name">${tool.name}</span></span>
            `;
            this.elements.messages.appendChild(eventDiv);
        });
        this.scrollToBottom();
    }

    showToolResult(data) {
        const eventDiv = document.createElement('div');
        eventDiv.className = 'tool-event';
        eventDiv.innerHTML = `
            <span>✅</span>
            <span><span class="tool-name">${data.name}</span> completed</span>
        `;
        this.elements.messages.appendChild(eventDiv);
        this.scrollToBottom();
    }

    updateSubagents(subagents) {
        this.subagents.clear();
        subagents.forEach(sa => {
            this.subagents.set(sa.run_id, sa);
        });
        this.renderSubagents();
    }

    updateSubagentCard(subagent) {
        this.subagents.set(subagent.run_id, subagent);
        this.renderSubagents();
    }

    renderSubagents() {
        const list = this.elements.subagentList;
        const count = this.subagents.size;

        this.elements.subagentCount.textContent = count;

        if (count === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <span class="empty-icon">🎯</span>
                    <p>No active subagents</p>
                    <small>Subagents will appear here when spawned</small>
                </div>
            `;
            return;
        }

        list.innerHTML = '';

        // Sort by created_at descending
        const sorted = Array.from(this.subagents.values())
            .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

        sorted.forEach(sa => {
            const card = document.createElement('div');
            card.className = `subagent-card ${sa.status}`;
            card.innerHTML = `
                <div class="subagent-header">
                    <span class="subagent-label">${sa.label || 'Subagent'}</span>
                    <span class="subagent-status ${sa.status}">${sa.status}</span>
                </div>
                <div class="subagent-task">${sa.task}</div>
            `;
            list.appendChild(card);
        });
    }

    async fetchStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();

            this.elements.activeCount.textContent = data.active_subagents;
            this.elements.queuedCount.textContent = data.queued_subagents;

            // Also fetch subagents
            const subResponse = await fetch(`/api/subagents/${this.sessionId}`);
            const subData = await subResponse.json();
            this.updateSubagents(subData.subagents || []);

        } catch (error) {
            console.error('Status fetch error:', error);
        }
    }

    async clearChat() {
        // Clear UI
        this.elements.messages.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">✨</div>
                <h2>Welcome to Agent Platform</h2>
                <p>I'm an AI assistant with the ability to spawn subagents for parallel work.</p>
                <div class="capabilities">
                    <div class="capability">
                        <span class="cap-icon">🔍</span>
                        <span>Web Search</span>
                    </div>
                    <div class="capability">
                        <span class="cap-icon">🤖</span>
                        <span>Spawn Subagents</span>
                    </div>
                    <div class="capability">
                        <span class="cap-icon">⚡</span>
                        <span>Parallel Processing</span>
                    </div>
                </div>
                <p class="try-prompt">Try: "Research the latest AI news and summarize in 3 bullet points"</p>
            </div>
        `;

        // Clear server state
        try {
            await fetch(`/api/clear/${this.sessionId}`, { method: 'POST' });
        } catch (error) {
            console.error('Clear error:', error);
        }
    }

    autoResize() {
        const textarea = this.elements.messageInput;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
    }

    scrollToBottom() {
        this.elements.messages.scrollTop = this.elements.messages.scrollHeight;
    }

    async changeProvider(provider) {
        this.currentProvider = provider;
        console.log(`Switched to provider: ${provider}`);

        try {
            await fetch(`/api/provider/${this.sessionId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider: provider })
            });

            // Show feedback
            this.showProviderNotification(provider);
        } catch (error) {
            console.error('Provider switch error:', error);
        }
    }

    showProviderNotification(provider) {
        const providerNames = {
            'gemini': 'Google Gemini',
            'deepseek': 'DeepSeek',
            'openai': 'ChatGPT (OpenAI)'
        };

        // Add a subtle notification to the chat
        const notifDiv = document.createElement('div');
        notifDiv.className = 'tool-event';
        notifDiv.innerHTML = `<span>🔄</span> <span>Switched to <strong>${providerNames[provider] || provider}</strong></span>`;
        notifDiv.style.borderLeftColor = 'var(--accent-primary)';

        // Only add if there are messages (not just welcome)
        const welcome = this.elements.messages.querySelector('.welcome-message');
        if (!welcome) {
            this.elements.messages.appendChild(notifDiv);
            this.scrollToBottom();
        }
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.agentPlatform = new AgentPlatform();
});
