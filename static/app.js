document.addEventListener('DOMContentLoaded', () => {
    const chatHistory = document.getElementById('chat-history');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const newChatBtn = document.getElementById('new-chat-btn');
    const chatListContainer = document.getElementById('chat-list');
    const titleEle = document.getElementById('current-chat-title');

    let currentChatId = null;

    // --- Core UI Helpers ---

    function escapeHTML(str) {
        return str.replace(/[&<>'"]/g, 
            tag => ({'&': '&amp;','<': '&lt;','>': '&gt;',"'": '&#39;','"': '&quot;'}[tag] || tag)
        ).replace(/\n/g, '<br>');
    }

    function typeHTMLAndScroll(container, html, onComplete) {
        let i = 0;
        let isTag = false;
        let partialHtml = '';
        
        function typeChar() {
            if (i >= html.length) {
                if (onComplete) onComplete();
                return;
            }
            
            const char = html[i];
            partialHtml += char;
            
            // Fast-forward HTML tags so they aren't parsed broken mid-animation
            if (char === '<') isTag = true;
            if (char === '>') isTag = false;

            if (!isTag) {
                container.innerHTML = partialHtml;
                chatHistory.scrollTop = chatHistory.scrollHeight;
            }
            
            i++;
            // Randomize typing speed slightly (0 delays inside tags to jump instantly)
            setTimeout(typeChar, isTag ? 0 : Math.random() * 15 + 5);
        }
        
        typeChar();
    }

    function addMessage(text, isUser = false, animate = false, onComplete = null) {
        const msgWrapper = document.createElement('div');
        msgWrapper.className = `message ${isUser ? 'user-message' : 'ai-message'} fade-in`;
        
        const msgContent = document.createElement('div');
        msgContent.className = 'message-content';
        
        let formattedText = escapeHTML(text);
        formattedText = formattedText.replace(/```(.*?)```/gs, '<pre><code>$1</code></pre>');
        formattedText = formattedText.replace(/`([^`]+)`/g, '<code>$1</code>');
        formattedText = formattedText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        msgWrapper.appendChild(msgContent);
        chatHistory.appendChild(msgWrapper);
        chatHistory.scrollTop = chatHistory.scrollHeight;

        if (animate) {
            typeHTMLAndScroll(msgContent, formattedText, onComplete);
        } else {
            msgContent.innerHTML = formattedText;
            if(onComplete) onComplete();
        }
    }

    function addTypingIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'message ai-message fade-in';
        indicator.id = 'typing-indicator';
        indicator.innerHTML = `
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>`;
        chatHistory.appendChild(indicator);
        chatHistory.scrollTop = chatHistory.scrollHeight;
        return indicator;
    }

    // --- State Management API Calls ---

    async function loadAllChats() {
        try {
            const res = await fetch('/api/chats');
            const data = await res.json();
            renderSidebar(data.chats);
            
            if (!data.chats || data.chats.length === 0) {
                await createNewChat();
            } else {
                await loadChatSession(data.chats[data.chats.length - 1].id);
            }
        } catch (e) { console.error("Could not fetch chat history", e); }
    }

    function renderSidebar(chats) {
        chatListContainer.innerHTML = '';
        chats.forEach(chat => {
            const li = document.createElement('li');
            li.className = `chat-item ${chat.id === currentChatId ? 'active' : ''}`;
            li.textContent = chat.title;
            li.addEventListener('click', () => loadChatSession(chat.id));
            chatListContainer.appendChild(li);
        });
    }

    function updateSidebarActiveState() {
        Array.from(chatListContainer.children).forEach(item => item.classList.remove('active'));
    }

    async function createNewChat() {
        try {
            const res = await fetch('/api/chats', { method: 'POST' });
            const data = await res.json();
            
            const li = document.createElement('li');
            li.className = 'chat-item active';
            li.textContent = data.title;
            li.setAttribute("data-id", data.id);
            li.addEventListener('click', () => loadChatSession(data.id));
            
            updateSidebarActiveState();
            chatListContainer.appendChild(li);
            
            switchChatView(data.id, data.title, [], 0);
        } catch (e) { console.error(e); }
    }

    async function loadChatSession(id) {
        if (currentChatId === id) return;
        try {
            const res = await fetch(`/api/chat/${id}`);
            const data = await res.json();
            switchChatView(data.id, data.title, data.history, data.tokens_used);
        } catch (e) { console.error(e); }
    }

    function switchChatView(id, title, history, tokens) {
        currentChatId = id;
        titleEle.textContent = title;
        chatHistory.innerHTML = '';
        
        if (history.length === 0) {
            addMessage("Hello! I'm BBBot. How can I assist you today?", false);
        } else {
            history.forEach(msg => addMessage(msg.text, msg.role === 'user'));
        }
        
        Array.from(chatListContainer.children).forEach(li => {
            li.classList.toggle('active', li.textContent === title || window.currentLoadedChat === id);
        });
        
        userInput.disabled = false;
        sendBtn.disabled = false;
        userInput.focus();
        loadAllChatsSidebarRefreshSilently();
    }

    async function loadAllChatsSidebarRefreshSilently() {
        const res = await fetch('/api/chats');
        const data = await res.json();
        chatListContainer.innerHTML = '';
        data.chats.forEach(chat => {
            const li = document.createElement('li');
            li.className = `chat-item ${chat.id === currentChatId ? 'active' : ''}`;
            li.textContent = chat.title;
            li.addEventListener('click', () => loadChatSession(chat.id));
            chatListContainer.appendChild(li);
        });
    }

    async function handleSend() {
        const text = userInput.value.trim();
        if (!text || !currentChatId) return;

        // User message is instant
        addMessage(text, true);
        userInput.value = '';
        userInput.disabled = true;
        sendBtn.disabled = true;

        const typingIndicator = addTypingIndicator();

        try {
            const response = await fetch(`/api/chat/${currentChatId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });

            if (!response.ok) throw new Error(`Server status ${response.status}`);
            
            const data = await response.json();
            const indicator = document.getElementById('typing-indicator');
            if(indicator) indicator.remove();
            
            if (data.reply) {
                // Animate AI generation effect
                addMessage(data.reply, false, true, () => {
                    // Only re-enable inputs when animation fully completes
                    userInput.disabled = false;
                    sendBtn.disabled = false;
                    userInput.focus();
                });
                
                if(data.title) {
                    titleEle.textContent = data.title;
                    loadAllChatsSidebarRefreshSilently();
                }
            } else if (data.error) {
                addMessage(`Error: ${data.error}`, false);
                userInput.disabled = false;
                sendBtn.disabled = false;
            }
            
        } catch (error) {
            const indicator = document.getElementById('typing-indicator');
            if(indicator) indicator.remove();
            
            addMessage(`Failed to connect. Error: ${error.message}`, false);
            
            // Re-enable input if error happens
            userInput.disabled = false;
            sendBtn.disabled = false;
            userInput.focus();
        }
    }

    // --- Event Listeners ---
    newChatBtn.addEventListener('click', createNewChat);
    sendBtn.addEventListener('click', handleSend);
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            handleSend();
        }
    });

    // Boot Up
    loadAllChats();
});
