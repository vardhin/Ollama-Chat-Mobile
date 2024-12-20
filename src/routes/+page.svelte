<script>
    import { onMount } from 'svelte';
    import { fade } from 'svelte/transition';
    import { Send, Maximize2, Minimize2, Menu, XCircle, RotateCcw, Zap, ZapOff, Moon } from 'lucide-svelte';

    let messages = [];
    let inputMessage = '';
    let chatContainer;
    let isLoading = false;
    let socket;
    let isFullscreen = false;
    let isFirstChunk = true;
    let pendingAssistantName = '';
    let isSidebarOpen = false;
    let contextStatus = { total_tokens: 0, context_limit: 0, usage_percentage: 0 };
    let fastMode = false;
    let isOledMode = false;

    // Add title
    const title = "Rhea";

    // Add helper function for scrolling
    function scrollToBottom() {
        requestAnimationFrame(() => {
            if (chatContainer) {
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
        });
    }

    onMount(() => {
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            console.log('Attempting to connect to:', wsUrl);
            
            socket = new WebSocket(wsUrl);
            
            socket.onopen = () => {
                console.log('WebSocket connected successfully');
            };
            
            socket.onmessage = (event) => {
                console.log('Received message:', event.data);
                const data = JSON.parse(event.data);
                
                if (data.error) {
                    messages = [...messages, { 
                        id: Date.now().toString(),
                        role: 'assistant', 
                        content: 'Sorry, there was an error: ' + data.error 
                    }];
                    isLoading = false;
                    return;
                }

                if (data.chunk) {
                    const lastMessage = messages[messages.length - 1];
                    let chunk = data.chunk;
                    
                    // Handle assistant name across chunks
                    if (isFirstChunk) {
                        pendingAssistantName = chunk;
                        isFirstChunk = false;
                        return;
                    } else if (chunk === ':') {
                        isFirstChunk = false;
                        return;
                    }
                    
                    // Replace double asterisks with single asterisk
                    chunk = chunk.replace(/\*\*/g, '*');
                    
                    lastMessage.content += chunk;
                    messages = messages;
                    
                    // Scroll while streaming only if near bottom
                    const isNearBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < 100;
                    if (isNearBottom) {
                        scrollToBottom();
                    }

                    // If the chunk ends with a period and a space or newline, assume it's the end
                    if (data.chunk.endsWith('. ') || data.chunk.endsWith('.\n') || data.chunk.endsWith('\n')) {
                        isLoading = false;
                    }
                }

                // Reset the first chunk flag when stream ends
                if (data.chunk === '') {
                    isFirstChunk = true;
                    pendingAssistantName = '';
                    isLoading = false;
                }
            };

            socket.onerror = (error) => {
                console.error('WebSocket error details:', error);
                messages = [...messages, { 
                    id: Date.now().toString(),
                    role: 'assistant', 
                    content: 'Sorry, there was a connection error.' 
                }];
                isLoading = false;
            };

            socket.onclose = (event) => {
                console.log('WebSocket closed. Code:', event.code, 'Reason:', event.reason);
                setTimeout(connectWebSocket, 3000);
            };
        }

        connectWebSocket();
        updateContextStatus();
        const statusInterval = setInterval(updateContextStatus, 10000); // Update every 10 seconds

        return () => {
            clearInterval(statusInterval);
        };
    });

    async function sendMessage() {
        if (!inputMessage.trim() || !socket || socket.readyState !== WebSocket.OPEN) return;

        // Reset textarea height BEFORE clearing input
        const textarea = document.querySelector('textarea');
        if (textarea) {
            textarea.style.height = '24px';
        }

        // Add user message
        const messageId = Date.now().toString();
        messages = [...messages, { id: messageId, role: 'user', content: inputMessage }];
        const userMessage = inputMessage;
        inputMessage = '';
        isLoading = true;

        scrollToBottom();

        // Add assistant message placeholder
        const assistantMessageId = (Date.now() + 1).toString();
        messages = [...messages, { id: assistantMessageId, role: 'assistant', content: '' }];

        // Send message through WebSocket
        socket.send(JSON.stringify({ message: userMessage }));
    }

    function handleKeydown(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            const textarea = event.target;
            textarea.style.height = '24px';
            sendMessage();
        }
    }

    // Add function to auto-resize textarea
    function adjustTextareaHeight(event) {
        const textarea = event.target;
        const lineHeight = 24;
        const padding = 12; // 0.75rem converted to pixels
        
        // Store the current scroll position
        const scrollPos = textarea.scrollTop;
        
        // Reset height to auto to get proper scrollHeight
        textarea.style.height = 'auto';
        
        // Calculate new height (limit to 3 lines)
        const totalHeight = Math.min(
            Math.max(lineHeight + (padding * 2), textarea.scrollHeight),
            (lineHeight * 3) + (padding * 2)
        );
        
        // Set the new height
        textarea.style.height = `${totalHeight}px`;
        
        // Restore scroll position
        textarea.scrollTop = scrollPos;
    }

    function toggleFullscreen() {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen()
                .then(() => isFullscreen = true)
                .catch(err => console.error(err));
        } else {
            document.exitFullscreen()
                .then(() => isFullscreen = false)
                .catch(err => console.error(err));
        }
    }

    // Add function to fetch context status
    async function updateContextStatus() {
        try {
            const response = await fetch('/api/context/status');
            contextStatus = await response.json();
        } catch (error) {
            console.error('Failed to fetch context status:', error);
        }
    }

    // Add function to clear context
    async function clearContext() {
        try {
            await fetch('/api/clear', { method: 'POST' });
            messages = [];
            updateContextStatus();
        } catch (error) {
            console.error('Failed to clear context:', error);
        }
    }

    // Add function to toggle fast mode
    function toggleFastMode() {
        fastMode = !fastMode;
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ toggle_fast_mode: fastMode }));
        }
    }

    // Add function to toggle OLED mode
    function toggleOledMode() {
        isOledMode = !isOledMode;
        document.documentElement.classList.toggle('oled-mode');
    }
</script>

<div class="app-container">
    <header class="top-bar">
        <div class="left-section">
            <button 
                class="menu-btn" 
                on:click={() => isSidebarOpen = !isSidebarOpen}
                aria-label="Toggle menu"
            >
                <Menu size={20} />
            </button>
            <h1>{title}</h1>
        </div>
        <div class="right-section">
            <button 
                class="icon-btn" 
                on:click={toggleOledMode}
                aria-label="Toggle OLED mode"
            >
                <Moon size={20} />
            </button>
            <button 
                class="icon-btn" 
                on:click={clearContext}
                aria-label="Clear context"
            >
                <RotateCcw size={20} />
            </button>
            <button 
                class="fullscreen-btn" 
                on:click={toggleFullscreen} 
                aria-label="Toggle fullscreen"
            >
                {#if isFullscreen}
                    <Minimize2 size={20} />
                {:else}
                    <Maximize2 size={20} />
                {/if}
            </button>
        </div>
    </header>

    <!-- Add sidebar -->
    {#if isSidebarOpen}
        <div class="sidebar" transition:fade={{ duration: 200 }}>
            <div class="sidebar-header">
                <h2>Settings</h2>
                <button 
                    class="close-btn" 
                    on:click={() => isSidebarOpen = false}
                    aria-label="Close sidebar"
                >
                    <XCircle size={20} />
                </button>
            </div>
            <div class="sidebar-content">
                <div class="context-info">
                    <h3>Context Usage</h3>
                    <div class="progress-bar">
                        <div 
                            class="progress" 
                            style="width: {contextStatus.usage_percentage}%"
                        ></div>
                    </div>
                    <p>{Math.round(contextStatus.total_tokens)} / {contextStatus.context_limit} tokens</p>
                </div>
                <div class="mode-toggle">
                    <h3>Fast Mode</h3>
                    <button 
                        class="toggle-btn {fastMode ? 'active' : ''}" 
                        on:click={toggleFastMode}
                    >
                        {#if fastMode}
                            <Zap size={20} />
                        {:else}
                            <ZapOff size={20} />
                        {/if}
                        {fastMode ? 'Enabled' : 'Disabled'}
                    </button>
                </div>
            </div>
        </div>
    {/if}

    <!-- Add overlay when sidebar is open -->
    {#if isSidebarOpen}
        <div 
            class="overlay" 
            on:click={() => isSidebarOpen = false}
            transition:fade={{ duration: 200 }}
        ></div>
    {/if}

    <div class="chat-container">
        <div class="messages" bind:this={chatContainer}>
            {#each messages as message (message.id)}
                <div 
                    class="message {message.role}" 
                    transition:fade|local={{ duration: 150 }}
                >
                    <div class="message-content">
                        {message.content}
                    </div>
                </div>
            {/each}
            {#if isLoading}
                <div class="loading-indicator">
                    <div class="dot"></div>
                    <div class="dot"></div>
                    <div class="dot"></div>
                </div>
            {/if}
        </div>
        
        <div class="input-container">
            <textarea
                bind:value={inputMessage}
                on:keydown={handleKeydown}
                on:input={adjustTextareaHeight}
                placeholder="Type a message..."
                rows="1"
            />
            <button 
                on:click={sendMessage} 
                disabled={isLoading || !inputMessage.trim()}
            >
                <Send size={20} />
            </button>
        </div>
    </div>
</div>

<style>
    /* Update font import */
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@300;400;500;600;700&display=swap');

    :global(body) {
        margin: 0;
        background-color: #151a23;
        color: #e0e1e2;
        font-family: 'Quicksand', sans-serif;
        scroll-behavior: smooth;
    }

    :global(*) {
        scrollbar-width: none;
        -ms-overflow-style: none;
        scroll-behavior: smooth;
    }

    :global(*::-webkit-scrollbar) {
        display: none;
    }

    :root {
        --container-bg: #151a23;
        --user-msg-bg: #00957d;
        --user-msg-shadow: 0 0 15px rgba(0, 149, 125, 0.3);
        --input-bg: #1b2531;
    }

    :global(.oled-mode) {
        --container-bg: #000000;
        --user-msg-bg: #006857;
        --user-msg-shadow: 0 0 10px rgba(0, 104, 87, 0.15);
        --input-bg: #131920;
    }

    .app-container {
        height: 100dvh;
        display: flex;
        flex-direction: column;
        position: fixed;
        width: 100%;
        left: 0;
        top: 0;
        background-color: var(--container-bg);
    }

    .top-bar {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        background: transparent;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        padding: 0.5rem 2rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        z-index: 10;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .top-bar h1 {
        margin: 0;
        font-size: 1.1rem;
        font-weight: 600;
        color: #fff;
    }

    .chat-container {
        flex: 1;
        max-width: 900px;
        margin: 0 auto;
        padding: 0 1rem;
        width: 100%;
        box-sizing: border-box;
        padding-top: 3rem;
        padding-bottom: 5rem;
        position: relative;
        height: 100%;
        overflow: hidden;
        background-color: var(--container-bg);
    }

    .messages {
        height: 100%;
        padding: 1rem;
        display: flex;
        flex-direction: column;
        gap: 1rem;
        background-color: inherit;
        border-radius: 0.75rem;
        overflow-y: auto;
        -webkit-overflow-scrolling: touch;
        position: relative;
    }

    .messages::-webkit-scrollbar {
        display: none;
    }

    .message {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .message.user {
        align-items: flex-end;
    }

    .message.assistant {
        align-items: flex-start;
    }

    .message-content {
        padding: 0.8rem 1rem;
        border-radius: 1rem;
        max-width: 80%;
        font-size: 0.95rem;
        line-height: 1.5;
        word-wrap: break-word;
        white-space: pre-wrap;
    }

    .user .message-content {
        background-color: var(--user-msg-bg);
        color: #f0fff4;
        border-bottom-right-radius: 0.25rem;
        box-shadow: var(--user-msg-shadow);
    }

    .assistant .message-content {
        background-color: var(--input-bg);
        color: #e0e1e2;
        border-bottom-left-radius: 0.25rem;
    }

    .input-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: transparent;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-top: 1px solid rgba(255, 255, 255, 0.1);
        padding: 1rem 1.5rem;
        z-index: 10;
        display: flex;
        gap: 0.75rem;
        align-items: center;
        justify-content: center;
    }

    /* Center the input container content */
    .input-container > div {
        max-width: 900px;
        margin: 0 auto;
        width: 100%;
        display: flex;
        gap: 0.75rem;
    }

    textarea {
        flex: 1;
        height: 24px;
        min-height: 24px;
        max-height: 90px;
        padding: 10px 16px;
        background-color: var(--input-bg);
        color: #e0e1e2;
        border: 1px solid #2a3441;
        border-radius: 22px;
        resize: none;
        font-family: 'Quicksand', sans-serif;
        font-size: 0.95rem;
        line-height: 1.5;
        transition: all 0.2s ease;
        overflow-y: auto;
        -webkit-appearance: none;
        appearance: none;
    }

    textarea:focus {
        outline: none;
        border-color: #00957d;
        box-shadow: 0 0 10px rgba(0, 149, 125, 0.2);
    }

    button {
        padding: 0;
        min-width: 44px;
        height: 44px;
        background-color: #00957d;
        color: white;
        border: none;
        border-radius: 50%;
        cursor: pointer;
        transition: all 0.2s ease;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    button:hover:not(:disabled) {
        background-color: #007d69;
        box-shadow: 0 0 10px rgba(0, 149, 125, 0.3);
        transform: scale(1.05);
    }

    .loading-indicator {
        display: flex;
        gap: 0.4rem;
        padding: 1rem;
        align-items: center;
    }

    .loading-indicator .dot {
        width: 0.5rem;
        height: 0.5rem;
        background-color: #2563eb;
        border-radius: 50%;
        animation: bounce 1.4s infinite ease-in-out;
    }

    .loading-indicator .dot:nth-child(1) { animation-delay: -0.32s; }
    .loading-indicator .dot:nth-child(2) { animation-delay: -0.16s; }

    @keyframes bounce {
        0%, 80%, 100% { transform: scale(0); }
        40% { transform: scale(1); }
    }

    /* Update mobile styles */
    @media (max-width: 768px) {
        .top-bar {
            position: absolute;
            padding: 0.4rem 1rem;
        }

        .input-container {
            position: absolute;
            padding: 0.8rem;
        }

        textarea {
            -webkit-appearance: none;
            appearance: none;
            font-size: 16px;
        }

        .fullscreen-btn {
            font-size: 1.25rem;
            width: 2rem;
            height: 2rem;
        }
    }

    /* Additional styles for very small screens */
    @media (max-width: 380px) {
        .chat-container {
            padding-top: calc(3rem + 0.3rem);
            padding-bottom: calc(5rem + 0.3rem);
        }

        .input-container {
            padding: 0.6rem;
        }
    }

    .fullscreen-btn {
        background: transparent;
        border: none;
        color: #e0e1e2;
        padding: 0.5rem;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: color 0.2s;
        width: 2.2rem;
        height: 2.2rem;
        border-radius: 0.5rem;
    }

    .fullscreen-btn:hover {
        color: #fff;
        background: rgba(255, 255, 255, 0.1);
    }

    .left-section {
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    .right-section {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .menu-btn, .icon-btn {
        background: transparent;
        border: none;
        color: #e0e1e2;
        padding: 0.5rem;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: color 0.2s;
        width: 2.2rem;
        height: 2.2rem;
        border-radius: 0.5rem;
    }

    .menu-btn:hover, .icon-btn:hover {
        color: #fff;
        background: rgba(255, 255, 255, 0.1);
    }

    .sidebar {
        position: fixed;
        top: 0;
        left: 0;
        height: 100vh;
        width: 260px;
        background: #18191c;
        z-index: 100;
        padding: 1rem;
        box-shadow: 0 0 20px rgba(0, 0, 0, 0.5);
        overflow-y: auto;
        -webkit-overflow-scrolling: touch;
        display: flex;
        flex-direction: column;
    }

    .sidebar-header {
        position: sticky;
        top: 0;
        background: #151a23;
        padding: 0.5rem 0;
        margin-bottom: 1.5rem;
        z-index: 1;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .sidebar-content {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 2rem;
        padding-bottom: 5rem;
        min-height: min-content;
    }

    .overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.7);
        z-index: 90;
        backdrop-filter: blur(3px);
    }

    .context-info h3, .mode-toggle h3 {
        margin: 0 0 1rem 0;
        font-size: 1rem;
        font-weight: 500;
    }

    .progress-bar {
        width: 100%;
        height: 6px;
        background: #2c2d31;
        border-radius: 3px;
        overflow: hidden;
        margin-bottom: 0.5rem;
    }

    .progress {
        height: 100%;
        background: #00957d;
        transition: width 0.3s ease;
    }

    .toggle-btn {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.75rem 1rem;
        border-radius: 0.5rem;
        background: #1b2531;
        border: none;
        color: #e0e1e2;
        cursor: pointer;
        transition: all 0.2s ease;
    }

    .toggle-btn.active {
        background: #00957d;
        color: #fff;
    }

    .close-btn {
        background: transparent;
        border: none;
        color: #e0e1e2;
        cursor: pointer;
        padding: 0.5rem;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: color 0.2s;
        width: 2rem;
        height: 2rem;
        border-radius: 0.5rem;
    }

    .close-btn:hover {
        color: #fff;
        background: rgba(255, 255, 255, 0.1);
    }

    @media (max-width: 768px) {
        .sidebar {
            width: 240px;
            height: 100dvh;
        }
    }
</style>
