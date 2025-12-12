// =================== Global State ===================
let messages = [];
let currentChatId = localStorage.getItem('currentChatId') || null;
let chatHistory = [];
let attachedFile = null; // Store file for attachment before sending

// OCR Sidebar State
let ocrDocuments = {};  // Store OCR results by ID
let currentOcrId = null;  // Currently displayed OCR

// =================== API ===================
const API = {
    async chat(prompt, sessionId = 'default') {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ prompt, session_id: sessionId })
        });
        if (!response.ok) throw new Error('Chat request failed');
        const data = await response.json();

        // Debug: Check raw JSON response
        console.log('Raw JSON response received');
        console.log('Response keys:', Object.keys(data));
        if (data.reply) {
            console.log('Reply length:', data.reply.length);
            // Check first occurrence of backslash
            const bsIdx = data.reply.indexOf('\\');
            if (bsIdx >= 0) {
                console.log(`Backslash found at index ${bsIdx}`);
                console.log('Context:', JSON.stringify(data.reply.substring(Math.max(0, bsIdx - 10), bsIdx + 20)));
            }
        }

        return data;
    },

    async getMessages(sessionId = 'default') {
        const response = await fetch(`/api/messages?session_id=${sessionId}`);
        if (!response.ok) throw new Error('Failed to get messages');
        return await response.json();
    },

    async clearMessages(sessionId = 'default') {
        const response = await fetch('/api/messages/clear', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId })
        });
        if (!response.ok) throw new Error('Failed to clear messages');
        return await response.json();
    },

    async newSession() {
        const response = await fetch('/api/session/new', { method: 'POST' });
        if (!response.ok) throw new Error('Failed to create session');
        return await response.json();
    }
};

// =================== Initialize ===================
// Wait for KaTeX to be loaded before initializing
function waitForKaTeX(callback, maxAttempts = 50) {
    if (typeof katex !== 'undefined' && typeof renderMathInElement !== 'undefined') {
        console.log('KaTeX loaded successfully');
        callback();
    } else if (maxAttempts > 0) {
        setTimeout(() => waitForKaTeX(callback, maxAttempts - 1), 100);
    } else {
        console.error('KaTeX failed to load after 5 seconds');
        callback(); // Continue anyway
    }
}

document.addEventListener('DOMContentLoaded', () => {
    waitForKaTeX(() => {
        initializeApp();
    });
});

function initializeApp() {
    // Load chat history
    loadChatHistory();

    // Load current session messages
    loadCurrentMessages();

    // Setup event listeners
    setupEventListeners();

    // Auto-resize textarea
    setupTextareaAutoResize();

    // Initialize OCR Sidebar
    initOcrSidebar();
    console.log('✅ OCR Sidebar initialized');
}

function setupEventListeners() {
    const sendBtn = document.getElementById('sendBtn');
    const chatInput = document.getElementById('chatInput');
    const newChatBtn = document.getElementById('newChatBtn');
    const attachFileBtn = document.getElementById('attachFileBtn');

    sendBtn.addEventListener('click', handleSendMessage);
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    });

    newChatBtn.addEventListener('click', handleNewChat);

    // OCR File upload handler
    if (attachFileBtn) {
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = 'application/pdf,.png,.jpg,.jpeg';
        fileInput.style.display = 'none';
        document.body.appendChild(fileInput);

        attachFileBtn.addEventListener('click', () => {
            fileInput.click();
        });

        fileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            console.log('📎 File selected for OCR:', file.name);
            const thinkingId = showThinkingIndicator('Đang xử lý OCR...');

            try {
                await uploadOCRFile(file);
                removeThinkingIndicator(thinkingId);
                console.log('✅ OCR upload completed');
            } catch (error) {
                removeThinkingIndicator(thinkingId);
                console.error('❌ OCR upload failed:', error);
                showNotification(`❌ Lỗi: ${error.message}`);
            }

            fileInput.value = '';
        });
    }
}

function setupTextareaAutoResize() {
    const textarea = document.getElementById('chatInput');
    textarea.addEventListener('input', () => {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
    });
}

// =================== Chat History ===================
function loadChatHistory() {
    // Load from localStorage - persistent storage, never auto-deleted
    const saved = localStorage.getItem('chatHistory');
    if (saved) {
        try {
            chatHistory = JSON.parse(saved);
            // Ensure chatHistory is an array
            if (!Array.isArray(chatHistory)) {
                console.warn('chatHistory is not an array, resetting...');
                chatHistory = [];
                saveChatHistory();
            }
            renderChatHistory();
        } catch (error) {
            console.error('Error parsing chatHistory:', error);
            chatHistory = [];
            saveChatHistory();
        }
    } else {
        // Initialize empty array if no history exists
        chatHistory = [];
        saveChatHistory();
    }
}

function saveChatHistory() {
    // Persist chat history to localStorage - this is permanent until user explicitly deletes
    try {
        localStorage.setItem('chatHistory', JSON.stringify(chatHistory));
        console.log(`Saved chat history: ${chatHistory.length} chats`);
    } catch (error) {
        console.error('Error saving chatHistory:', error);
        // If storage is full, try to clear old data or warn user
        if (error.name === 'QuotaExceededError') {
            alert('Lưu trữ đầy. Vui lòng xóa một số chat cũ hoặc dữ liệu khác.');
        }
    }
}

function renderChatHistory() {
    const list = document.getElementById('chatHistoryList');
    if (!list) {
        console.error('chatHistoryList element not found');
        return;
    }

    list.innerHTML = '';

    if (chatHistory.length === 0) {
        const emptyMsg = document.createElement('div');
        emptyMsg.className = 'history-empty';
        emptyMsg.style.padding = '1rem';
        emptyMsg.style.color = 'var(--text-tertiary)';
        emptyMsg.style.fontSize = '0.85rem';
        emptyMsg.style.textAlign = 'center';
        emptyMsg.textContent = 'Chưa có lịch sử chat';
        list.appendChild(emptyMsg);
        return;
    }

    chatHistory.forEach((chat, index) => {
        const item = document.createElement('div');
        item.className = 'history-item';
        if (chat.id === currentChatId) {
            item.classList.add('active');
        }

        const isStarred = chat.starred || false;

        item.innerHTML = `
            <span class="history-item-icon">💬</span>
            <span class="history-item-title" data-chat-id="${chat.id}">${escapeHtml(chat.title || 'New Chat')}</span>
            <div class="history-item-actions">
                <button class="history-action-btn star-btn" onclick="event.stopPropagation(); toggleStar('${chat.id}')" title="${isStarred ? 'Unstar' : 'Star'}">
                    <span class="action-icon">${isStarred ? '★' : '☆'}</span>
                </button>
                <button class="history-action-btn rename-btn" onclick="event.stopPropagation(); startRename('${chat.id}')" title="Rename">
                    <span class="action-icon">✏️</span>
                </button>
                <button class="history-action-btn delete-btn" onclick="event.stopPropagation(); showDeleteConfirm('${chat.id}')" title="Delete">
                    <span class="action-icon">🗑️</span>
                </button>
            </div>
        `;

        item.addEventListener('click', (e) => {
            // Don't load chat if clicking on actions
            if (!e.target.closest('.history-item-actions') &&
                !e.target.closest('.history-item-title[contenteditable="true"]')) {
                console.log('Loading chat:', chat.id);
                loadChat(chat.id);
            }
        });

        // Double-click to rename
        const titleElement = item.querySelector('.history-item-title');
        titleElement.addEventListener('dblclick', (e) => {
            e.stopPropagation();
            startRename(chat.id);
        });

        list.appendChild(item);
    });
}

function addToChatHistory(title, chatId) {
    const existing = chatHistory.findIndex(c => c.id === chatId);
    if (existing >= 0) {
        chatHistory[existing].title = title;
        chatHistory[existing].updatedAt = new Date().toISOString();
    } else {
        chatHistory.unshift({
            id: chatId,
            title: title,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        });
    }
    saveChatHistory();
    renderChatHistory();
}

// =================== Chat Management ===================
async function handleNewChat() {
    try {
        const response = await API.newSession();
        currentChatId = response.session_id;
        localStorage.setItem('currentChatId', currentChatId);
        messages = [];
        ocrDocuments = {}; // Reset OCR documents for new chat
        renderMessages();
        updateChatHistory();
        renderChatHistory(); // Update active state
        console.log('Created new chat:', currentChatId);
    } catch (error) {
        console.error('Failed to create new chat:', error);
        alert('Failed to create new chat. Please try again.');
    }
}

async function loadChat(chatId) {
    console.log('Loading chat:', chatId);
    currentChatId = chatId;
    localStorage.setItem('currentChatId', chatId);

    try {
        const response = await API.getMessages(chatId);
        console.log('Messages response:', response);
        const backendMessages = response.messages || [];
        console.log(`Loaded ${backendMessages.length} messages from backend for chat ${chatId}`);

        // Load messages from localStorage (includes OCR messages)
        const localStorageMessages = localStorage.getItem(`messages_${chatId}`);
        let localMessages = [];
        if (localStorageMessages) {
            try {
                localMessages = JSON.parse(localStorageMessages);
                console.log(`Found ${localMessages.length} messages in localStorage`);
            } catch (e) {
                console.error('Error parsing localStorage messages:', e);
            }
        }

        // Merge: Use localStorage if it has more messages (includes OCR), otherwise use backend
        // This assumes localStorage is the source of truth for client-side only messages like OCR
        if (localMessages.length >= backendMessages.length) {
            messages = localMessages;
            console.log(`Using ${messages.length} messages from localStorage (includes OCR)`);
        } else {
            messages = backendMessages;
            console.log(`Using ${messages.length} messages from backend`);
        }

        // Restore OCR documents for this session
        const savedOcrDocs = localStorage.getItem(`ocrDocs_${chatId}`);
        if (savedOcrDocs) {
            try {
                ocrDocuments = JSON.parse(savedOcrDocs);
                console.log(`Restored ${Object.keys(ocrDocuments).length} OCR documents`);
            } catch (e) {
                console.error('Error parsing OCR documents:', e);
                ocrDocuments = {};
            }
        } else {
            ocrDocuments = {};
        }



        if (messages.length === 0) {
            console.warn('No messages found for this chat');
        }

        renderMessages();

        // Restore notification panel from ocrDocuments
        restoreOcrNotifications();

        updateChatHistory();

        // Update active state in history
        renderChatHistory();
    } catch (error) {
        console.error('Failed to load chat:', error);
        alert('Failed to load chat. Please try again.');
    }
}

async function loadCurrentMessages() {
    if (currentChatId) {
        console.log('Loading current chat messages:', currentChatId);
        await loadChat(currentChatId);
    } else {
        console.log('No current chat ID, showing empty state');
        renderMessages(); // Show empty state
    }
}

function updateChatHistory() {
    if (messages.length > 0 && currentChatId) {
        const firstUserMessage = messages.find(m => m.role === 'user');
        const title = firstUserMessage ? firstUserMessage.content.substring(0, 50) : 'New Chat';
        addToChatHistory(title, currentChatId);
    }
}

// =================== Message Handling ===================
async function handleSendMessage() {
    const input = document.getElementById('chatInput');
    const prompt = input.value.trim();

    if (!prompt) return;

    // Ensure we have a chat session
    if (!currentChatId) {
        try {
            const response = await API.newSession();
            currentChatId = response.session_id;
            localStorage.setItem('currentChatId', currentChatId);
            console.log('Created new session for message:', currentChatId);
        } catch (error) {
            console.error('Failed to create session:', error);
            alert('Failed to create chat session. Please try again.');
            return;
        }
    }

    // Check if there's an attached file
    if (typeof attachedFile !== 'undefined' && attachedFile) {
        console.log('📎 File attached, uploading for OCR and Notion save...');
        const fileToUpload = attachedFile;  // Thêm dòng này
        attachedFile = null;

        // Show user message with file indicator
        const userMessage = {
            role: 'user',
            content: `${prompt}\n\n *File đính kèm: ${fileToUpload.name}*`,
            timestamp: new Date().toISOString()
        };
        messages.push(userMessage);
        renderMessage(userMessage);

        // Clear input
        input.value = '';
        input.style.height = 'auto';

        // Remove file attachment UI
        const attachmentDiv = document.getElementById('fileAttachment');
        if (attachmentDiv) {
            attachmentDiv.remove();
        }

        // Show processing indicator
        const thinkingId = showThinkingIndicator('Đang OCR và lưu vào Notion...');
        const startTime = Date.now();

        try {
            // Upload file for OCR (backend will save to Notion)
            const formData = new FormData();
            formData.append('file', fileToUpload);
            formData.append('session_id', currentChatId);

            console.log('📤 Uploading file for OCR...');
            const uploadResponse = await fetch('/api/upload-file', {
                method: 'POST',
                body: formData
            });

            if (!uploadResponse.ok) {
                const errorData = await uploadResponse.json();
                throw new Error(errorData.error || 'Upload failed');
            }

            const uploadData = await uploadResponse.json();
            const endTime = Date.now();
            const uploadTime = ((endTime - startTime) / 1000).toFixed(1);

            console.log('✅ OCR completed:', uploadData);

            // Remove thinking indicator
            removeThinkingIndicator(thinkingId);

            // Show OCR result message
            let resultMessage = `✅ **OCR hoàn tất**\n\n`;
            resultMessage += `📄 File: ${uploadData.filename}\n`;
            resultMessage += `📊 Ký tự: ${uploadData.char_count}\n`;
            resultMessage += `⏱️ Thời gian: ${uploadTime}s\n\n`;

            if (uploadData.notion_saved) {
                resultMessage += `💾 **Đã lưu vào Notion**\n`;
                resultMessage += `📝 Trang: "${uploadData.notion_page_title}"\n\n`;
                resultMessage += `Bạn có thể hỏi tôi về nội dung file này!`;
            } else {
                resultMessage += `⚠️ ${uploadData.message || 'Chưa lưu vào Notion'}\n\n`;
                resultMessage += `**Preview nội dung:**\n\`\`\`\n${uploadData.ocr_preview}\n\`\`\``;
            }

            const ocrResultMessage = {
                role: 'assistant',
                content: resultMessage,
                timestamp: new Date().toISOString()
            };
            messages.push(ocrResultMessage);
            renderMessage(ocrResultMessage);

            // attachedFile already cleared at start
            input.placeholder = 'Tôi có thể giúp gì cho bạn?';

            // Update chat history
            updateChatHistory();
            saveMessages();

            console.log('✅ File OCR and Notion save completed');

        } catch (error) {
            removeThinkingIndicator(thinkingId);
            console.error('Error processing file:', error);

            const errorMessage = {
                role: 'assistant',
                content: `❌ **Lỗi khi xử lý file**: ${error.message}\n\nVui lòng thử lại.`,
                timestamp: new Date().toISOString()
            };
            messages.push(errorMessage);
            renderMessage(errorMessage);

            // Don't clear attached file on error so user can retry
        }

        return; // Exit early since we handled file upload case
    }

    // Original flow: No file attached, just send text prompt
    // Clear input
    input.value = '';
    input.style.height = 'auto';

    // Add user message
    const userMessage = {
        role: 'user',
        content: prompt,
        timestamp: new Date().toISOString()
    };
    messages.push(userMessage);
    renderMessage(userMessage);

    // Show thinking indicator
    const thinkingId = showThinkingIndicator();
    const startTime = Date.now();

    try {
        console.log('Sending message to session:', currentChatId);
        const response = await API.chat(prompt, currentChatId);
        const endTime = Date.now();
        const responseTime = ((endTime - startTime) / 1000).toFixed(1);

        // Debug: Check LaTeX in response
        console.log('='.repeat(80));
        console.log('DEBUG: Response from backend:');
        console.log('Response length:', response.reply?.length || 0);
        const replyText = response.reply || '';

        // Check character codes to see actual backslashes
        const backslashIndex = replyText.indexOf('\\');
        if (backslashIndex >= 0) {
            console.log(`Found backslash at index ${backslashIndex}`);
            console.log('Characters around backslash:',
                JSON.stringify(replyText.substring(Math.max(0, backslashIndex - 5), backslashIndex + 10)));
        }

        // Check for LaTeX patterns with actual character inspection
        console.log('Contains $$:', replyText.includes('$$'));
        console.log('Contains $:', replyText.match(/\$[^$]+\$/g)?.length || 0);

        // Check for backslash patterns - need to check actual string content
        const hasBackslashBracket = replyText.includes('\\[') || replyText.includes('\\]');
        const hasBackslashParen = replyText.includes('\\(') || replyText.includes('\\)');
        console.log('Contains \\[:', hasBackslashBracket);
        console.log('Contains \\(:', hasBackslashParen);

        // Try to find LaTeX patterns with regex
        const latexMatches = replyText.match(/\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\$\$[\s\S]*?\$\$|\$[^$\n]+\$/g);
        if (latexMatches) {
            console.log(`Found ${latexMatches.length} LaTeX patterns:`, latexMatches.slice(0, 3));
        } else {
            console.log('NO LaTeX patterns found with regex!');
            // Try manual search
            const manualSearch = [];
            let idx = 0;
            while ((idx = replyText.indexOf('\\[', idx)) >= 0) {
                const endIdx = replyText.indexOf('\\]', idx);
                if (endIdx > idx) {
                    manualSearch.push(replyText.substring(idx, endIdx + 2));
                    idx = endIdx + 2;
                } else {
                    break;
                }
            }
            console.log(`Manual search found ${manualSearch.length} \\[...\\] patterns`);
            if (manualSearch.length > 0) {
                console.log('First manual match:', manualSearch[0].substring(0, 100));
            }
        }

        // Show raw string representation
        const sampleStart = replyText.indexOf('\\[') >= 0 ? replyText.indexOf('\\[') : 0;
        console.log('Sample (first 500 chars from LaTeX or start):', replyText.substring(sampleStart, sampleStart + 500));
        console.log('='.repeat(80));

        // Replay thinking trace if available
        if (response.trace && response.trace.length > 0) {
            await replayThinkingTrace(thinkingId, response.trace);
        } else {
            // Fallback delay if no trace (rare)
            await new Promise(r => setTimeout(r, 500));
        }

        // Mark thinking as completed
        updateThinkingComplete(thinkingId);

        // Add assistant message
        const assistantMessage = {
            role: 'assistant',
            content: response.reply,
            timestamp: new Date().toISOString(),
            responseTime: responseTime
        };
        messages.push(assistantMessage);

        // Render final message
        renderMessage(assistantMessage);

        // Update chat history
        updateChatHistory();

        // Save messages
        saveMessages();

        console.log('Message sent successfully, total messages:', messages.length);
    } catch (error) {
        removeThinkingIndicator(thinkingId);
        console.error('Chat error:', error);
        alert('Failed to send message. Please try again.');
    }
}

// =================== File Upload Handling ===================
async function handleFileUpload(file) {
    console.log('📁 File selected:', file.name, file.type, file.size);

    // Validate file type
    const validTypes = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg'];
    if (!validTypes.includes(file.type)) {
        alert('Chỉ hỗ trợ file PDF hoặc ảnh (PNG, JPG, JPEG)');
        return;
    }

    // Validate file size (max 20MB)
    const maxSize = 20 * 1024 * 1024; // 20MB
    if (file.size > maxSize) {
        alert('File quá lớn! Kích thước tối đa là 20MB');
        return;
    }

    // Store file for later upload when user sends message
    attachedFile = file;

    // Show file attachment in input area
    showFileAttachment(file.name, file.size);

    // Focus on input so user can type their prompt
    const chatInput = document.getElementById('chatInput');
    chatInput.focus();
    chatInput.placeholder = `Hãy nhập câu hỏi về file "${file.name}"...`;
}

// Show file attachment indicator
function showFileAttachment(filename, filesize) {
    const inputWrapper = document.querySelector('.chat-input-wrapper');
    const existingAttachment = document.getElementById('fileAttachment');

    if (existingAttachment) {
        existingAttachment.remove();
    }

    const filesizeText = (filesize / 1024 / 1024).toFixed(2) + ' MB';

    const attachmentDiv = document.createElement('div');
    attachmentDiv.id = 'fileAttachment';
    attachmentDiv.className = 'file-attachment';
    attachmentDiv.innerHTML = `
        <div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 0.75rem; background: linear-gradient(135deg, rgba(168, 85, 247, 0.1) 0%, rgba(236, 72, 153, 0.1) 100%); border: 1px solid rgba(168, 85, 247, 0.3); border-radius: 8px; margin-bottom: 0.5rem;">
            <span style="font-size: 1.2rem;">📎</span>
            <div style="flex: 1; min-width: 0;">
                <div style="font-size: 0.875rem; color: var(--text-primary); font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${filename}</div>
                <div style="font-size: 0.75rem; color: var(--text-tertiary);">${filesizeText}</div>
            </div>
            <button onclick="removeFileAttachment()" style="background: none; border: none; color: var(--text-tertiary); cursor: pointer; font-size: 1.2rem; padding: 0.25rem; line-height: 1; transition: color 0.2s;" title="Xóa file" onmouseover="this.style.color='var(--text-primary)'" onmouseout="this.style.color='var(--text-tertiary)'">×</button>
        </div>
    `;

    inputWrapper.insertBefore(attachmentDiv, inputWrapper.firstChild);
}

// Remove file attachment
function removeFileAttachment() {
    attachedFile = null;

    const attachmentDiv = document.getElementById('fileAttachment');
    if (attachmentDiv) {
        attachmentDiv.remove();
    }

    const chatInput = document.getElementById('chatInput');
    chatInput.placeholder = 'Tôi có thể giúp gì cho bạn?';
}


// =================== OCR SIDEBAR FUNCTIONS ===================

// Upload OCR file to backend
async function uploadOCRFile(file) {
    // Show progress modal
    OCRProgress.show(file.name, file.size);

    try {
        // Step 1: Upload (0-25%)
        OCRProgress.startUpload();

        const fd = new FormData();
        fd.append("file", file);

        // Simulate upload progress
        await new Promise(resolve => setTimeout(resolve, 500));
        OCRProgress.setProgress(25);

        // Step 2: Processing (25-75%)
        OCRProgress.startProcessing();

        const res = await fetch('/api/ocr_upload', { method: 'POST', body: fd });

        if (!res.ok) {
            const error = await res.json();
            OCRProgress.error(error.error || 'OCR upload failed');
            throw new Error(error.error || 'OCR upload failed');
        }

        // Simulate processing progress
        OCRProgress.updateProcessing(50);
        await new Promise(resolve => setTimeout(resolve, 300));

        const data = await res.json();

        // Step 3: Extracting (75-95%)
        OCRProgress.startExtracting();
        await new Promise(resolve => setTimeout(resolve, 400));

        // Store OCR data
        ocrDocuments[data.ocr_id] = data;

        // Step 4: Complete (100%)
        OCRProgress.complete();

        // Render message after modal hides
        setTimeout(() => {
            renderOcrMessage(data.ocr_id, data.meta.file_name);
        }, 1500);

        return data;
    } catch (error) {
        OCRProgress.error(error.message);
        throw error;
    }
}

// Render OCR notification in fixed panel
function renderOcrMessage(ocrId, fileName) {
    const panel = document.getElementById('ocrNotificationsList');
    if (!panel) return;

    // Get file metadata
    const doc = ocrDocuments[ocrId];
    const charCount = doc.meta.char_count || 0;
    const processedAt = new Date(doc.meta.processed_at || Date.now());
    const timeAgo = getTimeAgo(processedAt);

    // Create notification card
    const notificationCard = document.createElement('div');
    notificationCard.className = 'ocr-notification-item';
    notificationCard.dataset.ocrId = ocrId;
    notificationCard.innerHTML = `
        <div class="ocr-notification-header">
            <div class="ocr-notification-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
            </div>
            <div class="ocr-notification-info">
                <div class="ocr-notification-filename" title="${fileName}">${fileName}</div>
                <div class="ocr-notification-meta">${charCount.toLocaleString()} characters • ${timeAgo}</div>
            </div>
        </div>
        <div class="ocr-notification-actions">
            <button class="ocr-action-btn" onclick="openOcrSidebar('${ocrId}')">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                    <circle cx="12" cy="12" r="3"></circle>
                </svg>
                View Text
            </button>
            <button class="ocr-action-btn" onclick="removeOcrNotification('${ocrId}')">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
                Remove
            </button>
        </div>
    `;

    // Add to panel (prepend to show newest first)
    panel.prepend(notificationCard);

    // Update badge count
    updateOcrBadgeCount();

    // Explicitly save ocrDocuments to ensure persistence
    saveMessages();
}

// Restore OCR notifications on load
function restoreOcrNotifications() {
    const list = document.getElementById('ocrNotificationsList');
    if (!list) return;

    list.innerHTML = ''; // Clear existing

    // Sort docs by time (newest first)
    const docs = Object.values(ocrDocuments).sort((a, b) => {
        const timeA = new Date(a.meta.processed_at || 0);
        const timeB = new Date(b.meta.processed_at || 0);
        return timeA - timeB; // We use prepend in renderOcrMessage, so we sort oldest to newest to end up with newest on top
    });

    docs.forEach(doc => {
        renderOcrMessage(doc.ocr_id, doc.meta.file_name);
    });
}

// Helper function to get time ago string
function getTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    if (seconds < 60) return 'just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
}

// Remove OCR notification
function removeOcrNotification(ocrId) {
    const card = document.querySelector(`.ocr-notification-item[data-ocr-id="${ocrId}"]`);
    if (card) {
        card.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => card.remove(), 300);
    }
}

// Toggle OCR panel between badge and expanded view
function toggleOcrPanel() {
    const panel = document.getElementById('ocrNotificationsPanel');
    if (panel) {
        panel.classList.toggle('collapsed');
    }
}

// Update OCR badge count
function updateOcrBadgeCount() {
    const badge = document.getElementById('ocrBadgeCount');
    if (badge) {
        const count = Object.keys(ocrDocuments).length;
        badge.textContent = count;

        // Auto-expand if there are documents and panel is collapsed
        const panel = document.getElementById('ocrNotificationsPanel');
        if (count > 0 && panel && panel.classList.contains('collapsed')) {
            // Optional: auto-expand on first document
            // panel.classList.remove('collapsed');
        }
    }
}

// Make toggleOcrPanel globally accessible
window.toggleOcrPanel = toggleOcrPanel;

// Open OCR sidebar
function openOcrSidebar(ocrId) {
    const doc = ocrDocuments[ocrId];
    if (!doc) {
        console.error('OCR document not found:', ocrId);
        return;
    }

    currentOcrId = ocrId;

    const sidebar = document.getElementById('ocrSidebar');
    const title = document.getElementById('ocrSidebarTitle');
    const container = document.getElementById('ocrTextContainer');
    const mainContent = document.querySelector('.main-content');
    const notificationsPanel = document.getElementById('ocrNotificationsPanel');

    title.textContent = doc.meta.file_name;

    // Store original HTML in data attribute for later extraction
    container.dataset.originalHtml = doc.text;

    // Render as HTML for better formatting
    container.innerHTML = doc.text;

    // Add class to main content for smooth transition
    if (mainContent) {
        mainContent.classList.add('sidebar-open');
    }

    // Move notifications panel away
    if (notificationsPanel) {
        notificationsPanel.classList.remove('sidebar-open');
        notificationsPanel.classList.add('hidden-by-sidebar');
    }

    sidebar.classList.remove('hidden');

    console.log('Opened OCR sidebar for:', doc.meta.file_name);
}

// Close OCR sidebar
function closeOcrSidebar() {
    const sidebar = document.getElementById('ocrSidebar');
    const mainContent = document.querySelector('.main-content');
    const notificationsPanel = document.getElementById('ocrNotificationsPanel');

    sidebar.classList.add('hidden');

    // Remove class from main content for smooth transition
    if (mainContent) {
        mainContent.classList.remove('sidebar-open');
    }

    // Show notifications panel again
    if (notificationsPanel) {
        notificationsPanel.classList.remove('hidden-by-sidebar');
    }

    currentOcrId = null;
}

// Show context menu on text selection
function showContextMenu(e) {
    const selection = window.getSelection();
    const text = selection.toString().trim();

    if (!text) {
        document.getElementById('ocrContextMenu').classList.add('hidden');
        return;
    }

    e.preventDefault();

    const menu = document.getElementById('ocrContextMenu');
    menu.style.left = `${e.pageX}px`;
    menu.style.top = `${e.pageY}px`;
    menu.classList.remove('hidden');

    // Store selection for later use (for HTML extraction)
    menu.dataset.hasSelection = 'true';
}

// Helper to extract Markdown/LaTeX from selection
function getSelectedMarkdown() {
    const selection = window.getSelection();
    if (selection.rangeCount === 0) return '';

    // Clone range to avoid modifying user selection visually
    const range = selection.getRangeAt(0).cloneRange();

    // Helper to find math wrapper
    const getMathWrapper = (node) => {
        if (!node) return null;
        const el = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
        if (!el) return null;
        return el.closest('.latex-inline-block, .latex-display-block');
    };

    // Expand range to include full math blocks if partially selected
    const startWrapper = getMathWrapper(range.startContainer);
    if (startWrapper) range.setStartBefore(startWrapper);

    const endWrapper = getMathWrapper(range.endContainer);
    if (endWrapper) range.setEndAfter(endWrapper);

    // Clone expanded content
    const fragment = range.cloneContents();
    const div = document.createElement('div');
    div.appendChild(fragment);

    function convertNode(node) {
        if (node.nodeType === Node.TEXT_NODE) {
            return node.textContent;
        }

        if (node.nodeType === Node.ELEMENT_NODE) {
            // Priority 1: Check for LaTeX data attribute (our custom wrapper)
            const latex = node.getAttribute('data-latex');
            if (latex) {
                if (node.classList.contains('latex-display-block') || node.tagName === 'DIV' || node.style.display === 'block') {
                    return `\n\`\`\`math\n${latex}\n\`\`\`\n`;
                } else {
                    return `$${latex}$`;
                }
            }

            // Priority 2: Check for KaTeX root element (Fallback if wrapper is missing)
            if (node.classList.contains('katex')) {
                const annotation = node.querySelector('annotation');
                if (annotation) {
                    return `$${annotation.textContent}$`;
                }
                // Try mathml content if annotation missing
                const mathml = node.querySelector('.katex-mathml');
                if (mathml) {
                    return `$${mathml.textContent}$`;
                }
            }

            // Priority 3: Ignore internal KaTeX elements to prevent duplication
            // (Only ignore if we haven't extracted it in Priority 2)
            if (node.classList.contains('katex-mathml') ||
                node.classList.contains('katex-html') ||
                node.tagName === 'ANNOTATION') {
                return '';
            }

            // Priority 4: Traverse children
            const isBlock = ['P', 'DIV', 'BR', 'TR', 'LI'].includes(node.tagName);
            if (node.tagName === 'BR') return '\n';

            let content = '';
            node.childNodes.forEach(child => {
                content += convertNode(child);
            });

            if (isBlock) {
                // Add newlines only if content is not empty
                return content.trim() ? '\n' + content + '\n' : '';
            }
            return content;
        }
        return '';
    }

    let markdown = convertNode(div);
    // Cleanup excess whitespace and generic LaTeX/Math artifacts
    markdown = markdown.replace(/\n\s*\n\s*\n/g, '\n\n').trim();
    return markdown;
}

// Handle context menu actions
function onSelectionMenuClick(e) {
    const action = e.target.closest('button').dataset.action;

    // Get markdown if possible, otherwise plain text
    let text = getSelectedMarkdown();
    if (!text) {
        text = window.getSelection().toString().trim();
    }

    if (!text) return;

    if (action === 'copy') {
        navigator.clipboard.writeText(text);
        showNotification('✅ Đã copy văn bản');
    } else if (action === 'insert_chat') {
        insertTextToChatInput(text);
    } else if (action === 'solve_exercise') {
        console.log('Sending selected text (Markdown) for solve exercise');
        sendOcrAsMessage(text);
    } else if (action === 'save_notion') {
        saveOcrSnippetToNotion(text);
    }

    document.getElementById('ocrContextMenu').classList.add('hidden');
}

// Send OCR text as user message to solve exercise
async function sendOcrAsMessage(htmlText) {
    // Ensure we have a chat session
    if (!currentChatId) {
        try {
            const response = await API.newSession();
            currentChatId = response.session_id;
            localStorage.setItem('currentChatId', currentChatId);
            console.log('Created new session for OCR message:', currentChatId);
        } catch (error) {
            console.error('Failed to create session:', error);
            showNotification('❌ Không thể tạo session');
            return;
        }
    }

    // Create a temporary div to render HTML and extract plain text for display
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = htmlText;
    const displayText = tempDiv.textContent || tempDiv.innerText || '';

    // Show user message with rendered text (for UI display)
    const userMessage = {
        role: 'user',
        content: displayText.trim(),
        timestamp: new Date().toISOString()
    };
    messages.push(userMessage);
    renderMessage(userMessage);
    saveMessages();

    // Show thinking indicator
    const thinkingId = showThinkingIndicator('Đang giải bài tập...');

    try {
        // Send text to backend for processing
        console.log('Calling API.sendMessage with:', {
            sessionId: currentChatId,
            textLength: htmlText.length,
            textPreview: htmlText.substring(0, 100)
        });

        const response = await API.chat(htmlText, currentChatId);

        console.log('API response received:', response);

        // Replay thinking trace if available
        if (response.trace && response.trace.length > 0) {
            await replayThinkingTrace(thinkingId, response.trace);
        } else {
            // Fallback delay if no trace
            await new Promise(r => setTimeout(r, 500));
        }

        // Mark thinking as completed (keeps it visible)
        updateThinkingComplete(thinkingId);

        if (response.reply) {
            const assistantMessage = {
                role: 'assistant',
                content: response.reply,
                timestamp: new Date().toISOString()
            };
            messages.push(assistantMessage);
            renderMessage(assistantMessage);
            updateChatHistory();
            saveMessages();
        } else {
            console.warn('No response content in API response:', response);
            showNotification('⚠️ Không nhận được phản hồi từ AI');
        }
    } catch (error) {
        updateThinkingComplete(thinkingId, true); // Show error state but keep visible
        console.error('Error sending OCR message:', error);
        console.error('Error details:', {
            message: error.message,
            stack: error.stack,
            name: error.name
        });
        showNotification('❌ Lỗi khi gửi tin nhắn: ' + (error.message || 'Unknown error'));
    }
}


// Insert text to chat input
function insertTextToChatInput(text) {
    const input = document.getElementById('chatInput');
    const currentText = input.value;
    input.value = currentText ? `${currentText}\n\n${text}` : text;
    input.focus();
    autoResize(input);
}

// Set chat input for asking AI
function setChatInputForAskAI(text) {
    const input = document.getElementById('chatInput');
    input.value = `Giải thích: ${text}`;
    input.focus();
    autoResize(input);
}

// Save OCR snippet to Notion
async function saveOcrSnippetToNotion(text) {
    // Set the selected text for Notion (reuse existing global variable)
    selectedTextForNotion = text;

    // Open the Notion modal (reuse existing modal logic)
    const modal = document.getElementById('notionAddModal');
    const preview = document.getElementById('notionPreviewContent');

    if (!modal || !preview) {
        showNotification('❌ Lỗi: Không tìm thấy modal Notion');
        return;
    }

    // Show preview
    preview.textContent = text.substring(0, 500) + (text.length > 500 ? '...' : '');

    // Load pages/parents
    loadNotionPages();
    loadNotionParents();

    // Show modal
    modal.classList.add('active');
}

// Show notification
function showNotification(message) {
    const notif = document.createElement('div');
    notif.textContent = message;
    notif.style.cssText = `
        position: fixed; bottom: 2rem; right: 2rem;
        background: var(--bg-secondary); color: var(--text-primary);
        padding: 1rem 1.5rem; border-radius: 8px;
        border: 1px solid var(--border-color); box-shadow: var(--shadow-lg);
        z-index: 1002; animation: slideUp 0.3s ease;
    `;

    document.body.appendChild(notif);

    setTimeout(() => {
        notif.style.opacity = '0';
        notif.style.transform = 'translateY(10px)';
        notif.style.transition = 'all 0.3s ease';
        setTimeout(() => notif.remove(), 300);
    }, 3000);
}

// Initialize OCR sidebar event listeners
function initOcrSidebar() {
    // Close sidebar button
    document.getElementById('ocrSidebarCloseBtn').addEventListener('click', closeOcrSidebar);

    // Toolbar buttons
    document.getElementById('copyAllBtn').addEventListener('click', () => {
        const doc = ocrDocuments[currentOcrId];
        if (doc) {
            navigator.clipboard.writeText(doc.text);
            showNotification('✅ Đã copy toàn bộ văn bản');
        }
    });

    document.getElementById('insertAllBtn').addEventListener('click', () => {
        const doc = ocrDocuments[currentOcrId];
        if (doc) {
            insertTextToChatInput(doc.text);
        }
    });

    document.getElementById('saveNotionBtn').addEventListener('click', () => {
        const doc = ocrDocuments[currentOcrId];
        if (doc) {
            saveOcrSnippetToNotion(doc.text);
        }
    });

    // Text selection context menu
    const textContainer = document.getElementById('ocrTextContainer');
    textContainer.addEventListener('contextmenu', showContextMenu);
    textContainer.addEventListener('mouseup', showContextMenu);

    // Intercept copy event to provide plain text instead of HTML
    textContainer.addEventListener('copy', (e) => {
        const selection = window.getSelection();
        const selectedText = selection.toString();

        if (selectedText) {
            e.preventDefault();
            e.clipboardData.setData('text/plain', selectedText);
            console.log('Copied plain text:', selectedText.substring(0, 50) + '...');
        }
    });

    // Context menu item clicks
    const contextMenu = document.getElementById('ocrContextMenu');
    contextMenu.addEventListener('click', onSelectionMenuClick);

    // Hide context menu on click outside
    document.addEventListener('click', (e) => {
        if (!contextMenu.contains(e.target)) {
            contextMenu.classList.add('hidden');
        }
    });

    // OCR link clicks in chat (event delegation)
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('ocr-link')) {
            const ocrId = e.target.dataset.ocrId;
            if (ocrId) {
                openOcrSidebar(ocrId);
            }
        }
    });
}


// =================== Rendering ===================
function renderMessages() {
    const container = document.getElementById('chatMessages');
    if (!container) {
        console.error('chatMessages container not found');
        return;
    }

    console.log(`Rendering ${messages.length} messages`);
    container.innerHTML = '';

    if (messages.length === 0) {
        // Show empty state
        const emptyMsg = document.createElement('div');
        emptyMsg.className = 'empty-state';
        emptyMsg.style.textAlign = 'center';
        emptyMsg.style.padding = '3rem 2rem';
        emptyMsg.style.color = 'var(--text-tertiary)';
        emptyMsg.innerHTML = `
            <div style="font-size: 1.1rem; margin-bottom: 0.5rem; color: var(--text-secondary);">Bắt đầu học toán cùng tôi</div>
            <div style="font-size: 0.9rem;">Hãy đặt câu hỏi về toán học, tôi sẽ giúp bạn giải quyết và học tập hiệu quả hơn!</div>
        `;
        container.appendChild(emptyMsg);
        return;
    }

    messages.forEach((msg, index) => {
        console.log(`Rendering message ${index + 1}/${messages.length}:`, msg.role, msg.content.substring(0, 50));
        renderMessage(msg);
    });
    scrollToBottom();
}

function renderMessage(message) {
    const container = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${message.role}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = message.role === 'user' ? 'U' : 'A';

    const content = document.createElement('div');
    content.className = 'message-content';

    const text = document.createElement('div');
    text.className = 'message-text';

    let processedHtml = processContent(message.content);

    // For user messages, strip inline styles and problematic classes to ensure consistent styling
    // This fixes issues where OCR content pasted into chat breaks the layout
    if (message.role === 'user') {
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = processedHtml;

        const allElements = tempDiv.querySelectorAll('*');
        allElements.forEach(el => {
            // Remove inline styles (Critical)
            el.removeAttribute('style');

            // Remove legacy presentational attributes
            ['color', 'face', 'size', 'bgcolor', 'align', 'width', 'height', 'border', 'cellpadding', 'cellspacing'].forEach(attr => el.removeAttribute(attr));

            // Remove classes, but preserve KaTeX/LaTeX classes
            if (el.className) {
                const classes = el.className.split(/\s+/);
                const keptClasses = classes.filter(c =>
                    c.startsWith('katex') ||
                    c === 'latex-display-block' ||
                    c === 'latex-inline-block' ||
                    c === 'message-text' // potential self class
                );

                if (keptClasses.length > 0) {
                    el.className = keptClasses.join(' ');
                } else {
                    el.removeAttribute('class');
                }
            }
        });

        processedHtml = tempDiv.innerHTML;
    }

    text.innerHTML = processedHtml;

    // Make text selectable and track selection
    text.addEventListener('mouseup', handleTextSelection);

    const timestamp = document.createElement('div');
    timestamp.className = 'message-timestamp';
    const time = new Date(message.timestamp).toLocaleTimeString('vi-VN', {
        hour: '2-digit',
        minute: '2-digit'
    });
    timestamp.textContent = time;
    if (message.responseTime) {
        const timeSpan = document.createElement('span');
        timeSpan.textContent = `• ${message.responseTime}s`;
        timeSpan.style.color = 'var(--text-tertiary)';
        timestamp.appendChild(timeSpan);
    }

    content.appendChild(text);
    content.appendChild(timestamp);

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);

    container.appendChild(messageDiv);

    // Debug: Check if LaTeX blocks exist in DOM before rendering
    const displayBlocksBefore = text.querySelectorAll('.latex-display-block');
    const inlineBlocksBefore = text.querySelectorAll('.latex-inline-block');
    console.log(`DOM check - Display blocks: ${displayBlocksBefore.length}, Inline blocks: ${inlineBlocksBefore.length}`);

    if (displayBlocksBefore.length > 0 || inlineBlocksBefore.length > 0) {
        console.log('LaTeX blocks found in DOM, starting render...');
    }

    // Render LaTeX
    renderLaTeX(text);

    scrollToBottom();
}

function processContent(content) {
    // Debug: Log content before processing
    console.log('='.repeat(80));
    console.log('Processing content, length:', content.length);
    console.log('Contains $$:', content.includes('$$'));
    console.log('Contains $:', content.match(/\$[^$]+\$/g)?.length || 0);

    // Check for backslash patterns - need to check actual character codes
    const hasBackslashBracket = content.includes('\\[') || content.includes('\\]');
    const hasBackslashParen = content.includes('\\(') || content.includes('\\)');
    console.log('Contains \\[:', hasBackslashBracket);
    console.log('Contains \\(:', hasBackslashParen);

    // Try to find LaTeX patterns manually
    const testPattern1 = /\\\[/g;
    const testPattern2 = /\\\(/g;
    const matches1 = content.match(testPattern1);
    const matches2 = content.match(testPattern2);
    console.log('Matches for \\[:', matches1?.length || 0, matches1?.slice(0, 3));
    console.log('Matches for \\(:', matches2?.length || 0, matches2?.slice(0, 3));

    // Show sample of content
    const sampleStart = content.indexOf('\\[');
    if (sampleStart >= 0) {
        console.log('Sample around \\[:', content.substring(Math.max(0, sampleStart - 20), sampleStart + 100));
    }
    console.log('='.repeat(80));

    // Process Markdown and LaTeX
    const latexBlocks = [];
    let processed = content;
    let blockIndex = 0;

    // Extract LaTeX blocks - Use a simpler, more reliable approach
    // Collect all matches first, then replace in reverse order to preserve indices

    // Helper function to clean LaTeX content (remove trailing period)
    function cleanLatexContent(content) {
        let cleaned = content.trim();
        // Remove trailing period if it exists (common issue with LLM output)
        if (cleaned.endsWith('.')) {
            cleaned = cleaned.slice(0, -1).trim();
        }
        return cleaned;
    }

    // Helper function to find all matches and collect them
    function findAllMatches(text, pattern) {
        const matches = [];
        let match;
        const regex = new RegExp(pattern, 'g');
        while ((match = regex.exec(text)) !== null) {
            matches.push({
                fullMatch: match[0],
                content: match[1] || match[0],
                index: match.index,
                length: match[0].length
            });
        }
        return matches;
    }

    // 1. Find all \[...\] (display math with backslashes) - MUST be first
    // Pattern: In string '\\\\\\[' means \\\[ in regex, which matches \[ in text
    const displayMatches1 = findAllMatches(processed, '\\\\\\[([\\s\\S]*?)\\\\\\]');
    console.log(`Searching for \\[...\\] patterns in text of length ${processed.length}`);
    console.log(`Found ${displayMatches1.length} \\[...\\] patterns`);
    for (const match of displayMatches1.reverse()) { // Reverse to replace from end
        const placeholder = `__LATEX_DISPLAY_${blockIndex}__`;
        const cleanedContent = cleanLatexContent(match.content);
        latexBlocks.push({ type: 'display', content: cleanedContent, placeholder });
        processed = processed.substring(0, match.index) + placeholder + processed.substring(match.index + match.length);
        console.log(`Found display LaTeX block [${blockIndex}]:`, cleanedContent.substring(0, 50));
        blockIndex++;
    }

    // 2. Find all $$...$$ (display math with dollar signs)
    const displayMatches2 = findAllMatches(processed, '\\$\\$([\\s\\S]*?)\\$\\$');
    console.log(`Found ${displayMatches2.length} $$...$$ patterns`);
    for (const match of displayMatches2.reverse()) {
        const placeholder = `__LATEX_DISPLAY_${blockIndex}__`;
        const cleanedContent = cleanLatexContent(match.content);
        latexBlocks.push({ type: 'display', content: cleanedContent, placeholder });
        processed = processed.substring(0, match.index) + placeholder + processed.substring(match.index + match.length);
        console.log(`Found display LaTeX block $${blockIndex}:`, cleanedContent.substring(0, 50));
        blockIndex++;
    }

    // 3. Find all \(...\) (inline math with backslashes)
    const inlineMatches1 = findAllMatches(processed, '\\\\\\(([\\s\\S]*?)\\\\\\)');
    console.log(`Found ${inlineMatches1.length} \\(...\\) patterns`);
    for (const match of inlineMatches1.reverse()) {
        const placeholder = `__LATEX_INLINE_${blockIndex}__`;
        const cleanedContent = cleanLatexContent(match.content);
        latexBlocks.push({ type: 'inline', content: cleanedContent, placeholder });
        processed = processed.substring(0, match.index) + placeholder + processed.substring(match.index + match.length);
        console.log(`Found inline LaTeX block (${blockIndex}):`, cleanedContent.substring(0, 50));
        blockIndex++;
    }

    // 4. Find all $...$ (inline math with dollar signs) - must be last
    const inlineMatches2 = findAllMatches(processed, '\\$([^$\\n]+?)\\$');
    console.log(`Found ${inlineMatches2.length} $...$ patterns`);
    for (const match of inlineMatches2.reverse()) {
        const placeholder = `__LATEX_INLINE_${blockIndex}__`;
        const cleanedContent = cleanLatexContent(match.content);
        latexBlocks.push({ type: 'inline', content: cleanedContent, placeholder });
        processed = processed.substring(0, match.index) + placeholder + processed.substring(match.index + match.length);
        console.log(`Found inline LaTeX block $${blockIndex}:`, cleanedContent.substring(0, 50));
        blockIndex++;
    }

    // If no matches found, try manual extraction
    if (latexBlocks.length === 0) {
        console.log('No LaTeX found with regex, trying manual extraction...');

        // Manual search for \[...\]
        let idx = 0;
        while (idx < processed.length) {
            const bsIdx = processed.indexOf('\\', idx);
            if (bsIdx < 0) break;

            if (bsIdx + 1 < processed.length && processed[bsIdx + 1] === '[') {
                const endIdx = processed.indexOf('\\]', bsIdx + 2);
                if (endIdx > bsIdx) {
                    const mathContent = cleanLatexContent(processed.substring(bsIdx + 2, endIdx));
                    const placeholder = `__LATEX_DISPLAY_${blockIndex}__`;
                    latexBlocks.push({ type: 'display', content: mathContent, placeholder });
                    processed = processed.substring(0, bsIdx) + placeholder + processed.substring(endIdx + 2);
                    console.log(`Manual: Found display LaTeX block [${blockIndex}]:`, mathContent.substring(0, 50));
                    blockIndex++;
                    idx = bsIdx + placeholder.length;
                    continue;
                }
            }

            if (bsIdx + 1 < processed.length && processed[bsIdx + 1] === '(') {
                const endIdx = processed.indexOf('\\)', bsIdx + 2);
                if (endIdx > bsIdx) {
                    const mathContent = cleanLatexContent(processed.substring(bsIdx + 2, endIdx));
                    const placeholder = `__LATEX_INLINE_${blockIndex}__`;
                    latexBlocks.push({ type: 'inline', content: mathContent, placeholder });
                    processed = processed.substring(0, bsIdx) + placeholder + processed.substring(endIdx + 2);
                    console.log(`Manual: Found inline LaTeX block (${blockIndex}):`, mathContent.substring(0, 50));
                    blockIndex++;
                    idx = bsIdx + placeholder.length;
                    continue;
                }
            }

            idx = bsIdx + 1;
        }
    }

    // Debug: Check if we found any LaTeX
    if (latexBlocks.length === 0) {
        console.warn('No LaTeX blocks found! Checking content...');
        console.log('Content sample:', content.substring(0, 200));
        // Try to find any backslash patterns
        const hasBackslashBracket = content.includes('\\[') || content.includes('\\]');
        const hasBackslashParen = content.includes('\\(') || content.includes('\\)');
        console.log('Has \\[:', hasBackslashBracket, 'Has \\(:', hasBackslashParen);

        // Try alternative search - maybe backslashes are escaped differently
        const altPattern1 = content.match(/\\\\\[/g);
        const altPattern2 = content.match(/\\\\\(/g);
        console.log('Alternative patterns - \\\\[:', altPattern1?.length || 0);
        console.log('Alternative patterns - \\\\(:', altPattern2?.length || 0);

        // Show character codes around potential LaTeX
        const testIdx = content.indexOf('[');
        if (testIdx > 0) {
            const before = content.charCodeAt(testIdx - 1);
            console.log(`Character before [: ${before} (${String.fromCharCode(before)})`);
        }
    }

    // Processed already has placeholders, now we need to replace them after Markdown
    // The placeholders are already in the format __LATEX_TYPE_INDEX__

    console.log(`Total LaTeX blocks extracted: ${latexBlocks.length}`);
    if (latexBlocks.length > 0) {
        console.log('LaTeX blocks:', latexBlocks.map(b => ({ type: b.type, placeholder: b.placeholder, preview: b.content.substring(0, 30) })));
    }

    // Create a mapping of placeholders to their HTML elements
    // Replace placeholders with HTML elements BEFORE Markdown processing
    // This ensures Markdown won't interfere with them
    const placeholderMap = new Map();

    for (const block of latexBlocks) {
        // Store raw LaTeX content - escape for HTML attribute but keep raw for rendering
        const rawContent = block.content;
        // Escape for HTML attribute: only escape quotes and ampersands, preserve backslashes
        const escapedForAttr = rawContent
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Create HTML element - use a unique marker that Markdown won't touch
        const htmlElement = block.type === 'display'
            ? `<div class="latex-display-block" data-latex="${escapedForAttr}"></div>`
            : `<span class="latex-inline-block" data-latex="${escapedForAttr}"></span>`;

        placeholderMap.set(block.placeholder, htmlElement);
    }

    // Replace all placeholders at once
    for (const [placeholder, htmlElement] of placeholderMap) {
        // Check if placeholder exists in text
        if (processed.includes(placeholder)) {
            processed = processed.split(placeholder).join(htmlElement);
            console.log(`Replaced ${placeholder} with ${latexBlocks.find(b => b.placeholder === placeholder)?.type} element`);
        } else {
            console.warn(`Placeholder ${placeholder} not found in text!`);
        }
    }

    console.log(`Replaced ${latexBlocks.length} LaTeX placeholders with HTML elements (before Markdown)`);

    // Debug: Check placeholders before Markdown
    const remainingPlaceholders = processed.match(/__LATEX_[A-Z]+_\d+__/g);
    if (remainingPlaceholders && remainingPlaceholders.length > 0) {
        console.warn(`Found ${remainingPlaceholders.length} remaining placeholders after replace:`, remainingPlaceholders);
    }

    // Render Markdown
    if (typeof marked !== 'undefined') {
        try {
            marked.setOptions({
                breaks: true,
                gfm: true,
                headerIds: false,
                mangle: false
            });
            processed = marked.parse(processed);
            console.log('Markdown parsed');
        } catch (e) {
            console.warn('Markdown parsing error:', e);
            processed = escapeHtml(processed).replace(/\n/g, '<br>');
        }
    } else {
        processed = escapeHtml(processed).replace(/\n/g, '<br>');
    }

    // Debug: Check if LaTeX blocks are in the final HTML
    const finalDisplayCount = (processed.match(/latex-display-block/g) || []).length;
    const finalInlineCount = (processed.match(/latex-inline-block/g) || []).length;
    console.log(`Final HTML contains: ${finalDisplayCount} display blocks, ${finalInlineCount} inline blocks`);

    if (latexBlocks.length > 0 && (finalDisplayCount === 0 && finalInlineCount === 0)) {
        console.error('ERROR: LaTeX blocks were extracted but not found in final HTML!');
        console.log('Sample of processed HTML:', processed.substring(0, 500));
        console.log('Placeholders that should be replaced:', latexBlocks.map(b => b.placeholder));
        // Show what Markdown did to the content
        console.log('Sample after Markdown:', processed.substring(0, 500));
    }

    return processed;
}

function renderLaTeX(element) {
    // Wait for KaTeX to be available
    if (typeof katex === 'undefined') {
        console.warn('KaTeX not loaded yet, retrying...');
        setTimeout(() => renderLaTeX(element), 100);
        return;
    }

    console.log('Starting LaTeX rendering, KaTeX available:', typeof katex !== 'undefined');

    try {
        const displayBlocks = element.querySelectorAll('.latex-display-block');
        const inlineBlocks = element.querySelectorAll('.latex-inline-block');

        console.log(`Rendering LaTeX: ${displayBlocks.length} display blocks, ${inlineBlocks.length} inline blocks`);

        // Render display math blocks
        displayBlocks.forEach((block, index) => {
            // Get LaTeX from data attribute (required)
            let mathContent = block.getAttribute('data-latex');

            if (!mathContent) {
                // Fallback to textContent if data-latex not available
                mathContent = block.textContent.trim();
                // Remove $$ delimiters if present
                mathContent = mathContent.replace(/^\$\$|\$\$$/g, '').trim();
            }

            if (!mathContent) {
                console.warn(`Display block ${index} has no LaTeX content`);
                return;
            }

            console.log(`Rendering display block ${index}:`, mathContent.substring(0, 50));

            try {
                // Use katex.renderToString for better control
                const rendered = katex.renderToString(mathContent, {
                    displayMode: true,
                    throwOnError: false,
                    strict: false
                });
                block.innerHTML = rendered;
                block.classList.add('katex-display');
                console.log(`Successfully rendered display block ${index}`);
            } catch (e) {
                console.error(`Error rendering display math ${index}:`, e);
                console.error(`   LaTeX content:`, mathContent.substring(0, 100));
                block.innerHTML = `<span style="color: red;">[LaTeX Error: ${mathContent.substring(0, 30)}...]</span>`;
            }
        });

        // Render inline math blocks
        inlineBlocks.forEach((block, index) => {
            // Get LaTeX from data attribute (required)
            let mathContent = block.getAttribute('data-latex');

            if (!mathContent) {
                // Fallback to textContent if data-latex not available
                mathContent = block.textContent.trim();
                // Remove $ delimiters if present
                mathContent = mathContent.replace(/^\$|\$$/g, '').trim();
            }

            if (!mathContent) {
                console.warn(`Inline block ${index} has no LaTeX content`);
                return;
            }

            console.log(`Rendering inline block ${index}:`, mathContent.substring(0, 50));

            try {
                // Use katex.renderToString for better control
                const rendered = katex.renderToString(mathContent, {
                    displayMode: false,
                    throwOnError: false,
                    strict: false
                });
                block.innerHTML = rendered;
                console.log(`Successfully rendered inline block ${index}`);
            } catch (e) {
                console.error(`Error rendering inline math ${index}:`, e);
                console.error(`   LaTeX content:`, mathContent.substring(0, 100));
                block.innerHTML = `<span style="color: red;">[LaTeX Error: ${mathContent.substring(0, 30)}...]</span>`;
            }
        });

        if (displayBlocks.length > 0 || inlineBlocks.length > 0) {
            console.log('LaTeX rendering completed');
        }
    } catch (e) {
        console.error('LaTeX rendering error:', e);
    }
}

// =================== Thinking Indicator ===================
let thinkingCounter = 0;

const ThinkingIcons = {
    SPINNER: `<svg class="thinking-icon-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>`,
    CHECK: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
    ERROR: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
    ANALYSIS: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>`,
    ROUTING: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/><line x1="4" y1="4" x2="9" y2="9"/></svg>`,
    MATH: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"/><line x1="8" y1="6" x2="16" y2="6"/><line x1="16" y1="14" x2="16" y2="18"/><path d="M16 10h.01"/><path d="M12 10h.01"/><path d="M8 10h.01"/><path d="M12 14h.01"/><path d="M8 14h.01"/><path d="M12 18h.01"/><path d="M8 18h.01"/></svg>`,
    RESEARCH: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>`,
    OCR: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/></svg>`,
    FORMAT: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg>`,
    DEFAULT: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`
};

function showThinkingIndicator(initialText = 'Đang suy nghĩ...') {
    const container = document.getElementById('chatMessages');
    const thinkingId = `thinking-${thinkingCounter++}`;

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant thinking-message';
    messageDiv.id = thinkingId;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = 'A';

    const content = document.createElement('div');
    content.className = 'message-content';

    // Create new structure
    const thinkingContainer = document.createElement('div');
    thinkingContainer.className = 'thinking-container expanded'; // Expanded by default

    thinkingContainer.innerHTML = `
        <div class="thinking-header" onclick="toggleThinking('${thinkingId}')">
            <div class="thinking-title">
                ${ThinkingIcons.SPINNER}
                <span class="thinking-status">${initialText}</span>
            </div>
            <div class="thinking-toggle expanded">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M6 9l6 6 6-6"/>
                </svg>
            </div>
        </div>
        <div class="thinking-content" id="${thinkingId}-content">
            <!-- Steps will be added here -->
        </div>
    `;

    content.appendChild(thinkingContainer);
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);
    container.appendChild(messageDiv);

    // No need for local event listener with delegation
    scrollToBottom();
    return thinkingId;
}

function updateThinkingComplete(thinkingId, isError = false) {
    const container = document.querySelector(`#${thinkingId} .thinking-container`);
    if (!container) return;

    const icon = container.querySelector('.thinking-icon-spin');
    const status = container.querySelector('.thinking-status');
    const content = container.querySelector('.thinking-content');
    const toggle = container.querySelector('.thinking-toggle');

    // Collapse by default when done
    container.classList.remove('expanded');
    if (toggle) toggle.classList.remove('expanded');

    if (icon) {
        icon.classList.remove('thinking-icon-spin');
        icon.innerHTML = isError ? ThinkingIcons.ERROR : ThinkingIcons.CHECK;
        // Adjust style for static icon if needed
        icon.style.display = 'flex';
    }

    if (status) {
        status.textContent = isError ? 'Đã xảy ra lỗi' : 'Đã suy nghĩ xong';
    }
}

async function replayThinkingTrace(thinkingId, trace) {
    const contentBox = document.getElementById(`${thinkingId}-content`);
    const statusText = document.querySelector(`#${thinkingId} .thinking-status`);
    if (!contentBox) return;

    // Clear initial content if any
    contentBox.innerHTML = '';

    for (const log of trace) {
        const stepDiv = document.createElement('div');
        stepDiv.className = 'thinking-step';

        // Icon based on step type
        let icon = ThinkingIcons.DEFAULT;
        if (log.step.includes('analysis')) icon = ThinkingIcons.ANALYSIS;
        else if (log.step.includes('routing')) icon = ThinkingIcons.ROUTING;
        else if (log.step.includes('math')) icon = ThinkingIcons.MATH;
        else if (log.step.includes('research')) icon = ThinkingIcons.RESEARCH;
        else if (log.step.includes('ocr')) icon = ThinkingIcons.OCR;
        else if (log.step.includes('formatting')) icon = ThinkingIcons.FORMAT;
        else if (log.step.includes('done')) icon = ThinkingIcons.CHECK;

        stepDiv.innerHTML = `
            <span class="thinking-step-icon">${icon}</span>
            <span class="thinking-step-text">${log.message}</span>
            <span class="thinking-step-time">${new Date(log.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
        `;

        contentBox.appendChild(stepDiv);

        // Update header status
        if (statusText) statusText.textContent = log.message;

        // Auto scroll
        contentBox.scrollTop = contentBox.scrollHeight;

        // Fake delay for "Replay" effect
        await new Promise(r => setTimeout(r, 600)); // 600ms per step
    }

    // Keep expanded for a moment before completing
    await new Promise(r => setTimeout(r, 500));
}

function removeThinkingIndicator(thinkingId) {
    // Legacy support or error cleanup
    const element = document.getElementById(thinkingId);
    if (element) element.remove();
}

// Global event delegation for Thinking UI (Backup for onclick)
document.addEventListener('click', function (e) {
    // Only handle if it's a thinking header and NOT handled by inline onclick
    // We can detect this if we want, but letting both run is mostly harmless provided we check state
    const header = e.target.closest('.thinking-header');
    if (header && !header.hasAttribute('onclick')) {
        const container = header.closest('.thinking-container');
        if (container) {
            container.classList.toggle('expanded');
            const toggle = header.querySelector('.thinking-toggle');
            if (toggle) toggle.classList.toggle('expanded');
        }
    }
});

function toggleThinking(thinkingId) {
    console.log('toggleThinking called for:', thinkingId);

    // Try getting container directly by querying children of the ID
    // valid selector for: id="thinking-0" -> #thinking-0 .thinking-container
    let container = document.querySelector(`#${thinkingId} .thinking-container`);
    let toggle = document.querySelector(`#${thinkingId} .thinking-toggle`);

    // Fallback: If passed ID is actually the container ID or unrelated
    if (!container) {
        const element = document.getElementById(thinkingId);
        if (element) container = element.querySelector('.thinking-container');
    }

    if (container) {
        console.log('Container found, toggling...', container.classList.contains('expanded'));
        container.classList.toggle('expanded');

        // Also toggle content directly for redundancy
        const content = container.querySelector('.thinking-content');
        if (content) {
            content.classList.toggle('expanded');
            console.log('Content class toggled:', content.classList.contains('expanded'));
        }

        if (toggle) {
            toggle.classList.toggle('expanded');
        } else {
            // Try defining toggle relative to container if not found via ID
            toggle = container.querySelector('.thinking-toggle');
            if (toggle) toggle.classList.toggle('expanded');
        }
    } else {
        console.error('FAILED to find thinking container for ID:', thinkingId);
    }
}

// Make toggleThinking available globally
window.toggleThinking = toggleThinking;

// =================== Inline Actions ===================
// Context menu replaced with inline actions (star, rename, delete)

function toggleStar(chatId) {
    const chat = chatHistory.find(c => c.id === chatId);
    if (chat) {
        chat.starred = !chat.starred;
        saveChatHistory();
        renderChatHistory();
    }
}

function startRename(chatId) {
    const chat = chatHistory.find(c => c.id === chatId);
    if (!chat) return;

    const item = document.querySelector(`.history-item-title[data-chat-id="${chatId}"]`);
    if (!item) return;

    const originalTitle = chat.title || 'New Chat';
    item.contentEditable = 'true';
    item.focus();

    // Select all text
    const range = document.createRange();
    range.selectNodeContents(item);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);

    // Handle save on Enter or blur
    const saveRename = () => {
        const newTitle = item.textContent.trim();
        if (newTitle && newTitle !== originalTitle) {
            chat.title = newTitle;
            saveChatHistory();
        }
        item.contentEditable = 'false';
        renderChatHistory();
    };

    const cancelRename = () => {
        item.textContent = originalTitle;
        item.contentEditable = 'false';
    };

    item.addEventListener('blur', saveRename, { once: true });
    item.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            item.blur();
        } else if (e.key === 'Escape') {
            e.preventDefault();
            cancelRename();
        }
    }, { once: true });
}

let currentDeleteChatId = null;

function showDeleteConfirm(chatId) {
    currentDeleteChatId = chatId;
    const modal = document.getElementById('deleteConfirmModal');
    if (modal) {
        modal.classList.add('active');
    }
}

function cancelDelete(chatId) {
    currentDeleteChatId = null;
    const modal = document.getElementById('deleteConfirmModal');
    if (modal) {
        modal.classList.remove('active');
    }
}

function confirmDelete(chatId) {
    // Remove from history
    chatHistory = chatHistory.filter(c => c.id !== chatId);
    saveChatHistory();

    // Clear messages if this is the current chat
    if (currentChatId === chatId) {
        currentChatId = null;
        localStorage.removeItem('currentChatId');
        messages = [];
        renderMessages();
    }

    // Remove from localStorage
    localStorage.removeItem(`messages_${chatId}`);

    // Close modal
    cancelDelete(chatId);

    renderChatHistory();
}

// Make functions available globally
window.toggleStar = toggleStar;
window.startRename = startRename;
window.showDeleteConfirm = showDeleteConfirm;
window.cancelDelete = cancelDelete;
window.confirmDelete = confirmDelete;

// =================== Utilities ===================
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function scrollToBottom() {
    const container = document.getElementById('chatContainer');
    container.scrollTop = container.scrollHeight;
}

function saveMessages() {
    // Persist messages to localStorage - permanent storage, never auto-deleted
    if (currentChatId) {
        try {
            localStorage.setItem(`messages_${currentChatId}`, JSON.stringify(messages));
            // Also save OCR documents for this session
            localStorage.setItem(`ocrDocs_${currentChatId}`, JSON.stringify(ocrDocuments));
            console.log(`Saved ${messages.length} messages and ${Object.keys(ocrDocuments).length} OCR docs for chat ${currentChatId}`);
        } catch (error) {
            console.error('Error saving messages:', error);
            if (error.name === 'QuotaExceededError') {
                alert('Lưu trữ đầy. Vui lòng xóa một số chat cũ hoặc dữ liệu khác.');
            }
        }
    }
}

// =================== MCP Functions ===================
let allPages = []; // Store all loaded pages for filtering

const MCP = {
    async listResources() {
        const response = await fetch('/api/mcp/list-resources');
        const data = await response.json();
        if (!response.ok || !data.success) {
            // Check if it's an API key error
            if (data.error && data.error.includes('not configured') || data.error.includes('connect Notion')) {
                throw new Error('NOTION_NOT_CONNECTED');
            }
            throw new Error(data.error || 'Failed to list resources');
        }
        return data;
    },

    async readResource(uri) {
        const response = await fetch('/api/mcp/read-resource', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ uri })
        });
        if (!response.ok) throw new Error('Failed to read resource');
        return await response.json();
    }
};

// MCP Tools List Modal Management
function openMCPToolsModal() {
    const modal = document.getElementById('mcpToolsModal');
    if (modal) {
        modal.classList.add('active');
        updateNotionToolStatus();
    }
}

function closeMCPToolsModal() {
    const modal = document.getElementById('mcpToolsModal');
    if (modal) {
        modal.classList.remove('active');
    }
}

function updateNotionToolStatus() {
    const notionKey = localStorage.getItem('notionApiKey') || '';
    const statusEl = document.getElementById('notionToolStatus');
    const toolItem = document.getElementById('mcpToolNotion');

    if (statusEl) {
        if (notionKey && notionKey.trim()) {
            statusEl.textContent = 'Đã kết nối';
            statusEl.style.color = 'var(--accent-color)';
            if (toolItem) toolItem.classList.add('connected');
        } else {
            statusEl.textContent = 'Chưa kết nối';
            statusEl.style.color = 'var(--text-tertiary)';
            if (toolItem) toolItem.classList.remove('connected');
        }
    }
}

// MCP Modal Management (Notion Pages)
function openMCPModal() {
    const modal = document.getElementById('mcpModal');
    if (modal) {
        modal.classList.add('active');
    }
}

function closeMCPModal() {
    const modal = document.getElementById('mcpModal');
    if (modal) {
        modal.classList.remove('active');
    }
}

function openPageContentModal(title, content) {
    const modal = document.getElementById('pageContentModal');
    const titleEl = document.getElementById('pageContentTitle');
    const bodyEl = document.getElementById('pageContentBody');
    const addAllBtn = document.getElementById('addAllBtn');
    const addSelectedBtn = document.getElementById('addSelectedBtn');

    if (modal && titleEl && bodyEl) {
        titleEl.textContent = title || 'Page Content';

        // Store original content for later use
        modal.dataset.pageContent = content;
        modal.dataset.pageTitle = title || 'Page Content';

        console.log('Opening page modal:', {
            title,
            contentLength: content?.length || 0,
            contentType: typeof content
        });

        // Check if content exists
        if (!content || !content.trim()) {
            bodyEl.innerHTML = '<div style="color: var(--text-tertiary); padding: 2rem; text-align: center;">Không có nội dung</div>';
            if (addAllBtn) addAllBtn.style.display = 'none';
            modal.classList.add('active');
            return;
        }

        // Format content nicely - split into paragraphs
        // Handle both \n\n and single \n
        const lines = content.split('\n');
        const paragraphs = [];
        let currentParagraph = [];

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            if (line) {
                currentParagraph.push(line);
            } else {
                if (currentParagraph.length > 0) {
                    paragraphs.push(currentParagraph.join(' '));
                    currentParagraph = [];
                }
            }
        }

        if (currentParagraph.length > 0) {
            paragraphs.push(currentParagraph.join(' '));
        }

        // If no paragraphs found, use original content
        if (paragraphs.length === 0) {
            paragraphs.push(content.trim());
        }

        let formattedHTML = '<div class="mcp-page-content">';

        paragraphs.forEach(paragraph => {
            if (paragraph.trim()) {
                // Check if paragraph is a title (all caps, starts with #, or is very short and uppercase)
                const isTitle = paragraph.match(/^#{1,6}\s/) ||
                    (paragraph.length < 100 && paragraph.match(/^[A-Z\s]{5,}$/)) ||
                    paragraph.match(/^[A-Z][a-z]*:?\s*$/);

                if (isTitle) {
                    formattedHTML += `<div class="mcp-content-paragraph mcp-content-title">${escapeHtml(paragraph.trim())}</div>`;
                } else {
                    formattedHTML += `<div class="mcp-content-paragraph">${escapeHtml(paragraph.trim())}</div>`;
                }
            }
        });

        formattedHTML += '</div>';
        bodyEl.innerHTML = formattedHTML;

        console.log('Formatted content with', paragraphs.length, 'paragraphs');

        // Set up event listeners for buttons
        if (addAllBtn) {
            addAllBtn.onclick = () => addContentToChat(content, title);
        }

        // Handle text selection
        const contentDiv = bodyEl.querySelector('.mcp-page-content');
        if (contentDiv) {
            const checkSelection = () => {
                setTimeout(() => {
                    const selection = window.getSelection();
                    const selectedText = selection.toString().trim();

                    if (selectedText.length > 0 && selection.rangeCount > 0) {
                        // Check if selection is within content div
                        const range = selection.getRangeAt(0);
                        if (contentDiv.contains(range.commonAncestorContainer) ||
                            range.commonAncestorContainer.contains(contentDiv)) {
                            // Show "Add Selected" button
                            if (addSelectedBtn) {
                                addSelectedBtn.style.display = 'inline-flex';
                                addSelectedBtn.onclick = () => {
                                    addContentToChat(selectedText, `Selected from: ${title}`);
                                    selection.removeAllRanges();
                                    addSelectedBtn.style.display = 'none';
                                };
                            }
                        }
                    } else {
                        // Hide "Add Selected" button
                        if (addSelectedBtn) {
                            addSelectedBtn.style.display = 'none';
                        }
                    }
                }, 50);
            };

            contentDiv.addEventListener('mouseup', checkSelection);
            contentDiv.addEventListener('keyup', checkSelection);

            // Hide button when clicking outside content
            document.addEventListener('click', (e) => {
                if (!contentDiv.contains(e.target)) {
                    const selection = window.getSelection();
                    if (selection.rangeCount === 0 || !contentDiv.contains(selection.getRangeAt(0).commonAncestorContainer)) {
                        if (addSelectedBtn) {
                            addSelectedBtn.style.display = 'none';
                        }
                    }
                }
            });
        }

        modal.classList.add('active');
    }
}

function addContentToChat(content, title) {
    if (!content || !content.trim()) {
        alert('Không có nội dung để thêm');
        return;
    }

    // Close the modal
    closePageContentModal();

    // Get chat input
    const chatInput = document.getElementById('chatInput');
    if (!chatInput) {
        alert('Không tìm thấy ô nhập chat');
        return;
    }

    // Add content directly without any prefix
    const contentToAdd = content.trim();

    // Add to chat input
    const currentValue = chatInput.value.trim();
    if (currentValue) {
        chatInput.value = currentValue + '\n\n' + contentToAdd;
    } else {
        chatInput.value = contentToAdd;
    }

    // Focus on input
    chatInput.focus();

    // Auto-resize textarea
    chatInput.style.height = 'auto';
    chatInput.style.height = chatInput.scrollHeight + 'px';

    // Show a brief confirmation
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: var(--accent-gradient);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        box-shadow: var(--shadow-lg);
        z-index: 10000;
        animation: fadeIn 0.3s ease;
    `;
    notification.textContent = `✓ Đã thêm vào chat!`;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 2000);
}

function closePageContentModal() {
    const modal = document.getElementById('pageContentModal');
    if (modal) {
        modal.classList.remove('active');
    }
}

// Load Pages
async function loadPages() {
    const loadingEl = document.getElementById('pagesLoading');
    const listEl = document.getElementById('pagesList');
    const emptyEl = document.getElementById('pagesEmpty');

    if (!loadingEl || !listEl) return;

    loadingEl.style.display = 'block';
    listEl.innerHTML = '';
    if (emptyEl) emptyEl.style.display = 'none';

    try {
        const result = await MCP.listResources();

        if (result.success && result.resources) {
            allPages = result.resources.filter(r => r.type === 'page');

            if (allPages.length === 0) {
                if (emptyEl) emptyEl.style.display = 'block';
            } else {
                renderPages(allPages);
            }
        } else {
            listEl.innerHTML = `<div style="color: #ef4444; padding: 1rem;">Lỗi: ${result.error || 'Lỗi không xác định'}</div>`;
        }
    } catch (error) {
        if (error.message === 'NOTION_NOT_CONNECTED') {
            // Show connection prompt
            listEl.innerHTML = `
                <div class="mcp-connection-prompt">
                    <div class="mcp-connection-icon">🔗</div>
                    <div class="mcp-connection-title">Chưa kết nối Notion</div>
                    <div class="mcp-connection-desc">Bạn cần kết nối Notion để sử dụng tính năng này. Vui lòng vào Settings > Ứng dụng & trình kết nối để kết nối.</div>
                    <button class="mcp-connection-btn" onclick="closeMCPModal(); document.getElementById('settingsModal')?.classList.add('active'); switchSettingsSection('integrations');">
                        Kết nối Notion
                    </button>
                </div>
            `;
        } else {
            listEl.innerHTML = `<div style="color: #ef4444; padding: 1rem;">Lỗi: ${error.message}</div>`;
        }
        console.error('Error loading pages:', error);
    } finally {
        loadingEl.style.display = 'none';
    }
}

// Render pages list
function renderPages(pages) {
    const listEl = document.getElementById('pagesList');
    const emptyEl = document.getElementById('pagesEmpty');

    if (!listEl) return;

    listEl.innerHTML = '';

    if (pages.length === 0) {
        if (emptyEl) emptyEl.style.display = 'block';
        return;
    }

    if (emptyEl) emptyEl.style.display = 'none';

    pages.forEach(page => {
        const item = document.createElement('div');
        item.className = 'mcp-page-item';
        item.innerHTML = `
            <div class="mcp-page-item-title">${escapeHtml(page.name)}</div>
            <div class="mcp-page-item-id">${escapeHtml(page.uri)}</div>
        `;
        item.addEventListener('click', () => loadPageContent(page.uri, page.name));
        listEl.appendChild(item);
    });
}

// Filter pages by search query
function filterPages(query) {
    if (!query || !query.trim()) {
        renderPages(allPages);
        return;
    }

    const searchTerm = query.toLowerCase().trim();
    const filtered = allPages.filter(page =>
        page.name.toLowerCase().includes(searchTerm)
    );

    renderPages(filtered);
}

// Load Page Content
async function loadPageContent(uri, title) {
    const loadingEl = document.getElementById('pagesLoading');

    if (loadingEl) loadingEl.style.display = 'block';

    try {
        console.log('Loading page content:', { uri, title });
        const result = await MCP.readResource(uri);

        console.log('Page content result:', {
            success: result.success,
            contentLength: result.content?.length || 0,
            hasContent: !!result.content,
            error: result.error
        });

        if (result.success) {
            if (result.content && result.content.trim()) {
                console.log('Opening page modal with content:', result.content.substring(0, 200));
                openPageContentModal(title, result.content);
            } else {
                alert('Nội dung trang trống');
                console.warn('Page content is empty or undefined');
            }
        } else {
            alert(`Lỗi: ${result.error || 'Không thể tải nội dung trang'}`);
            console.error('Failed to load page:', result.error);
        }
    } catch (error) {
        alert(`Lỗi: ${error.message}`);
        console.error('Error loading page content:', error);
        console.error('Error stack:', error.stack);
    } finally {
        if (loadingEl) loadingEl.style.display = 'none';
    }
}


// =================== Notion Add Functionality ===================
let selectedTextForNotion = '';
let selectedTextElement = null;

// Create floating button for adding to Notion
let notionFloatBtn = null;

function initNotionFloatButton() {
    if (!notionFloatBtn) {
        notionFloatBtn = document.createElement('button');
        notionFloatBtn.className = 'notion-add-float-btn';
        notionFloatBtn.innerHTML = '<span>Thêm vào Notion</span>';
        notionFloatBtn.onclick = openNotionAddModal;
        document.body.appendChild(notionFloatBtn);
    }
}

function isNodeInsideLaTeXBlock(node) {
    // Check if node is inside a LaTeX block
    let parent = node.parentElement;
    while (parent) {
        if (parent.classList && (parent.classList.contains('latex-display-block') || parent.classList.contains('latex-inline-block'))) {
            return true;
        }
        parent = parent.parentElement;
    }
    return false;
}

function extractLaTeXFromSelection(selection) {
    const range = selection.getRangeAt(0);
    const container = range.commonAncestorContainer;
    const parentElement = container.nodeType === Node.TEXT_NODE ? container.parentElement : container;

    // Check if selection contains LaTeX elements
    const messageElement = parentElement.closest('.message');
    if (!messageElement) return null;

    const messageText = messageElement.querySelector('.message-text');
    if (!messageText) return null;

    // Find all LaTeX blocks within or intersecting the selection
    const allDisplayBlocks = messageText.querySelectorAll('.latex-display-block');
    const allInlineBlocks = messageText.querySelectorAll('.latex-inline-block');

    let parts = [];

    // Get all nodes in the selection range
    const walker = document.createTreeWalker(
        messageText,
        NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT,
        {
            acceptNode: function (node) {
                // Skip text nodes inside LaTeX blocks (these are rendered KaTeX output)
                if (node.nodeType === Node.TEXT_NODE) {
                    if (isNodeInsideLaTeXBlock(node)) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    return range.intersectsNode(node) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
                }
                // Accept LaTeX block elements
                if (node.classList && (node.classList.contains('latex-display-block') || node.classList.contains('latex-inline-block'))) {
                    return range.intersectsNode(node) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
                }
                return NodeFilter.FILTER_SKIP;
            }
        }
    );

    // Collect all text nodes and LaTeX blocks in order
    const nodes = [];
    let node;
    while (node = walker.nextNode()) {
        nodes.push(node);
    }

    // Also check for LaTeX blocks that intersect (in case they weren't caught by walker)
    for (const block of allDisplayBlocks) {
        if (range.intersectsNode(block) && !nodes.includes(block)) {
            nodes.push(block);
        }
    }

    for (const block of allInlineBlocks) {
        if (range.intersectsNode(block) && !nodes.includes(block)) {
            nodes.push(block);
        }
    }

    // Sort nodes by their position in DOM
    nodes.sort((a, b) => {
        const pos = a.compareDocumentPosition(b);
        if (pos & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
        if (pos & Node.DOCUMENT_POSITION_PRECEDING) return 1;
        return 0;
    });

    // Build content preserving order and line structure
    // Group nodes by their line position to preserve inline LaTeX with text
    let currentLine = [];
    let lines = [];

    for (let i = 0; i < nodes.length; i++) {
        const node = nodes[i];
        const prevNode = i > 0 ? nodes[i - 1] : null;

        if (node.classList && node.classList.contains('latex-display-block')) {
            // Display LaTeX always starts a new line
            // Save current line if it has content
            if (currentLine.length > 0) {
                lines.push(currentLine.join(' ').trim());
                currentLine = [];
            }

            let latex = node.getAttribute('data-latex');

            // Fallback: if no data-latex, try to extract from rendered content
            if (!latex || latex.trim() === '') {
                const katexElement = node.querySelector('.katex-mathml annotation[encoding="application/x-tex"]');
                if (katexElement) {
                    latex = katexElement.textContent.trim();
                } else {
                    latex = node.textContent.trim();
                    latex = latex.replace(/^\$\$|\$\$$/g, '').trim();
                }
            }

            if (latex && latex.trim()) {
                // Unescape HTML entities
                latex = latex
                    .replace(/&amp;/g, '&')
                    .replace(/&quot;/g, '"')
                    .replace(/&#39;/g, "'")
                    .replace(/&lt;/g, '<')
                    .replace(/&gt;/g, '>');
                lines.push(`\`\`\`math\n${latex}\n\`\`\``);
            }
        } else if (node.classList && node.classList.contains('latex-inline-block')) {
            // Inline LaTeX stays on the same line with text
            let latex = node.getAttribute('data-latex');

            // Fallback: if no data-latex, try to extract from rendered content
            if (!latex || latex.trim() === '') {
                const katexElement = node.querySelector('.katex-mathml annotation[encoding="application/x-tex"]');
                if (katexElement) {
                    latex = katexElement.textContent.trim();
                } else {
                    latex = node.textContent.trim();
                    latex = latex.replace(/^\$|\$$/g, '').trim();
                }
            }

            if (latex && latex.trim()) {
                // Unescape HTML entities
                latex = latex
                    .replace(/&amp;/g, '&')
                    .replace(/&quot;/g, '"')
                    .replace(/&#39;/g, "'")
                    .replace(/&lt;/g, '<')
                    .replace(/&gt;/g, '>');
                currentLine.push(`$${latex}$`);
            }
        } else if (node.nodeType === Node.TEXT_NODE) {
            // Only add text nodes that are NOT inside LaTeX blocks
            if (!isNodeInsideLaTeXBlock(node)) {
                const text = node.textContent.trim();
                if (text) {
                    currentLine.push(text);
                }
            }
        }
    }

    // Add remaining line content
    if (currentLine.length > 0) {
        lines.push(currentLine.join(' ').trim());
    }

    // If we found LaTeX, return formatted content with text
    if (lines.length > 0) {
        return lines.join('\n');
    }

    return null;
}

function handleTextSelection(e) {
    // Check if Notion is connected before showing button
    const notionKey = localStorage.getItem('notionApiKey') || '';
    if (!notionKey || !notionKey.trim()) {
        // Notion not connected, don't show button
        if (notionFloatBtn) {
            notionFloatBtn.classList.remove('active');
        }
        return;
    }

    const selection = window.getSelection();
    const selectedText = selection.toString().trim();

    if (selectedText && selectedText.length > 0 && selection.rangeCount > 0) {
        // Try to extract LaTeX with text first
        const latexContent = extractLaTeXFromSelection(selection);

        if (latexContent) {
            // Use LaTeX content with text if found
            selectedTextForNotion = latexContent;
        } else {
            // Use plain text
            selectedTextForNotion = selectedText;
        }

        selectedTextElement = e.target.closest('.message');

        // Show floating button (only if Notion is connected)
        if (notionFloatBtn) {
            notionFloatBtn.classList.add('active');

            // Position button consistently near selection (always same position relative to selection)
            const range = selection.getRangeAt(0);
            const rect = range.getBoundingClientRect();

            // Get actual button dimensions after it's visible
            const buttonRect = notionFloatBtn.getBoundingClientRect();
            const buttonHeight = buttonRect.height || 32;
            const buttonWidth = buttonRect.width || 130;
            const offsetY = 8; // Distance above selection

            // Calculate position: above and centered on selection
            let top = rect.top - buttonHeight - offsetY;
            let left = rect.left + (rect.width / 2) - (buttonWidth / 2);

            // Keep button within viewport bounds
            top = Math.max(20, Math.min(top, window.innerHeight - buttonHeight - 20));
            left = Math.max(20, Math.min(left, window.innerWidth - buttonWidth - 20));

            notionFloatBtn.style.top = `${top}px`;
            notionFloatBtn.style.left = `${left}px`;
        }
    } else {
        // Hide button after a short delay to allow click
        setTimeout(() => {
            const currentSelection = window.getSelection();
            if (!currentSelection.toString().trim()) {
                if (notionFloatBtn) {
                    notionFloatBtn.classList.remove('active');
                }
                selectedTextForNotion = '';
                selectedTextElement = null;
            }
        }, 100);
    }
}

// Close floating button when clicking outside
document.addEventListener('click', (e) => {
    if (notionFloatBtn && !notionFloatBtn.contains(e.target) && !e.target.closest('.message-text')) {
        const selection = window.getSelection();
        if (!selection.toString().trim()) {
            notionFloatBtn.classList.remove('active');
        }
    }
});

function openNotionAddModal() {
    // Check if Notion is connected
    const notionKey = localStorage.getItem('notionApiKey') || '';
    if (!notionKey || !notionKey.trim()) {
        alert('Vui lòng kết nối Notion trước. Vào Settings > Ứng dụng & trình kết nối để kết nối.');
        // Open settings modal
        const settingsModal = document.getElementById('settingsModal');
        if (settingsModal) {
            settingsModal.classList.add('active');
            switchSettingsSection('integrations');
        }
        return;
    }

    if (!selectedTextForNotion) {
        alert('Vui lòng chọn nội dung cần thêm vào Notion');
        return;
    }

    const modal = document.getElementById('notionAddModal');
    const preview = document.getElementById('notionPreviewContent');

    if (!modal || !preview) return;

    // Show preview
    preview.textContent = selectedTextForNotion.substring(0, 500) + (selectedTextForNotion.length > 500 ? '...' : '');

    // Load pages/parents
    loadNotionPages();
    loadNotionParents();

    // Show modal
    modal.classList.add('active');
}

function closeNotionAddModal() {
    const modal = document.getElementById('notionAddModal');
    if (modal) {
        modal.classList.remove('active');
    }
    if (notionFloatBtn) {
        notionFloatBtn.classList.remove('active');
    }
    selectedTextForNotion = '';
    selectedTextElement = null;
}

async function loadNotionPages() {
    const select = document.getElementById('notionPageSelect');
    if (!select) return;

    select.innerHTML = '<option value="">Đang tải...</option>';

    try {
        const response = await fetch('/api/mcp/list-resources');
        const data = await response.json();

        if (data.success && data.resources) {
            select.innerHTML = '<option value="">Chọn trang...</option>';

            const pages = data.resources.filter(r => r.type === 'page');
            pages.forEach(page => {
                const option = document.createElement('option');
                option.value = page.id;
                option.textContent = page.name || page.id;
                select.appendChild(option);
            });

            if (pages.length === 0) {
                select.innerHTML = '<option value="">Không có trang nào</option>';
            }
        } else {
            select.innerHTML = '<option value="">Lỗi khi tải trang</option>';
        }
    } catch (error) {
        console.error('Error loading pages:', error);
        select.innerHTML = '<option value="">Lỗi khi tải trang</option>';
    }
}

async function loadNotionParents() {
    const select = document.getElementById('notionParentSelect');
    if (!select) return;

    select.innerHTML = '<option value="">Đang tải...</option>';

    try {
        const response = await fetch('/api/mcp/list-resources');
        const data = await response.json();

        if (data.success && data.resources) {
            select.innerHTML = '<option value="">Chọn trang cha...</option>';

            // Show both pages and databases as parents
            data.resources.forEach(resource => {
                const option = document.createElement('option');
                option.value = resource.id;
                option.textContent = `${resource.name || resource.id} (${resource.type})`;
                select.appendChild(option);
            });

            if (data.resources.length === 0) {
                select.innerHTML = '<option value="">Không có trang cha nào</option>';
            }
        } else {
            select.innerHTML = '<option value="">Lỗi khi tải trang cha</option>';
        }
    } catch (error) {
        console.error('Error loading parents:', error);
        select.innerHTML = '<option value="">Lỗi khi tải trang cha</option>';
    }
}

async function saveToNotion() {
    const actionRadio = document.querySelector('input[name="notionAction"]:checked');
    if (!actionRadio) return;

    const action = actionRadio.value;
    const content = selectedTextForNotion;

    if (!content || !content.trim()) {
        alert('Không có nội dung để thêm');
        return;
    }

    try {
        if (action === 'create') {
            const titleInput = document.getElementById('notionPageTitle');
            const parentSelect = document.getElementById('notionParentSelect');

            if (!titleInput || !parentSelect) return;

            const title = titleInput.value.trim();
            const parentId = parentSelect.value;

            if (!title) {
                alert('Vui lòng nhập tiêu đề trang');
                return;
            }

            if (!parentId) {
                alert('Vui lòng chọn trang cha');
                return;
            }

            const response = await fetch('/api/notion/create-page', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, parent_id: parentId, content })
            });

            const data = await response.json();

            if (data.success) {
                showNotification('✓ Đã tạo trang mới trong Notion!', 'success');
                closeNotionAddModal();
            } else {
                alert('Lỗi: ' + (data.error || 'Không thể tạo trang'));
            }
        } else {
            const pageSelect = document.getElementById('notionPageSelect');
            const modeRadio = document.querySelector('input[name="updateMode"]:checked');

            if (!pageSelect || !modeRadio) return;

            const pageId = pageSelect.value;
            const mode = modeRadio.value;

            if (!pageId) {
                alert('Vui lòng chọn trang cần cập nhật');
                return;
            }

            const response = await fetch('/api/notion/update-page', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ page_id: pageId, content, mode })
            });

            const data = await response.json();

            if (data.success) {
                showNotification('✓ Đã cập nhật trang trong Notion!', 'success');
                closeNotionAddModal();
            } else {
                alert('Lỗi: ' + (data.error || 'Không thể cập nhật trang'));
            }
        }
    } catch (error) {
        console.error('Error saving to Notion:', error);
        alert('Lỗi khi lưu vào Notion: ' + error.message);
    }
}

function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? 'var(--accent-gradient)' : '#ef4444'};
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        box-shadow: var(--shadow-lg);
        z-index: 10000;
        animation: fadeIn 0.3s ease;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

document.addEventListener('DOMContentLoaded', () => {
    // Initialize Notion float button
    initNotionFloatButton();

    // Notion modal event listeners
    const notionModal = document.getElementById('notionAddModal');
    const notionCloseBtn = document.getElementById('notionAddModalClose');
    const notionCancelBtn = document.getElementById('notionCancelBtn');
    const notionSaveBtn = document.getElementById('notionSaveBtn');
    const refreshPagesBtn = document.getElementById('refreshPagesBtn');
    const refreshParentsBtn = document.getElementById('refreshParentsBtn');

    if (notionCloseBtn) {
        notionCloseBtn.onclick = closeNotionAddModal;
    }

    if (notionCancelBtn) {
        notionCancelBtn.onclick = closeNotionAddModal;
    }

    if (notionSaveBtn) {
        notionSaveBtn.onclick = saveToNotion;
    }

    if (refreshPagesBtn) {
        refreshPagesBtn.onclick = loadNotionPages;
    }

    if (refreshParentsBtn) {
        refreshParentsBtn.onclick = loadNotionParents;
    }

    // Toggle between create and update sections
    const actionRadios = document.querySelectorAll('input[name="notionAction"]');
    actionRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            const createSection = document.getElementById('createSection');
            const updateSection = document.getElementById('updateSection');

            if (e.target.value === 'create') {
                if (createSection) createSection.style.display = 'block';
                if (updateSection) updateSection.style.display = 'none';
            } else {
                if (createSection) createSection.style.display = 'none';
                if (updateSection) updateSection.style.display = 'block';
            }
        });
    });

    // Close modal when clicking outside
    if (notionModal) {
        notionModal.addEventListener('click', (e) => {
            if (e.target === notionModal) {
                closeNotionAddModal();
            }
        });
    }

    // MCP Button - Open tools list
    const mcpBtn = document.getElementById('mcpBtn');
    if (mcpBtn) {
        mcpBtn.addEventListener('click', openMCPToolsModal);
    }

    // MCP Tools Modal Close
    const mcpToolsModalClose = document.getElementById('mcpToolsModalClose');
    if (mcpToolsModalClose) {
        mcpToolsModalClose.addEventListener('click', closeMCPToolsModal);
    }

    const mcpToolsModal = document.getElementById('mcpToolsModal');
    if (mcpToolsModal) {
        mcpToolsModal.addEventListener('click', (e) => {
            if (e.target === mcpToolsModal) {
                closeMCPToolsModal();
            }
        });
    }

    // Notion Tool Item - Open Notion pages or settings
    const notionToolItem = document.getElementById('mcpToolNotion');
    if (notionToolItem) {
        notionToolItem.addEventListener('click', () => {
            const notionKey = localStorage.getItem('notionApiKey') || '';
            if (notionKey && notionKey.trim()) {
                // Open Notion pages modal
                closeMCPToolsModal();
                setTimeout(() => openMCPModal(), 200);
            } else {
                // Open settings to connect
                closeMCPToolsModal();
                const settingsModal = document.getElementById('settingsModal');
                if (settingsModal) {
                    settingsModal.classList.add('active');
                    switchSettingsSection('integrations');
                    setTimeout(() => {
                        const notionConnectBtn = document.getElementById('notionConnectBtn');
                        if (notionConnectBtn) {
                            notionConnectBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        }
                    }, 300);
                }
            }
        });
    }

    // Modal Close Buttons
    const mcpModalClose = document.getElementById('mcpModalClose');
    if (mcpModalClose) {
        mcpModalClose.addEventListener('click', closeMCPModal);
    }

    const pageContentModalClose = document.getElementById('pageContentModalClose');
    if (pageContentModalClose) {
        pageContentModalClose.addEventListener('click', closePageContentModal);
    }

    // Close modals when clicking outside
    const mcpModal = document.getElementById('mcpModal');
    if (mcpModal) {
        mcpModal.addEventListener('click', (e) => {
            if (e.target === mcpModal) {
                closeMCPModal();
            }
        });
    }

    const pageContentModal = document.getElementById('pageContentModal');
    if (pageContentModal) {
        pageContentModal.addEventListener('click', (e) => {
            if (e.target === pageContentModal) {
                closePageContentModal();
            }
        });
    }

    // Load Pages Button
    const loadPagesBtn = document.getElementById('loadPagesBtn');
    if (loadPagesBtn) {
        loadPagesBtn.addEventListener('click', loadPages);
    }

    // Page Search Input - Real-time filtering
    const pageSearchInput = document.getElementById('pageSearchInput');
    if (pageSearchInput) {
        pageSearchInput.addEventListener('input', (e) => {
            filterPages(e.target.value);
        });

        // Clear search when modal opens
        const mcpModal = document.getElementById('mcpModal');
        if (mcpModal) {
            const observer = new MutationObserver(() => {
                if (mcpModal.classList.contains('active')) {
                    pageSearchInput.value = '';
                    if (allPages.length > 0) {
                        renderPages(allPages);
                    }
                }
            });
            observer.observe(mcpModal, { attributes: true, attributeFilter: ['class'] });
        }
    }

    // =================== Settings Modal ===================
    const userProfileBtn = document.getElementById('userProfileBtn');
    const settingsModal = document.getElementById('settingsModal');
    const settingsCloseBtn = document.getElementById('settingsCloseBtn');
    const settingsNavItems = document.querySelectorAll('.settings-nav-item');
    const settingsSections = document.querySelectorAll('.settings-section');

    // Open settings modal
    if (userProfileBtn) {
        userProfileBtn.addEventListener('click', () => {
            if (settingsModal) {
                settingsModal.classList.add('active');
                loadSettings();
                // Re-setup listeners in case settings modal content was dynamically loaded
                setupSettingsListeners();

                // Specifically attach clear data/history button listeners when modal opens
                setTimeout(() => {
                    const clearBtn = document.getElementById('clearDataBtn');
                    const clearHistoryBtn = document.getElementById('clearHistoryBtn');

                    if (clearBtn) {
                        console.log('Clear data button found when modal opened');
                        // Remove any existing listeners to avoid duplicates
                        const newClearBtn = clearBtn.cloneNode(true);
                        clearBtn.parentNode.replaceChild(newClearBtn, clearBtn);

                        newClearBtn.addEventListener('click', (e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            console.log('Clear data button clicked (from modal open)');
                            const modal = document.getElementById('clearAllDataModal');
                            if (modal) {
                                console.log('Opening clear all data modal');
                                modal.classList.add('active');
                            } else {
                                console.error('Clear all data modal not found');
                            }
                        });
                    } else {
                        console.error('Clear data button not found when modal opened');
                    }

                    if (clearHistoryBtn) {
                        console.log('Clear history button found when modal opened');
                        // Remove any existing listeners to avoid duplicates
                        const newClearHistoryBtn = clearHistoryBtn.cloneNode(true);
                        clearHistoryBtn.parentNode.replaceChild(newClearHistoryBtn, clearHistoryBtn);

                        newClearHistoryBtn.addEventListener('click', (e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            console.log('Clear history button clicked (from modal open)');
                            const modal = document.getElementById('clearAllDataModal');
                            if (modal) {
                                // Update modal content for chat clearing
                                const modalTitle = modal.querySelector('h3');
                                const modalDesc = modal.querySelector('p');
                                const modalList = modal.querySelector('.clear-data-list');
                                const modalWarning = modal.querySelector('p[style*="color: #ef4444"]');

                                if (modalTitle) modalTitle.textContent = 'Xóa tất cả lịch sử chat?';
                                if (modalDesc) modalDesc.textContent = 'Hành động này sẽ xóa:';
                                if (modalList) {
                                    modalList.innerHTML = '<li>Tất cả lịch sử chat</li><li>Tất cả tin nhắn</li>';
                                }
                                if (modalWarning) modalWarning.textContent = 'Hành động này không thể hoàn tác!';
                                const confirmBtn = document.getElementById('clearAllDataYes');
                                if (confirmBtn) confirmBtn.textContent = 'Xóa tất cả';

                                window.currentClearAction = 'chats';
                                console.log('Opening clear chat history modal');
                                modal.classList.add('active');
                            } else {
                                console.error('Clear all data modal not found');
                            }
                        });
                    } else {
                        console.error('Clear history button not found when modal opened');
                    }

                    if (clearBtn) {
                        console.log('Clear data button found when modal opened');
                        // Remove any existing listeners to avoid duplicates
                        const newClearBtn = clearBtn.cloneNode(true);
                        clearBtn.parentNode.replaceChild(newClearBtn, clearBtn);

                        newClearBtn.addEventListener('click', (e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            console.log('Clear data button clicked (from modal open)');
                            const modal = document.getElementById('clearAllDataModal');
                            if (modal) {
                                // Update modal content for full reset
                                const modalTitle = modal.querySelector('h3');
                                const modalDesc = modal.querySelector('p');
                                const modalList = modal.querySelector('.clear-data-list');
                                const modalWarning = modal.querySelector('p[style*="color: #ef4444"]');

                                if (modalTitle) modalTitle.textContent = 'Reset về mặc định?';
                                if (modalDesc) modalDesc.textContent = 'Hành động này sẽ:';
                                if (modalList) {
                                    modalList.innerHTML = '<li>Xóa tất cả lịch sử chat</li><li>Xóa tất cả tin nhắn</li><li>Xóa tất cả cài đặt</li><li>Xóa API keys đã lưu</li><li>Reset theme về mặc định (vàng)</li><li>Ngắt tất cả kết nối</li>';
                                }
                                if (modalWarning) modalWarning.textContent = 'Hành động này không thể hoàn tác!';
                                const confirmBtn = document.getElementById('clearAllDataYes');
                                if (confirmBtn) confirmBtn.textContent = 'Reset về mặc định';

                                window.currentClearAction = 'all';
                                console.log('Opening reset modal');
                                modal.classList.add('active');
                            } else {
                                console.error('Clear all data modal not found');
                            }
                        });
                    } else {
                        console.error('Clear data button not found when modal opened');
                    }
                }, 100);
            }
        });
    }

    // Close settings modal
    if (settingsCloseBtn) {
        settingsCloseBtn.addEventListener('click', closeSettingsModal);
    }

    if (settingsModal) {
        settingsModal.addEventListener('click', (e) => {
            if (e.target === settingsModal) {
                closeSettingsModal();
            }
        });
    }

    // Switch settings sections
    settingsNavItems.forEach(item => {
        item.addEventListener('click', () => {
            const section = item.getAttribute('data-section');
            switchSettingsSection(section);
        });
    });

    // Load saved settings
    loadSettings();

    // Save settings on change
    setupSettingsListeners();
});

function closeSettingsModal() {
    const settingsModal = document.getElementById('settingsModal');
    if (settingsModal) {
        settingsModal.classList.remove('active');
        // Only save settings, don't trigger validation
        // Validation only happens when user explicitly saves API key
        saveSettingsWithoutValidation();
    }
}

function switchSettingsSection(section) {
    const navItems = document.querySelectorAll('.settings-nav-item');
    const sections = document.querySelectorAll('.settings-section');

    navItems.forEach(item => {
        if (item.getAttribute('data-section') === section) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    sections.forEach(sec => {
        if (sec.id === `section-${section}`) {
            sec.classList.add('active');
        } else {
            sec.classList.remove('active');
        }
    });

    // Load integration status when opening integrations section
    if (section === 'integrations') {
        if (window.loadIntegrationStatus) {
            window.loadIntegrationStatus();
        } else {
            loadIntegrationStatus();
        }
    }
}

function loadSettings() {
    // Load theme
    const savedTheme = localStorage.getItem('appTheme') || 'pink';
    applyTheme(savedTheme);

    // Load API keys
    const googleKey = localStorage.getItem('googleApiKey') || '';
    const notionKey = localStorage.getItem('notionApiKey') || '';

    const googleInput = document.getElementById('googleApiKey');
    const notionInput = document.getElementById('notionApiKey');

    if (googleInput) googleInput.value = googleKey;
    if (notionInput) notionInput.value = notionKey;

    // Load other settings
    const showResponseTime = localStorage.getItem('showResponseTime') === 'true';
    const autoScroll = localStorage.getItem('autoScroll') !== 'false';
    const notifyOnResponse = localStorage.getItem('notifyOnResponse') !== 'false';
    const soundNotification = localStorage.getItem('soundNotification') === 'true';
    const language = localStorage.getItem('language') || 'vi';
    const interfaceTheme = localStorage.getItem('interfaceTheme') || 'system';

    const showResponseTimeCheck = document.getElementById('showResponseTime');
    const autoScrollCheck = document.getElementById('autoScroll');
    const notifyCheck = document.getElementById('notifyOnResponse');
    const soundCheck = document.getElementById('soundNotification');
    const languageSelect = document.getElementById('languageSelect');
    const interfaceSelect = document.getElementById('interfaceSelect');

    if (showResponseTimeCheck) showResponseTimeCheck.checked = showResponseTime;
    if (autoScrollCheck) autoScrollCheck.checked = autoScroll;
    if (notifyCheck) notifyCheck.checked = notifyOnResponse;
    if (soundCheck) soundCheck.checked = soundNotification;
    if (languageSelect) languageSelect.value = language;
    if (interfaceSelect) {
        interfaceSelect.value = interfaceTheme;
        applyInterfaceTheme(interfaceTheme);
    }
}

function saveSettingsWithoutValidation() {
    // Save settings without triggering API key validation
    // This is used when closing settings modal to avoid unnecessary notifications

    // Save API keys to localStorage only (no backend calls, no validation)
    const googleInput = document.getElementById('googleApiKey');
    const notionInput = document.getElementById('notionApiKey');

    if (googleInput) {
        localStorage.setItem('googleApiKey', googleInput.value);
    }

    if (notionInput) {
        localStorage.setItem('notionApiKey', notionInput.value);
    }

    // Save other settings
    const showResponseTimeCheck = document.getElementById('showResponseTime');
    const autoScrollCheck = document.getElementById('autoScroll');
    const notifyCheck = document.getElementById('notifyOnResponse');
    const soundCheck = document.getElementById('soundNotification');
    const languageSelect = document.getElementById('languageSelect');
    const interfaceSelect = document.getElementById('interfaceSelect');

    if (showResponseTimeCheck) localStorage.setItem('showResponseTime', showResponseTimeCheck.checked);
    if (autoScrollCheck) localStorage.setItem('autoScroll', autoScrollCheck.checked);
    if (notifyCheck) localStorage.setItem('notifyOnResponse', notifyCheck.checked);
    if (soundCheck) localStorage.setItem('soundNotification', soundCheck.checked);
    if (languageSelect) localStorage.setItem('language', languageSelect.value);
    if (interfaceSelect) localStorage.setItem('interfaceTheme', interfaceSelect.value);
}

function saveSettings() {
    // Save API keys to localStorage
    const googleInput = document.getElementById('googleApiKey');
    const notionInput = document.getElementById('notionApiKey');

    if (googleInput) {
        const previousGoogleKey = localStorage.getItem('googleApiKey') || '';
        const newGoogleKey = googleInput.value;
        localStorage.setItem('googleApiKey', newGoogleKey);

        // Only send to backend if key changed
        if (newGoogleKey && newGoogleKey !== previousGoogleKey) {
            fetch('/api/settings/update-api-key', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: 'google', key: newGoogleKey })
            }).catch(err => console.error('Error saving Google API key:', err));
        }
    }

    if (notionInput) {
        const previousKey = localStorage.getItem('notionApiKey') || '';
        const newKey = notionInput.value;

        localStorage.setItem('notionApiKey', newKey);

        // Only send to backend and validate if key actually changed
        if (newKey && newKey !== previousKey) {
            // Reset validation flag when new key is entered
            notionConnectionValidated = false;

            fetch('/api/settings/update-api-key', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: 'notion', key: newKey })
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    // Hide API input section
                    const apiSection = document.getElementById('notionApiSection');
                    if (apiSection) apiSection.style.display = 'none';
                    // Update integration status (this will also update tool status)
                    if (window.loadIntegrationStatus) {
                        window.loadIntegrationStatus();
                    } else {
                        loadIntegrationStatus();
                    }
                    // Validate connection (only show notification on success, not on every validation)
                    validateNotionConnection(newKey, true);
                }
            }).catch(err => console.error('Error saving Notion API key:', err));
        } else if (!newKey && previousKey) {
            // Key was removed
            notionConnectionValidated = false;
            if (window.loadIntegrationStatus) {
                window.loadIntegrationStatus();
            } else {
                loadIntegrationStatus();
            }
        }
    }

    // Save other settings
    const showResponseTimeCheck = document.getElementById('showResponseTime');
    const autoScrollCheck = document.getElementById('autoScroll');
    const notifyCheck = document.getElementById('notifyOnResponse');
    const soundCheck = document.getElementById('soundNotification');
    const languageSelect = document.getElementById('languageSelect');
    const interfaceSelect = document.getElementById('interfaceSelect');

    if (showResponseTimeCheck) localStorage.setItem('showResponseTime', showResponseTimeCheck.checked);
    if (autoScrollCheck) localStorage.setItem('autoScroll', autoScrollCheck.checked);
    if (notifyCheck) localStorage.setItem('notifyOnResponse', notifyCheck.checked);
    if (soundCheck) localStorage.setItem('soundNotification', soundCheck.checked);
    if (languageSelect) localStorage.setItem('language', languageSelect.value);
    if (interfaceSelect) {
        localStorage.setItem('interfaceTheme', interfaceSelect.value);
        applyInterfaceTheme(interfaceSelect.value);
    }
}

function setupSettingsListeners() {
    console.log('Setting up settings listeners...');

    // Theme switcher
    const themePink = document.getElementById('themePink');
    const themeOrange = document.getElementById('themeOrange');

    if (themePink) {
        themePink.addEventListener('click', () => {
            applyTheme('pink');
            saveSettings();
        });
    }

    if (themeOrange) {
        themeOrange.addEventListener('click', () => {
            applyTheme('orange');
            saveSettings();
        });
    }

    // Password toggle
    const passwordToggles = document.querySelectorAll('.settings-input-toggle');
    passwordToggles.forEach(toggle => {
        toggle.addEventListener('click', () => {
            const targetId = toggle.getAttribute('data-target');
            const input = document.getElementById(targetId);
            if (input) {
                if (input.type === 'password') {
                    input.type = 'text';
                } else {
                    input.type = 'password';
                }
            }
        });
    });

    // Interface theme select
    const interfaceSelect = document.getElementById('interfaceSelect');
    if (interfaceSelect) {
        interfaceSelect.addEventListener('change', (e) => {
            applyInterfaceTheme(e.target.value);
            saveSettings();
        });
    }

    // API key toggle buttons
    const apiKeyToggles = document.querySelectorAll('.api-key-toggle');
    apiKeyToggles.forEach(toggle => {
        toggle.addEventListener('click', () => {
            const targetId = toggle.getAttribute('data-target');
            const input = document.getElementById(targetId);
            if (input) {
                if (input.type === 'password') {
                    input.type = 'text';
                } else {
                    input.type = 'password';
                }
            }
        });
    });

    // Save API key buttons
    const saveBtns = document.querySelectorAll('.settings-save-btn');
    saveBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const keyType = btn.getAttribute('data-key');
            const input = document.getElementById(`${keyType}ApiKey`);
            if (input && input.value) {
                // saveSettings() will handle validation and notifications
                saveSettings();
            }
        });
    });

    // Integration connect/disconnect buttons
    const notionConnectBtn = document.getElementById('notionConnectBtn');
    const notionDisconnectBtn = document.getElementById('notionDisconnectBtn');

    if (notionConnectBtn) {
        notionConnectBtn.addEventListener('click', () => {
            openNotionConnectionModal();
        });
    }

    if (notionDisconnectBtn) {
        notionDisconnectBtn.addEventListener('click', () => {
            disconnectNotion();
        });
    }

    // Load integration status on page load
    loadIntegrationStatus();

    // Update Notion tool status when integration status changes
    // Wrap loadIntegrationStatus to also update tool status
    const originalLoadIntegrationStatus = loadIntegrationStatus;
    window.loadIntegrationStatus = function () {
        originalLoadIntegrationStatus();
        updateNotionToolStatus();
    };

    // Delete confirmation modal event listeners
    const deleteConfirmModal = document.getElementById('deleteConfirmModal');
    const deleteConfirmYes = document.getElementById('deleteConfirmYes');
    const deleteConfirmNo = document.getElementById('deleteConfirmNo');

    if (deleteConfirmYes) {
        deleteConfirmYes.addEventListener('click', () => {
            if (currentDeleteChatId) {
                confirmDelete(currentDeleteChatId);
            }
        });
    }

    if (deleteConfirmNo) {
        deleteConfirmNo.addEventListener('click', () => {
            if (currentDeleteChatId) {
                cancelDelete(currentDeleteChatId);
            }
        });
    }

    if (deleteConfirmModal) {
        deleteConfirmModal.addEventListener('click', (e) => {
            if (e.target === deleteConfirmModal) {
                if (currentDeleteChatId) {
                    cancelDelete(currentDeleteChatId);
                }
            }
        });
    }

    // Auto-save on change
    const settingsInputs = document.querySelectorAll('.settings-input, .settings-select, .settings-toggle input, .settings-range');
    settingsInputs.forEach(input => {
        input.addEventListener('change', saveSettings);
    });

    // Export data
    const exportBtn = document.getElementById('exportDataBtn');
    if (exportBtn) {
        exportBtn.addEventListener('click', exportChatData);
    }

    // Clear history button - only clears chats
    const clearHistoryBtn = document.getElementById('clearHistoryBtn');
    if (clearHistoryBtn) {
        console.log('Clear history button found, adding event listener');
        clearHistoryBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('Clear history button clicked');
            const modal = document.getElementById('clearAllDataModal');
            if (modal) {
                // Update modal content for chat clearing
                const modalTitle = modal.querySelector('h3');
                const modalDesc = modal.querySelector('p');
                const modalList = modal.querySelector('.clear-data-list');
                const modalWarning = modal.querySelector('p[style*="color: #ef4444"]');
                const confirmBtn = document.getElementById('clearAllDataYes');

                if (modalTitle) modalTitle.textContent = 'Xóa tất cả lịch sử chat?';
                if (modalDesc) modalDesc.textContent = 'Hành động này sẽ xóa:';
                if (modalList) {
                    modalList.innerHTML = '<li>Tất cả lịch sử chat</li><li>Tất cả tin nhắn</li>';
                }
                if (modalWarning) modalWarning.textContent = 'Hành động này không thể hoàn tác!';
                if (confirmBtn) confirmBtn.textContent = 'Xóa tất cả';

                // Set action to clear chats only
                window.currentClearAction = 'chats';

                console.log('Opening clear chat history modal');
                modal.classList.add('active');
            } else {
                console.error('Clear all data modal not found');
            }
        });
    } else {
        console.warn('Clear history button not found on initial load');
    }

    // Clear data button - resets everything
    const clearBtn = document.getElementById('clearDataBtn');
    if (clearBtn) {
        console.log('Clear data button found, adding event listener');
        clearBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('Clear data button clicked');
            const modal = document.getElementById('clearAllDataModal');
            if (modal) {
                // Update modal content for full reset
                const modalTitle = modal.querySelector('h3');
                const modalDesc = modal.querySelector('p');
                const modalList = modal.querySelector('.clear-data-list');
                const modalWarning = modal.querySelector('p[style*="color: #ef4444"]');
                const confirmBtn = document.getElementById('clearAllDataYes');

                if (modalTitle) modalTitle.textContent = 'Reset về mặc định?';
                if (modalDesc) modalDesc.textContent = 'Hành động này sẽ:';
                if (modalList) {
                    modalList.innerHTML = '<li>Xóa tất cả lịch sử chat</li><li>Xóa tất cả tin nhắn</li><li>Xóa tất cả cài đặt</li><li>Xóa API keys đã lưu</li><li>Reset theme về mặc định (vàng)</li><li>Ngắt tất cả kết nối</li>';
                }
                if (modalWarning) modalWarning.textContent = 'Hành động này không thể hoàn tác!';
                if (confirmBtn) confirmBtn.textContent = 'Reset về mặc định';

                // Set action to clear all data
                window.currentClearAction = 'all';

                console.log('Opening reset modal');
                modal.classList.add('active');
            } else {
                console.error('Clear all data modal not found');
            }
        });
    } else {
        console.warn('Clear data button not found on initial load');
    }

    // Clear all data modal event listeners
    const clearAllDataModal = document.getElementById('clearAllDataModal');
    const clearAllDataYes = document.getElementById('clearAllDataYes');
    const clearAllDataNo = document.getElementById('clearAllDataNo');

    if (clearAllDataYes) {
        clearAllDataYes.addEventListener('click', () => {
            const action = window.currentClearAction || 'all';
            if (action === 'chats') {
                clearAllChats();
            } else {
                clearAllData();
            }
            if (clearAllDataModal) {
                clearAllDataModal.classList.remove('active');
            }
        });
    }

    if (clearAllDataNo) {
        clearAllDataNo.addEventListener('click', () => {
            if (clearAllDataModal) {
                clearAllDataModal.classList.remove('active');
            }
        });
    }

    if (clearAllDataModal) {
        clearAllDataModal.addEventListener('click', (e) => {
            if (e.target === clearAllDataModal) {
                clearAllDataModal.classList.remove('active');
            }
        });
    }
}

function applyTheme(theme) {
    const root = document.documentElement;
    const themePink = document.getElementById('themePink');
    const themeOrange = document.getElementById('themeOrange');

    if (theme === 'orange') {
        // Orange theme - Complete color system
        // Backgrounds
        root.style.setProperty('--bg-primary', '#0a0505');
        root.style.setProperty('--bg-secondary', '#120a08');
        root.style.setProperty('--bg-tertiary', '#1a0f0a');
        root.style.setProperty('--bg-hover', '#221510');
        root.style.setProperty('--bg-active', '#2a1a12');
        root.style.setProperty('--bg-glass', 'rgba(18, 10, 8, 0.9)');

        // Text colors
        root.style.setProperty('--text-primary', '#ffffff');
        root.style.setProperty('--text-secondary', '#f5d4b8');
        root.style.setProperty('--text-tertiary', '#e8c4a5');

        // Borders
        root.style.setProperty('--border-color', 'rgba(245, 158, 11, 0.12)');
        root.style.setProperty('--border-hover', 'rgba(245, 158, 11, 0.2)');

        // Accent colors
        root.style.setProperty('--accent-color', '#f59e0b');
        root.style.setProperty('--accent-hover', '#fbbf24');
        root.style.setProperty('--accent-gradient', 'linear-gradient(135deg, #f59e0b 0%, #f97316 100%)');
        root.style.setProperty('--accent-glow', 'rgba(245, 158, 11, 0.25)');

        // Update background pattern for orange theme
        updateBackgroundPattern('orange');

        if (themePink) themePink.classList.remove('active');
        if (themeOrange) themeOrange.classList.add('active');
    } else {
        // Pink theme (current) - Complete color system
        // Backgrounds
        root.style.setProperty('--bg-primary', '#0a0508');
        root.style.setProperty('--bg-secondary', '#120a0e');
        root.style.setProperty('--bg-tertiary', '#1a0f14');
        root.style.setProperty('--bg-hover', '#22151a');
        root.style.setProperty('--bg-active', '#2a1a20');
        root.style.setProperty('--bg-glass', 'rgba(18, 10, 14, 0.9)');

        // Text colors
        root.style.setProperty('--text-primary', '#ffffff');
        root.style.setProperty('--text-secondary', '#e8b8c8');
        root.style.setProperty('--text-tertiary', '#d4a5b5');

        // Borders
        root.style.setProperty('--border-color', 'rgba(255, 145, 164, 0.12)');
        root.style.setProperty('--border-hover', 'rgba(255, 145, 164, 0.2)');

        // Accent colors
        root.style.setProperty('--accent-color', '#ff6b9d');
        root.style.setProperty('--accent-hover', '#ff8fb3');
        root.style.setProperty('--accent-gradient', 'linear-gradient(135deg, #ff6b9d 0%, #ff91a4 100%)');
        root.style.setProperty('--accent-glow', 'rgba(255, 107, 157, 0.25)');

        // Update background pattern for pink theme
        updateBackgroundPattern('pink');

        if (themePink) themePink.classList.add('active');
        if (themeOrange) themeOrange.classList.remove('active');
    }

    localStorage.setItem('appTheme', theme);
}

function applyInterfaceTheme(theme) {
    const root = document.documentElement;
    if (theme === 'light') {
        // Light theme - adjust brightness
        root.style.setProperty('--bg-primary', '#f5f5f5');
        root.style.setProperty('--bg-secondary', '#ffffff');
        root.style.setProperty('--bg-tertiary', '#fafafa');
        root.style.setProperty('--bg-hover', '#f0f0f0');
        root.style.setProperty('--text-primary', '#1a1a1a');
        root.style.setProperty('--text-secondary', '#4a4a4a');
        root.style.setProperty('--text-tertiary', '#6a6a6a');
        root.style.setProperty('--border-color', 'rgba(0, 0, 0, 0.1)');
    } else if (theme === 'dark') {
        // Dark theme - restore original dark colors based on current accent
        const currentTheme = localStorage.getItem('appTheme') || 'pink';
        applyTheme(currentTheme);
    } else {
        // System - follow system preference
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        if (prefersDark) {
            const currentTheme = localStorage.getItem('appTheme') || 'pink';
            applyTheme(currentTheme);
        } else {
            applyInterfaceTheme('light');
        }
    }
}

function updateBackgroundPattern(theme) {
    const appContainer = document.querySelector('.app-container');
    if (!appContainer) return;

    // Create or update style element for background pattern
    let styleEl = document.getElementById('dynamic-bg-pattern');
    if (!styleEl) {
        styleEl = document.createElement('style');
        styleEl.id = 'dynamic-bg-pattern';
        document.head.appendChild(styleEl);
    }

    if (theme === 'orange') {
        styleEl.textContent = `
            .app-container::before {
                background: 
                    radial-gradient(circle at 20% 50%, rgba(245, 158, 11, 0.05) 0%, transparent 50%),
                    radial-gradient(circle at 80% 80%, rgba(249, 115, 22, 0.04) 0%, transparent 50%);
            }
        `;
    } else {
        styleEl.textContent = `
            .app-container::before {
                background: 
                    radial-gradient(circle at 20% 50%, rgba(255, 107, 157, 0.05) 0%, transparent 50%),
                    radial-gradient(circle at 80% 80%, rgba(255, 145, 164, 0.04) 0%, transparent 50%);
            }
        `;
    }
}

function exportChatData() {
    const allChats = [];
    const keys = Object.keys(localStorage);

    keys.forEach(key => {
        if (key.startsWith('messages_')) {
            const chatId = key.replace('messages_', '');
            const messages = JSON.parse(localStorage.getItem(key) || '[]');
            const chatInfo = JSON.parse(localStorage.getItem(`chat_${chatId}`) || '{}');

            allChats.push({
                chatId,
                title: chatInfo.title || 'Untitled',
                timestamp: chatInfo.timestamp || Date.now(),
                messages
            });
        }
    });

    const dataStr = JSON.stringify(allChats, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `chat-export-${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    URL.revokeObjectURL(url);

    showNotification('✓ Đã xuất dữ liệu thành công!', 'success');
}

// Clear all chats only (preserve settings and API keys)
function clearAllChats() {
    try {
        // Clear all chat-related data
        const keys = Object.keys(localStorage);
        keys.forEach(key => {
            // Remove all chat data
            if (key.startsWith('messages_') ||
                key.startsWith('chat_') ||
                key === 'chatHistory' ||
                key === 'currentChatId') {
                localStorage.removeItem(key);
            }
        });

        // Clear chat history array
        chatHistory = [];
        messages = [];
        currentChatId = null;

        // Update UI
        renderChatHistory();
        renderMessages();

        // Show notification
        showNotification('✓ Đã xóa tất cả lịch sử chat', 'success');

        // Close confirmation modal
        const clearAllDataModal = document.getElementById('clearAllDataModal');
        if (clearAllDataModal) {
            clearAllDataModal.classList.remove('active');
        }

        console.log('All chats cleared successfully');
    } catch (error) {
        console.error('Error clearing chats:', error);
        showNotification('Lỗi khi xóa lịch sử chat', 'error');
    }
}

// Clear all data and reset to default (including settings, API keys, theme)
function clearAllData() {
    try {
        // Clear all chat-related data
        const keys = Object.keys(localStorage);
        keys.forEach(key => {
            // Remove all chat data
            if (key.startsWith('messages_') ||
                key.startsWith('chat_') ||
                key === 'chatHistory' ||
                key === 'currentChatId') {
                localStorage.removeItem(key);
            }
        });

        // Clear chat history array
        chatHistory = [];
        messages = [];
        currentChatId = null;

        // Clear API keys
        localStorage.removeItem('notionApiKey');
        localStorage.removeItem('googleApiKey');

        // Clear all settings
        localStorage.removeItem('appTheme');
        localStorage.removeItem('showResponseTime');
        localStorage.removeItem('autoScroll');
        localStorage.removeItem('notifyOnResponse');
        localStorage.removeItem('soundNotification');
        localStorage.removeItem('language');
        localStorage.removeItem('interfaceTheme');

        // Reset validation flag
        notionConnectionValidated = false;

        // Clear backend API keys from session
        fetch('/api/settings/update-api-key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'notion', key: '' })
        }).catch(err => console.error('Error clearing Notion API key:', err));

        fetch('/api/settings/update-api-key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'google', key: '' })
        }).catch(err => console.error('Error clearing Google API key:', err));

        // Reset theme to default (orange/yellow)
        applyTheme('orange');
        applyInterfaceTheme('system');
        updateBackgroundPattern('orange');

        // Update UI
        renderChatHistory();
        renderMessages();

        // Reload integration status
        if (window.loadIntegrationStatus) {
            window.loadIntegrationStatus();
        } else {
            loadIntegrationStatus();
        }

        // Reload settings to reflect cleared state
        loadSettings();

        // Show notification
        showNotification('✓ Đã reset về mặc định', 'success');

        // Close confirmation modal
        const clearAllDataModal = document.getElementById('clearAllDataModal');
        if (clearAllDataModal) {
            clearAllDataModal.classList.remove('active');
        }

        // Close settings modal if open
        const settingsModal = document.getElementById('settingsModal');
        if (settingsModal) {
            settingsModal.classList.remove('active');
        }

        console.log('All data cleared and reset to default');
    } catch (error) {
        console.error('Error clearing data:', error);
        showNotification('Lỗi khi reset dữ liệu', 'error');
    }
}

function loadIntegrationStatus() {
    const notionKey = localStorage.getItem('notionApiKey') || '';
    const notionCard = document.getElementById('notionIntegrationCard');
    const connectBtn = document.getElementById('notionConnectBtn');
    const details = document.getElementById('notionIntegrationDetails');
    const apiSection = document.getElementById('notionApiSection');

    if (notionKey && notionKey.trim()) {
        // Connected
        if (connectBtn) {
            connectBtn.classList.add('connected');
            connectBtn.querySelector('.btn-text').textContent = 'Đã kết nối';
            connectBtn.style.display = 'flex';
        }
        if (details) {
            details.style.display = 'block';
        }
        if (apiSection) {
            apiSection.style.display = 'none';
        }
    } else {
        // Not connected
        if (connectBtn) {
            connectBtn.classList.remove('connected');
            connectBtn.querySelector('.btn-text').textContent = 'Kết nối';
            connectBtn.style.display = 'flex';
        }
        if (details) {
            details.style.display = 'none';
        }
        if (apiSection) {
            apiSection.style.display = 'none';
        }
    }
}

function openNotionConnectionModal() {
    // Show API key input section within the integration card
    const apiSection = document.getElementById('notionApiSection');
    const details = document.getElementById('notionIntegrationDetails');
    const connectBtn = document.getElementById('notionConnectBtn');

    if (apiSection) {
        apiSection.style.display = 'block';
        if (details) details.style.display = 'none';
        if (connectBtn) connectBtn.style.display = 'none';

        // Focus on input
        const notionInput = document.getElementById('notionApiKey');
        if (notionInput) {
            setTimeout(() => {
                notionInput.focus();
                notionInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 100);
        }
    }
}

function disconnectNotion() {
    if (confirm('Bạn có chắc muốn ngắt kết nối Notion? Bạn sẽ không thể sử dụng các tính năng MCP cho đến khi kết nối lại.')) {
        localStorage.removeItem('notionApiKey');
        // Clear input
        const notionInput = document.getElementById('notionApiKey');
        if (notionInput) notionInput.value = '';

        // Reset validation flag
        notionConnectionValidated = false;

        // Hide floating button if visible
        if (notionFloatBtn) {
            notionFloatBtn.classList.remove('active');
        }

        // Also clear from session
        fetch('/api/settings/update-api-key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'notion', key: '' })
        }).catch(err => console.error('Error clearing Notion API key:', err));

        if (window.loadIntegrationStatus) {
            window.loadIntegrationStatus();
        } else {
            loadIntegrationStatus();
        }
        showNotification('✓ Đã ngắt kết nối Notion', 'success');
    }
}

// Track if we've already shown connection success notification
let notionConnectionValidated = false;

async function validateNotionConnection(apiKey, showSuccessNotification = false) {
    try {
        // Test connection by trying to list resources
        const response = await fetch('/api/mcp/list-resources', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();
        if (data.success) {
            // Update integration status
            if (window.loadIntegrationStatus) {
                window.loadIntegrationStatus();
            } else {
                loadIntegrationStatus();
            }

            // Only show success notification if explicitly requested and not already shown
            if (showSuccessNotification && !notionConnectionValidated) {
                showNotification('Kết nối Notion thành công!', 'success');
                notionConnectionValidated = true;
            }
        } else {
            // Always show error notification
            showNotification('Không thể kết nối với Notion. Vui lòng kiểm tra API key.', 'error');
            notionConnectionValidated = false;
        }
    } catch (error) {
        console.error('Error validating Notion connection:', error);
        showNotification('Lỗi khi kiểm tra kết nối Notion', 'error');
        notionConnectionValidated = false;
    }
}

// =================== Paste Handling ===================
let currentPastedFile = null;

function showPasteModal(file) {
    const modal = document.getElementById('pasteImageModal');
    const preview = document.getElementById('pasteImagePreview');
    const filename = document.getElementById('pasteFilename');

    if (!modal || !preview || !filename) return;

    // Store file for later use
    currentPastedFile = file;

    // Set filename
    filename.textContent = file.name;

    // Create preview URL
    const reader = new FileReader();
    reader.onload = (e) => {
        preview.src = e.target.result;
    };
    reader.readAsDataURL(file);

    // Show modal
    modal.classList.add('active');
}

function hidePasteModal() {
    const modal = document.getElementById('pasteImageModal');
    const preview = document.getElementById('pasteImagePreview');

    if (modal) {
        modal.classList.remove('active');
    }

    if (preview) {
        preview.src = '';
    }

    currentPastedFile = null;
}

function initializePasteHandler() {
    const chatInput = document.getElementById('chatInput');
    if (!chatInput) return;

    // Prevent duplicate listeners
    if (chatInput.dataset.pasteHandlerAttached) return;

    chatInput.addEventListener('paste', async (e) => {
        const items = (e.clipboardData || e.originalEvent.clipboardData).items;

        for (let i = 0; i < items.length; i++) {
            if (items[i].type.indexOf('image') !== -1) {
                const blob = items[i].getAsFile();
                if (!blob) continue;

                // Prevent default paste behavior
                e.preventDefault();

                // Create a file with a timestamp if name is generic
                const filename = blob.name === 'image.png' ? `pasted_image_${Date.now()}.png` : blob.name;
                const file = new File([blob], filename, { type: blob.type });

                // Show custom modal instead of confirm
                showPasteModal(file);
                return; // Handle only the first image
            }
        }
    });

    chatInput.dataset.pasteHandlerAttached = 'true';
    console.log('Paste handler initialized on chatInput');
}

// Initialize paste modal button handlers
function initializePasteModalHandlers() {
    const ocrBtn = document.getElementById('pasteOcrBtn');
    const cancelBtn = document.getElementById('pasteCancelBtn');
    const modal = document.getElementById('pasteImageModal');

    // Prevent duplicate listeners
    if (ocrBtn && ocrBtn.dataset.listenerAttached) return;

    if (ocrBtn) {
        ocrBtn.addEventListener('click', async () => {
            if (!currentPastedFile) {
                console.warn('No file to process');
                hidePasteModal();
                return;
            }

            // Store file reference before hiding modal
            const fileToProcess = currentPastedFile;
            hidePasteModal();

            try {
                console.log('User confirmed OCR for paste:', fileToProcess.name);
                await uploadOCRFile(fileToProcess);
                showNotification('Đã tải lên OCR thành công', 'success');
            } catch (error) {
                console.error('Paste OCR failed:', error);
                showNotification('Lỗi khi xử lý OCR: ' + error.message, 'error');
            }
        });
        ocrBtn.dataset.listenerAttached = 'true';
    }

    if (cancelBtn && !cancelBtn.dataset.listenerAttached) {
        cancelBtn.addEventListener('click', () => {
            hidePasteModal();
        });
        cancelBtn.dataset.listenerAttached = 'true';
    }

    // Close on overlay click
    if (modal && !modal.dataset.listenerAttached) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                hidePasteModal();
            }
        });
        modal.dataset.listenerAttached = 'true';
    }
}

// Initialize paste handler
document.addEventListener('DOMContentLoaded', () => {
    initializePasteHandler();
    initializePasteModalHandlers();
});
// Also call immediately in case DOM is already loaded
if (document.readyState === 'loading') {
    // DOM not ready yet, DOMContentLoaded will handle it
} else {
    // DOM already loaded
    initializePasteHandler();
    initializePasteModalHandlers();
}

