from flask import Flask
from flask_sock import Sock
from flask_cors import CORS
import json
import ollama
from typing import Iterator
from rhea import ChatManager, ConfigManager, Message, CharacterProfile

app = Flask(__name__)
CORS(app)
sock = Sock(app)

# Initialize managers as global objects
config_manager = ConfigManager()
chat_manager = ChatManager(
    model_name=config_manager.config.model_name,
    context_limit=config_manager.config.context_limit
)

@sock.route('/ws')
def chat(ws):
    fast_mode = False  # Initialize fast mode flag
    
    # Initialize character profiles
    chat_manager.set_current_profiles("user", "assistant")
    
    # Force reinitialize the conversation with full character context
    chat_manager.conversation = []  # Clear any existing conversation
    system_message = chat_manager._create_system_message()  # Create fresh system message with full context
    chat_manager.conversation = [system_message]  # Set as first message
    
    # Send initial profile confirmation
    ws.send(json.dumps({
        'system': f"Chat initialized. You are {chat_manager.current_user_profile.name}, speaking with {chat_manager.current_assistant_profile.name}"
    }))
    
    while True:
        data = json.loads(ws.receive())
        message = data.get('message', '')

        # Handle fast mode toggle
        if data.get('toggle_fast_mode') is not None:
            fast_mode = data['toggle_fast_mode']
            ws.send(json.dumps({
                'system': f"Fast mode {'enabled' if fast_mode else 'disabled'}"
            }))
            continue

        if not message:
            ws.send(json.dumps({"error": "Message is required"}))
            continue

        try:
            # Format message with character name
            user_message = f"{chat_manager.current_user_profile.name}:\n{message}"
            chat_manager.add_to_conversation("user", user_message)

            # Ensure system message is always first
            if not chat_manager.conversation[0]['role'] == 'system':
                chat_manager.conversation.insert(0, system_message)

            ollama_stream = ollama.chat(
                model=config_manager.config.model_name,
                messages=chat_manager.conversation,
                options={"num_ctx": config_manager.config.context_limit},
                stream=True,
            )
            
            full_response = []
            for chunk in ollama_stream:
                chunk_content = chunk['message']['content']
                full_response.append(chunk_content)
                ws.send(json.dumps({
                    'chunk': chunk_content,
                    'character': chat_manager.current_assistant_profile.name
                }))
            
            # Store the complete response with character name
            complete_response = ''.join(full_response)
            assistant_message = f"{chat_manager.current_assistant_profile.name}:\n{complete_response}"
            chat_manager.add_to_conversation("assistant", assistant_message)
            
        except Exception as e:
            ws.send(json.dumps({'error': str(e)}))

@app.route('/api/config', methods=['GET', 'PUT'])
def handle_config():
    if request.method == 'GET':
        return jsonify(config_manager.config.__dict__)
    
    data = request.json
    for key, value in data.items():
        if hasattr(config_manager.config, key):
            setattr(config_manager.config, key, value)
    config_manager.save_config()
    return jsonify(config_manager.config.__dict__)

@app.route('/api/profiles', methods=['GET', 'POST', 'DELETE'])
def handle_profiles():
    if request.method == 'GET':
        profiles = {
            role: {
                'name': profile.name,
                'traits': profile.traits,
                'backstory': profile.backstory,
                'goals': profile.goals,
                'personality': profile.personality
            }
            for role, profile in chat_manager.character_profiles.items()
        }
        return jsonify(profiles)
    
    elif request.method == 'POST':
        data = request.json
        role = data.get('role')
        profile_data = data.get('profile')
        if not role or not profile_data:
            return jsonify({"error": "Role and profile data required"}), 400
        
        profile = CharacterProfile(**profile_data)
        chat_manager.add_character_profile(role, profile)
        return jsonify({"message": f"Profile added for {role}"})
    
    elif request.method == 'DELETE':
        role = request.args.get('role')
        if not role:
            return jsonify({"error": "Role parameter required"}), 400
        
        if role in chat_manager.character_profiles:
            del chat_manager.character_profiles[role]
            chat_manager._save_profiles()
            return jsonify({"message": f"Profile deleted for {role}"})
        return jsonify({"error": "Profile not found"}), 404

@app.route('/api/events', methods=['GET', 'POST'])
def handle_events():
    if request.method == 'GET':
        return jsonify({"events": chat_manager.key_events})
    
    data = request.json
    event = data.get('event')
    if not event:
        return jsonify({"error": "Event content required"}), 400
    
    chat_manager.add_key_event(event)
    return jsonify({"message": "Event added", "events": chat_manager.key_events})

# Add a new endpoint to get current character information
@app.route('/api/characters/current', methods=['GET'])
def get_current_characters():
    return jsonify({
        'assistant': {
            'name': chat_manager.current_assistant_profile.name,
            'traits': chat_manager.current_assistant_profile.traits,
            'personality': chat_manager.current_assistant_profile.personality
        } if chat_manager.current_assistant_profile else None,
        'user': {
            'name': chat_manager.current_user_profile.name,
            'traits': chat_manager.current_user_profile.traits,
            'personality': chat_manager.current_user_profile.personality
        } if chat_manager.current_user_profile else None
    })

@app.route('/api/clear', methods=['POST'])
def clear_conversation():
    try:
        # Reset the conversation to just the system message
        chat_manager.conversation = []
        system_message = chat_manager._create_system_message()
        chat_manager.conversation = [system_message]
        
        return jsonify({
            "message": "Conversation history cleared",
            "status": "success"
        })
    except Exception as e:
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500

# Add these new routes for context management
@app.route('/api/context/status', methods=['GET'])
def get_context_status():
    total_tokens = sum(len(msg['content'].split()) for msg in chat_manager.conversation)
    return jsonify({
        "total_tokens": total_tokens,
        "context_limit": config_manager.config.context_limit,
        "usage_percentage": (total_tokens / config_manager.config.context_limit) * 100
    })

@app.route('/api/context/trim', methods=['POST'])
def trim_context():
    data = request.json
    target_percentage = data.get('target_percentage', 50)
    
    # Keep system message and calculate target token count
    system_message = chat_manager.conversation[0]
    target_tokens = (config_manager.config.context_limit * target_percentage) / 100
    
    # Start fresh with system message
    new_conversation = [system_message]
    current_tokens = len(system_message['content'].split())
    
    # Add messages from the end (most recent) until we hit target
    for message in reversed(chat_manager.conversation[1:]):
        message_tokens = len(message['content'].split())
        if current_tokens + message_tokens <= target_tokens:
            new_conversation.insert(1, message)  # Insert after system message
            current_tokens += message_tokens
        else:
            break
    
    chat_manager.conversation = new_conversation
    
    return jsonify({
        "message": "Context trimmed successfully",
        "remaining_messages": len(chat_manager.conversation),
        "current_usage_percentage": (current_tokens / config_manager.config.context_limit) * 100
    })

if __name__ == '__main__':
    app.run(debug=True, port=3000, host='0.0.0.0') 