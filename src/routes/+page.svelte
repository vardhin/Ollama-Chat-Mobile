<script>
    import { onMount } from 'svelte';
    import { fade } from 'svelte/transition';

    let messages = [];
    let inputMessage = '';
    let chatContainer;
    let isLoading = false;

    async function sendMessage() {
        if (!inputMessage.trim()) return;

        // Add user message
        const messageId = Date.now().toString(); // Unique ID for each message
        messages = [...messages, { id: messageId, role: 'user', content: inputMessage }];
        const userMessage = inputMessage;
        inputMessage = '';
        isLoading = true;

        // Auto-scroll to bottom
        setTimeout(() => {
            chatContainer?.scrollTo({
                top: chatContainer.scrollHeight,
                behavior: 'smooth'
            });
        }, 100);

        try {
            const response = await fetch('http://localhost:5000/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: userMessage, stream: true })
            });

            if (!response.ok) throw new Error('Network response was not ok');

            // Add assistant message placeholder with unique ID
            const assistantMessageId = (Date.now() + 1).toString();
            messages = [...messages, { id: assistantMessageId, role: 'assistant', content: '' }];
            
            const reader = response.body?.getReader();
            const decoder = new TextDecoder();

            while (reader) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.chunk) {
                                // Update the message content without recreating the entire messages array
                                const lastMessage = messages[messages.length - 1];
                                lastMessage.content += data.chunk;
                                messages = messages; // Trigger reactivity
                                
                                // Auto-scroll while receiving chunks
                                chatContainer?.scrollTo({
                                    top: chatContainer.scrollHeight,
                                    behavior: 'smooth'
                                });
                            }
                        } catch (e) {
                            console.error('Error parsing SSE data:', e);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Error:', error);
            messages = [...messages, { 
                id: Date.now().toString(),
                role: 'assistant', 
                content: 'Sorry, there was an error processing your request.' 
            }];
        } finally {
            isLoading = false;
        }
    }

    function handleKeydown(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    }
</script>

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

<style>
    .chat-container {
        display: flex;
        flex-direction: column;
        height: 100vh;
        max-width: 800px;
        margin: 0 auto;
        padding: 1rem;
        box-sizing: border-box;
    }

    .messages {
        flex: 1;
        overflow-y: auto;
        padding: 1rem;
        display: flex;
        flex-direction: column;
        gap: 1rem;
        margin-bottom: 1rem;
    }

    .message {
        display: flex;
        align-items: flex-start;
        animation: fadeIn 0.3s ease-out;
    }

    .message.user {
        justify-content: flex-end;
    }

    .message-content {
        max-width: 80%;
        padding: 0.8rem 1rem;
        border-radius: 1rem;
        white-space: pre-wrap;
        word-break: break-word;
    }

    .user .message-content {
        background-color: #007AFF;
        color: white;
        border-radius: 1rem 1rem 0 1rem;
    }

    .assistant .message-content {
        background-color: #E9ECEF;
        color: black;
        border-radius: 1rem 1rem 1rem 0;
    }

    .input-container {
        display: flex;
        gap: 0.5rem;
        padding: 1rem;
        background-color: white;
        border-top: 1px solid #E9ECEF;
        position: sticky;
        bottom: 0;
    }

    textarea {
        flex: 1;
        padding: 0.8rem;
        border: 1px solid #E9ECEF;
        border-radius: 0.5rem;
        resize: none;
        font-family: inherit;
        font-size: 1rem;
        line-height: 1.5;
        max-height: 150px;
    }

    button {
        padding: 0.8rem 1.5rem;
        background-color: #007AFF;
        color: white;
        border: none;
        border-radius: 0.5rem;
        cursor: pointer;
        font-weight: 500;
        transition: opacity 0.2s;
    }

    button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    .loading-indicator {
        display: flex;
        gap: 0.3rem;
        padding: 1rem;
        justify-content: center;
    }

    .dot {
        width: 8px;
        height: 8px;
        background-color: #007AFF;
        border-radius: 50%;
        animation: bounce 1.4s infinite ease-in-out;
    }

    .dot:nth-child(1) { animation-delay: -0.32s; }
    .dot:nth-child(2) { animation-delay: -0.16s; }

    @keyframes bounce {
        0%, 80%, 100% { transform: scale(0); }
        40% { transform: scale(1); }
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* Mobile Responsiveness */
    @media (max-width: 768px) {
        .chat-container {
            padding: 0.5rem;
        }

        .message-content {
            max-width: 85%;
            padding: 0.6rem 0.8rem;
            font-size: 0.95rem;
        }

        .input-container {
            padding: 0.8rem;
        }

        textarea {
            padding: 0.6rem;
        }

        button {
            padding: 0.6rem 1.2rem;
        }
    }
</style>
