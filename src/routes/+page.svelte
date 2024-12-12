<script>
    import { onMount } from 'svelte';
    import { fade } from 'svelte/transition';

    let messages = [];
    let inputMessage = '';
    let chatContainer;
    let isLoading = false;
    let socket;

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
                    lastMessage.content += data.chunk;
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

                // If we receive an empty chunk, it's the end of the stream
                if (data.chunk === '') {
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
</script>

<div class="app-container">
    <header class="top-bar">
        <h1>{title}</h1>
    </header>
    
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
                Send
            </button>
        </div>
    </div>
</div>

<style>
    /* Update font import */
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@300;400;500;600;700&display=swap');

    :global(body) {
        margin: 0;
        background-color: #1a1b1e;
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

    .app-container {
        height: 100vh;
        display: flex;
        flex-direction: column;
    }

    .top-bar {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        background: rgba(44, 45, 49, 0.4);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        padding: 1rem 2rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        z-index: 10;
    }

    .top-bar h1 {
        margin: 0;
        font-size: 1.5rem;
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
        padding-top: calc(4rem + 1rem); /* Increased padding-top */
        padding-bottom: calc(5rem + 1rem); /* Increased padding-bottom */
    }

    .messages {
        height: calc(100vh - 10rem); /* Decreased height by increasing subtraction */
        padding: 1rem;
        display: flex;
        flex-direction: column;
        gap: 1rem;
        background-color: #1a1b1e;
        border-radius: 0.75rem;
        overflow-y: auto;
        scroll-behavior: smooth;
        scrollbar-width: none;
        -ms-overflow-style: none;
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
    }

    .user .message-content {
        background-color: #2563eb;
        color: white;
        border-bottom-right-radius: 0.25rem;
    }

    .assistant .message-content {
        background-color: #2c2d31;
        color: #e0e1e2;
        border-bottom-left-radius: 0.25rem;
    }

    .input-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: rgba(44, 45, 49, 0.4);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-top: 1px solid rgba(255, 255, 255, 0.1);
        padding: 1rem 1.5rem;
        z-index: 10;
        display: flex;
        gap: 0.75rem;
        align-items: flex-end;
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
        min-height: 24px;
        max-height: 90px; /* Reduced to 3 lines */
        padding: 0.75rem;
        background-color: #1a1b1e;
        color: #e0e1e2;
        border: 1px solid #383a3f;
        border-radius: 0.5rem;
        resize: none;
        font-family: 'Quicksand', sans-serif;
        font-size: 0.95rem;
        line-height: 1.5;
        transition: border-color 0.2s, height 0.15s ease-out;
        overflow-y: auto;
    }

    textarea:focus {
        outline: none;
        border-color: #2563eb;
    }

    button {
        padding: 0.75rem 1.5rem;
        background-color: #2563eb;
        color: white;
        border: none;
        border-radius: 0.5rem;
        font-size: 0.95rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
        font-family: 'Quicksand', sans-serif;
    }

    button:hover:not(:disabled) {
        background-color: #1d4ed8;
    }

    button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
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
            padding: 0.75rem 1rem;
        }

        .chat-container {
            padding-top: calc(4rem + 0.5rem);
            padding-bottom: calc(5rem + 0.5rem);
        }

        .input-container {
            padding: 0.8rem;
        }

        .messages {
            padding: 0.75rem;
            gap: 0.75rem;
        }
    }

    /* Additional styles for very small screens */
    @media (max-width: 380px) {
        .chat-container {
            padding-top: calc(4rem + 0.3rem);
            padding-bottom: calc(5rem + 0.3rem);
        }

        .input-container {
            padding: 0.6rem;
        }
    }
</style>
