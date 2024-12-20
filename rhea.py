"""
Rhea - An Ollama-based Character Chat Interface

This module implements a character-based chat interface using the Ollama API.
It supports persistent configuration, character profiles, and streaming responses.

Configuration Structure (.rhea/config.json):
{
    "model_name": str,        # Ollama model name
    "context_limit": int,     # Maximum context length
    "refresh_rate": int,      # UI refresh rate
    "max_width": int         # Maximum display width
}

Character Profile Structure (.rhea/profiles.json):
{
    "role": {                 # "assistant" or "user"
        "name": str,          # Character name
        "traits": List[str],  # Character traits
        "backstory": str,     # Character background
        "goals": str,         # Character objectives
        "personality": str    # Character personality
    }
}

Usage:
1. Ensure Ollama is running with your desired model
2. Run the script: python rhea.py
3. Configure settings and profiles through the menu
4. Start chatting with your character!

Dependencies:
- ollama
- rich
- pathlib
- typing
- dataclasses
"""

import ollama
import json
import os
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.prompt import Prompt
from rich import box

@dataclass
class Message:
    role: str
    content: str
    
@dataclass
class CharacterProfile:
    name: str
    traits: List[str]
    backstory: str
    goals: str
    personality: str

@dataclass
class Configuration:
    model_name: str = "fluffy/l3-8b-stheno-v3.2:latest"
    context_limit: int = 5000
    refresh_rate: int = 4
    max_width: int = 120
    
class ConfigManager:
    def __init__(self):
        self.config = Configuration()
        self.config_dir = Path('.rhea')
        self.config_file = self.config_dir / 'config.json'
        self.profiles_file = self.config_dir / 'profiles.json'
        self._ensure_config_dir()
        self._create_default_files()
        self._load_config()
    
    def _ensure_config_dir(self) -> None:
        """Create configuration directory if it doesn't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self) -> None:
        """Load configuration from file if it exists."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                    self.config = Configuration(**config_data)
            except Exception as e:
                print(f"Error loading config: {e}")
    
    def save_config(self) -> None:
        """Save current configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config.__dict__, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def show_config_menu(self, console: Console) -> None:
        while True:
            console.clear()
            console.print("[bold blue]Configuration Menu[/bold blue]")
            console.print("\n1. Change Model Name (current: {})".format(self.config.model_name))
            console.print("2. Change Context Limit (current: {})".format(self.config.context_limit))
            console.print("3. Change Refresh Rate (current: {})".format(self.config.refresh_rate))
            console.print("4. Change Max Width (current: {})".format(self.config.max_width))
            console.print("5. Save and Return")
            
            choice = Prompt.ask("\nEnter your choice", default="5")
            
            if choice == "1":
                self.config.model_name = Prompt.ask("Enter new model name", default=self.config.model_name)
            elif choice == "2":
                try:
                    self.config.context_limit = int(Prompt.ask("Enter new context limit", default=str(self.config.context_limit)))
                except ValueError:
                    console.print("[red]Invalid input. Using default value.[/red]")
            elif choice == "3":
                try:
                    self.config.refresh_rate = int(Prompt.ask("Enter new refresh rate", default=str(self.config.refresh_rate)))
                except ValueError:
                    console.print("[red]Invalid input. Using default value.[/red]")
            elif choice == "4":
                try:
                    self.config.max_width = int(Prompt.ask("Enter new max width", default=str(self.config.max_width)))
                except ValueError:
                    console.print("[red]Invalid input. Using default value.[/red]")
            elif choice == "5":
                break
    
    def _create_default_files(self) -> None:
        """Create default configuration files if they don't exist."""
        # Create default config.json
        if not self.config_file.exists():
            default_config = {
                "model_name": "fluffy/l3-8b-stheno-v3.2:latest",
                "context_limit": 5000,
                "refresh_rate": 4,
                "max_width": 120
            }
            with open(self.config_file, 'w') as f:
                json.dump(default_config, f, indent=4)

        # Create default profiles.json
        if not self.profiles_file.exists():
            default_profiles = {
                "assistant": {
                    "name": "Assistant",
                    "traits": ["helpful", "friendly"],
                    "backstory": "A helpful AI assistant.",
                    "goals": "To help users effectively.",
                    "personality": "Professional and courteous."
                },
                "user": {
                    "name": "User",
                    "traits": ["human"],
                    "backstory": "A user of the system.",
                    "goals": "To interact with the assistant.",
                    "personality": "Regular user."
                }
            }
            with open(self.profiles_file, 'w') as f:
                json.dump(default_profiles, f, indent=4)

class ChatManager:
    def __init__(self, model_name: str = "fluffy/l3-8b-stheno-v3.2:latest", 
                 context_limit: int = 5000):
        self.model_name = model_name
        self.context_limit = context_limit
        self.conversation: List[Dict[str, str]] = []
        self.key_events: List[str] = []
        self.character_profiles: Dict[str, CharacterProfile] = {}
        self.profiles_file = Path('.rhea') / 'profiles.json'
        self.current_assistant_profile = None
        self.current_user_profile = None
        print(f"Looking for profiles at: {self.profiles_file}")  # Debug
        self._load_profiles()
        print(f"Loaded profiles: {list(self.character_profiles.keys())}")  # Debug
        if 'assistant' in self.character_profiles:
            self.current_assistant_profile = self.character_profiles['assistant']
        if 'user' in self.character_profiles:
            self.current_user_profile = self.character_profiles['user']
        self._initialize_conversation()
        self.message_count = 0
        self.last_cleanup = 0
        
    def _initialize_conversation(self):
        """Initialize the conversation with character context and key information."""
        system_message = self._create_system_message()
        self.conversation = [system_message]

    def _create_system_message(self) -> Dict[str, str]:
        """Create a system message that includes character context and key events."""
        if not self.current_assistant_profile:
            return {"role": "system", "content": "Basic AI assistant mode."}
        
        context = f"""You are {self.current_assistant_profile.name}. Fully embody this character:

        Your Identity:
        - Name: {self.current_assistant_profile.name}
        - Traits: {', '.join(self.current_assistant_profile.traits)}
        - Backstory: {self.current_assistant_profile.backstory}
        - Goals: {self.current_assistant_profile.goals}
        - Personality: {self.current_assistant_profile.personality}

        Your Context:
        - You are interacting with: {self.current_user_profile.name}
        - Their traits: {', '.join(self.current_user_profile.traits)}
        - Their backstory: {self.current_user_profile.backstory}
        
        Recent Events:
        {self._format_key_events()}

        Stay completely in character, using all elements from your profile to shape your responses."""
        
        return {"role": "system", "content": context}

    def add_key_event(self, event: str):
        """Add an important event or piece of information to remember."""
        self.key_events.append(event)
        # Update system message with new context
        self.conversation[0] = self._create_system_message()

    def _format_key_events(self) -> str:
        """Format key events for the system message."""
        if not self.key_events:
            return "No significant events yet."
        return "\n".join(f"- {event}" for event in self.key_events)

    def add_to_conversation(self, role: str, content: str) -> None:
        """Add a new message to the conversation."""
        if role == "user" and self.current_user_profile:
            profile_context = f"{self.current_user_profile.name}:\n{content}"
        elif role == "assistant" and self.current_assistant_profile:
            profile_context = f"{self.current_assistant_profile.name}:\n{content}"
        else:
            profile_context = content
        
        new_message = {"role": role, "content": profile_context}
        self.conversation.append(new_message)
        
        total_length = sum(len(msg["content"]) for msg in self.conversation)
        if total_length > self.context_limit * 0.75:
            num_msgs_to_keep = max(4, self.context_limit // 1000)
            self.conversation = [self.conversation[0]] + self.conversation[-num_msgs_to_keep:]
            
            if len(self.conversation) > 2:
                summary_msg = {
                    "role": "system",
                    "content": f"Previous conversation between {self.current_assistant_profile.name} and {self.current_user_profile.name} has been summarized."
                }
                self.conversation.insert(1, summary_msg)

    def _load_profiles(self) -> None:
        """Load character profiles from file."""
        if self.profiles_file.exists():
            print(f"Found profiles file at {self.profiles_file}")  # Debug
            try:
                with open(self.profiles_file, 'r', encoding='utf-8') as f:
                    profiles_data = json.load(f)
                    print(f"Loaded profiles data: {profiles_data}")  # Debug
                    self.character_profiles = {}
                    for role, profile_data in profiles_data.items():
                        self.character_profiles[role] = CharacterProfile(**profile_data)
                        print(f"Added profile for role: {role}")  # Debug
            except Exception as e:
                print(f"Error loading profiles: {str(e)}")
        else:
            print(f"No profiles file found at {self.profiles_file}")  # Debug

    def _save_profiles(self) -> None:
        """Save character profiles to file."""
        try:
            # Ensure the directory exists
            self.profiles_file.parent.mkdir(parents=True, exist_ok=True)
            
            profiles_data = {
                role: {
                    'name': profile.name,
                    'traits': profile.traits,
                    'backstory': profile.backstory,
                    'goals': profile.goals,
                    'personality': profile.personality
                }
                for role, profile in self.character_profiles.items()
            }
            print(f"Saving profiles to {self.profiles_file}")  # Debug
            print(f"Data to save: {profiles_data}")  # Debug
            
            with open(self.profiles_file, 'w', encoding='utf-8') as f:
                json.dump(profiles_data, f, indent=4)
            print("Profiles saved successfully")  # Debug
        except Exception as e:
            print(f"Error saving profiles: {str(e)}")

    def add_character_profile(self, role: str, profile: CharacterProfile) -> None:
        """Add a character profile and save to file."""
        print(f"Adding new profile for role: {role}")  # Debug
        self.character_profiles[role] = profile
        self._save_profiles()

    def set_current_profiles(self, user_role: str, assistant_role: str) -> None:
        """Set the current user and assistant profiles."""
        self.current_user_profile = self.character_profiles.get(user_role)
        self.current_assistant_profile = self.character_profiles.get(assistant_role)
        print(f"Set profiles - User: {self.current_user_profile.name if self.current_user_profile else 'None'}, Assistant: {self.current_assistant_profile.name if self.current_assistant_profile else 'None'}")

    def run_llm(self) -> bool:
        """
        Run the LLM with the current conversation.
        Returns True if successful, False if an error occurred.
        """
        try:
            stream = ollama.chat(
                model=self.model_name,
                messages=self.conversation,
                options={"num_ctx": self.context_limit},
                stream=True,
            )
            
            response_content = []
            for chunk in stream:
                chunk_content = chunk['message']['content']
                response_content.append(chunk_content)
                print(chunk_content, end='', flush=True)
            
            full_response = ''.join(response_content)
            self.add_to_conversation("assistant", full_response)
            return True
            
        except Exception as e:
            print(f"\nError: {str(e)}")
            return False

    def periodic_cleanup(self) -> None:
        """Perform periodic cleanup of conversation history"""
        self.message_count += 1
        
        # Every 50 messages, do a deep cleanup
        if self.message_count - self.last_cleanup >= 50:
            self.last_cleanup = self.message_count
            
            # Keep system message and last 25% of messages
            msgs_to_keep = max(4, len(self.conversation) // 4)
            self.conversation = [self.conversation[0]] + self.conversation[-msgs_to_keep:]
            
            # Force Python garbage collection
            import gc
            gc.collect()

class ChatInterface:
    def __init__(self, chat_manager: ChatManager):
        self.chat_manager = chat_manager
        self.console = Console()
        self.messages: List[Message] = []
        
    def format_messages(self, include_last_incomplete="", show_prompt=True):
        formatted = ""
        for msg in self.messages:
            if msg.role == "system":
                formatted += f"[bold yellow]{msg.content}[/bold yellow]\n\n"
            elif msg.role == "user":
                formatted += f"[bold blue]{self.chat_manager.current_user_profile.name}:[/bold blue] {msg.content}\n\n"
            elif msg.role == "assistant":
                formatted += f"[bold green]{self.chat_manager.current_assistant_profile.name}:[/bold green] {msg.content}\n\n"
        
        if include_last_incomplete:
            formatted += f"[bold green]{self.chat_manager.current_assistant_profile.name}:[/bold green] {include_last_incomplete}\n\n"
            
        if show_prompt:
            formatted += f"[bold blue]{self.chat_manager.current_user_profile.name}:[/bold blue] "
            
        return Panel(
            formatted,
            title="[bold blue]Character Chat[/bold blue]",
            title_align="left",
            border_style="bright_blue",
            box=box.ROUNDED,
            padding=(1, 2),
            width=min(120, self.console.width - 2)
        )

    def add_message(self, role: str, content: str):
        self.messages.append(Message(role=role, content=content))
        
# Test profile creation
# test_profile = CharacterProfile(
#     name="Test",
#     traits=["trait1", "trait2"],
#     backstory="Test backstory",
#     goals="Test goals",
#     personality="Test personality"
# )
# print(f"Profile created: {test_profile}")

def show_main_menu(console: Console) -> str:
    console.clear()
    console.print("[bold blue]Main Menu[/bold blue]")
    console.print("\n1. Start Chat")
    console.print("2. Configure Settings")
    console.print("3. Manage Character Profiles")
    console.print("4. Load Example Profiles")
    console.print("5. Exit")
    
    return Prompt.ask("\nEnter your choice", default="1")

def manage_profiles(chat_manager: ChatManager, console: Console) -> None:
    while True:
        console.clear()
        console.print("[bold blue]Character Profile Management[/bold blue]")
        console.print("\n1. View Current Profiles")
        console.print("2. Add New Profile")
        console.print("3. Delete Profile")
        console.print("4. Return to Main Menu")
        
        choice = Prompt.ask("\nEnter your choice", default="4")
        
        if choice == "1":
            if not chat_manager.character_profiles:
                console.print("[yellow]No profiles found.[/yellow]")
            else:
                for role, profile in chat_manager.character_profiles.items():
                    console.print(f"\n[bold]{role}[/bold]:")
                    console.print(f"Name: {profile.name}")
                    console.print(f"Traits: {', '.join(profile.traits)}")
                    console.print(f"Backstory: {profile.backstory}")
                    console.print(f"Goals: {profile.goals}")
                    console.print(f"Personality: {profile.personality}")
            Prompt.ask("\nPress Enter to continue")
            
        elif choice == "2":
            role = Prompt.ask("Enter role (user/assistant)")
            name = Prompt.ask("Enter name")
            traits = Prompt.ask("Enter traits (comma-separated)").split(",")
            backstory = Prompt.ask("Enter backstory")
            goals = Prompt.ask("Enter goals")
            personality = Prompt.ask("Enter personality")
            
            profile = CharacterProfile(
                name=name,
                traits=[t.strip() for t in traits],
                backstory=backstory,
                goals=goals,
                personality=personality
            )
            chat_manager.add_character_profile(role, profile)
            console.print("[green]Profile added successfully![/green]")
            Prompt.ask("\nPress Enter to continue")
            
        elif choice == "3":
            if not chat_manager.character_profiles:
                console.print("[yellow]No profiles to delete.[/yellow]")
            else:
                role = Prompt.ask("Enter role to delete", 
                                choices=list(chat_manager.character_profiles.keys()))
                if role in chat_manager.character_profiles:
                    del chat_manager.character_profiles[role]
                    chat_manager._save_profiles()
                    console.print("[green]Profile deleted successfully![/green]")
            Prompt.ask("\nPress Enter to continue")
            
        elif choice == "4":
            break

def select_characters(chat_manager: ChatManager, console: Console) -> tuple[str, str]:
    """Allow user to select characters from available profiles"""
    console.clear()
    console.print("[bold blue]Character Selection[/bold blue]\n")
    
    if not chat_manager.character_profiles:
        console.print("[yellow]No character profiles found. Please create profiles first.[/yellow]")
        return None, None
    
    # Show available profiles
    console.print("Available profiles:")
    for role, profile in chat_manager.character_profiles.items():
        console.print(f"{role}: {profile.name}")
    
    # Let user select profiles
    user_role = Prompt.ask("\nSelect user profile", 
                          choices=list(chat_manager.character_profiles.keys()))
    assistant_role = Prompt.ask("Select assistant profile", 
                              choices=list(chat_manager.character_profiles.keys()))
    
    chat_manager.set_current_profiles(user_role, assistant_role)
    
    if chat_manager.current_assistant_profile and chat_manager.current_user_profile:
        console.print("\n[green]Characters selected successfully:[/green]")
        console.print(f"AI is playing as: [bold]{chat_manager.current_assistant_profile.name}[/bold]")
        console.print(f"You are playing as: [bold]{chat_manager.current_user_profile.name}[/bold]")
    else:
        console.print("[red]Error setting up characters[/red]")
        
    Prompt.ask("\nPress Enter to continue")
    return user_role, assistant_role

def format_streaming_text(text: str) -> str:
    """Convert markdown-style formatting to Rich formatting."""
    # Replace **text** with [bold]text[/bold]
    while "**" in text:
        text = text.replace("**", "[bold]", 1)
        text = text.replace("**", "[/bold]", 1)
    
    # Replace *text* with [italic]text[/italic]
    while "*" in text:
        text = text.replace("*", "[italic]", 1)
        text = text.replace("*", "[/italic]", 1)
    
    # Replace _text_ with [underline]text[/underline]
    while "_" in text:
        text = text.replace("_", "[underline]", 1)
        text = text.replace("_", "[/underline]", 1)
    
    return text

def run_chat(interface: ChatInterface, chat_manager: ChatManager, config: Configuration) -> None:
    user_role, assistant_role = select_characters(chat_manager, interface.console)
    if user_role is None or assistant_role is None:
        interface.console.print("[red]Cannot start chat without character profiles.[/red]")
        Prompt.ask("\nPress Enter to return to menu")
        return
        
    chat_manager.set_current_profiles(user_role, assistant_role)
    
    welcome_msg = f"""Welcome to a conversation with {chat_manager.current_assistant_profile.name if chat_manager.current_assistant_profile else 'AI'}
    Type your messages below and press Enter. 
    Special commands:
    /key <event> - Add a key event to remember
    /events - Show current key events
    /exit - Exit chat"""
    
    interface.add_message("system", welcome_msg)
    
    while True:
        try:
            print("\033[2J\033[H", end="")
            interface.console.print(interface.format_messages(show_prompt=False))
            user_input = Prompt.ask("")
            
            if not user_input.strip():
                continue
                
            if user_input.startswith("/"):
                if user_input.startswith("/key "):
                    event = user_input[5:].strip()
                    chat_manager.add_key_event(event)
                    interface.add_message("system", f"Added key event: {event}")
                    continue
                elif user_input == "/events":
                    events = chat_manager._format_key_events()
                    interface.add_message("system", f"Key events:\n{events}")
                    continue
                elif user_input == "/exit":
                    break
            
            print("\033[2J\033[H", end="")
            interface.add_message("user", user_input)
            chat_manager.add_to_conversation("user", user_input)
            
            try:
                stream = ollama.chat(
                    model=config.model_name,
                    messages=chat_manager.conversation,
                    options={"num_ctx": config.context_limit},
                    stream=True,
                )
                
                current_response = ""
                with Live(
                    interface.format_messages(current_response, show_prompt=False),
                    refresh_per_second=config.refresh_rate,
                    transient=False,
                    auto_refresh=True,
                    vertical_overflow="visible"
                ) as live:
                    for chunk in stream:
                        chunk_content = chunk['message']['content']
                        current_response += chunk_content
                        formatted_response = format_streaming_text(current_response)
                        live.update(interface.format_messages(formatted_response, show_prompt=False))
                        print("\033[9999B", end="", flush=True)
                        print("\033[A" * 1, end="", flush=True)
                
                interface.add_message("assistant", current_response)
                chat_manager.add_to_conversation("assistant", current_response)
                
            except Exception as e:
                error_msg = f"""Connection Error 🔌
Please ensure Ollama is running with: ollama run {config.model_name}
Error details: {str(e)}"""
                interface.add_message("system", error_msg)
                continue
                
        except KeyboardInterrupt:
            raise
        except Exception as e:
            interface.add_message("system", f"Error: {str(e)}")

def create_example_profiles(chat_manager: ChatManager) -> None:
    """Create basic template profiles for first-time setup."""
    # Basic Assistant Profile
    assistant_profile = CharacterProfile(
        name="Assistant",
        traits=["helpful", "professional", "knowledgeable"],
        backstory="A helpful AI assistant.",
        goals="To assist users effectively and professionally.",
        personality="Professional and courteous."
    )

    # Basic User Profile
    user_profile = CharacterProfile(
        name="User",
        traits=["user"],
        backstory="A user of the system.",
        goals="To interact with the assistant.",
        personality="Standard user."
    )

    # Add profiles to chat manager
    chat_manager.add_character_profile("assistant", assistant_profile)
    chat_manager.add_character_profile("user", user_profile)
    
    return "Basic profile templates created successfully!"

def main():
    console = Console()
    config_manager = ConfigManager()
    chat_manager = ChatManager(
        model_name=config_manager.config.model_name,
        context_limit=config_manager.config.context_limit
    )
    
    while True:
        choice = show_main_menu(console)
        
        if choice == "1":
            # Start chat
            if not chat_manager.character_profiles:
                console.print("[yellow]No character profiles found. Please create profiles first.[/yellow]")
                Prompt.ask("\nPress Enter to continue")
                continue
                
            interface = ChatInterface(chat_manager)
            try:
                run_chat(interface, chat_manager, config_manager.config)
            except Exception as e:
                console.print(f"[red]Error: {str(e)}[/red]")
                Prompt.ask("\nPress Enter to continue")
                
        elif choice == "2":
            config_manager.show_config_menu(console)
            
        elif choice == "3":
            manage_profiles(chat_manager, console)
            
        elif choice == "4":
            console.print("\n[yellow]Please create your own profiles through the profile management menu.[/yellow]")
            Prompt.ask("\nPress Enter to continue")
            
        elif choice == "5":
            console.print("\nGoodbye! 👋")
            break

if __name__ == "__main__":
    main()

