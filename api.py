from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import json
import ollama
from typing import Iterator
from rhea import ChatManager, ConfigManager, Message, CharacterProfile

app = Flask(__name__)
CORS(app)

# Initialize managers as global objects
config_manager = ConfigManager()
chat_manager = ChatManager(
    model_name=config_manager.config.model_name,
    context_limit=config_manager.config.context_limit
)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message', '')
    should_stream = data.get('stream', True)  # Renamed from 'stream' to 'should_stream'

    if not message:
        return jsonify({"error": "Message is required"}), 400

    def generate_response() -> Iterator[str]:
        chat_manager.add_to_conversation("user", message)
        try:
            ollama_stream = ollama.chat(  # Renamed from 'stream' to 'ollama_stream'
                model=config_manager.config.model_name,
                messages=chat_manager.conversation,
                options={"num_ctx": config_manager.config.context_limit},
                stream=True,
            )
            
            response_content = []
            for chunk in ollama_stream:
                chunk_content = chunk['message']['content']
                response_content.append(chunk_content)
                if should_stream:  # Use should_stream instead of stream
                    yield f"data: {json.dumps({'chunk': chunk_content})}\n\n"
            
            full_response = ''.join(response_content)
            chat_manager.add_to_conversation("assistant", full_response)
            
            if not should_stream:
                yield f"data: {json.dumps({'response': full_response})}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    if should_stream:  # Use should_stream instead of stream
        return Response(
            stream_with_context(generate_response()),
            mimetype='text/event-stream'
        )
    else:
        response = "".join(generate_response())
        return jsonify({"response": response})

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

if __name__ == '__main__':
    app.run(debug=True) 