import os
import tiktoken
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables (API Key)
load_dotenv()

# Initialize the tiktoken tokenizer (cl100k_base is typically used by modern models)
tokenizer = tiktoken.get_encoding("cl100k_base")

class ContextAwareChatBot:
    def __init__(self, max_history_tokens=200, existing_history=None):
        """
        Initializes the chatbot.
        max_history_tokens is set deliberately low in the demo to show the summarization feature.
        """
        self.max_history_tokens = max_history_tokens
        
        # Initialize Gemini GenAI client
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("Warning: GEMINI_API_KEY is not set in the environment or .env file.")
        
        self.client = genai.Client(api_key=api_key)
        
        # --- Prompt Engineering Task ---
        # Context-aware system prompt template with strict instructions on 
        # non-repetition, hallucination avoidance, and asking for clarification.
        self.system_instruction = (
            "You are a helpful and intelligent AI assistant. "
            "Follow these critical rules:\n"
            "1. Be contextual: Pay strict attention to pronouns (e.g., 'it', 'they') and references from previous interactions.\n"
            "2. Avoid repetition: Do not repeat previous answers verbatim if the user asks variations of the same question.\n"
            "3. Prevent hallucination: If you do not know the answer or lack sufficient context, DO NOT guess.\n"
            "4. Ask for clarification: Explicitly ask the user for clarification if the request is vague, ambiguous, or you are unsure.\n"
        )
        
        # Maintain chat history
        self.history = existing_history if existing_history is not None else []
        
    def count_tokens(self, text: str) -> int:
        """Counts tokens in a text using tiktoken."""
        return len(tokenizer.encode(text))
        
    def get_history_token_count(self) -> int:
        """Calculates total tokens currently used in conversation history."""
        total = 0
        for msg in self.history:
            for part in msg.get('parts', []):
                total += self.count_tokens(part.get('text', ''))
        return total
        
    def summarize_history(self):
        """
        Token Optimization Strategy:
        Summarizes older messages to free up context window tokens.
        Leaves the most recent turns intact for immediate conversation flow.
        """
        if len(self.history) <= 4:
            # We need enough history to make summarizing worth it without losing immediate context
            return
            
        # Keep the last 4 conversational turns (2 from user, 2 from model ideally)
        keep_recent = 4
        messages_to_summarize = self.history[:-keep_recent]
        recent_messages = self.history[-keep_recent:]
        
        # Create a single textual block of older messages
        old_text = "\n".join([f"{msg['role']}: {msg['parts'][0]['text']}" for msg in messages_to_summarize])
        
        prompt = (
            "Please concisely summarize the following older conversation history. "
            "Retain the key facts, topics discussed, and the overall context so it can be used "
            "as memory for an AI assistant. Do not answer the user, just summarize the conversation:\n\n"
            f"{old_text}"
        )
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            
            # Formulate the summary as a system/context note (injected via user role so API accepts it)
            summary_text = f"[System Context Optimization: Earlier conversation summarized as: {response.text}]"
            
            # Reconstruct history: The new summary context + recent message flow
            self.history = [{'role': 'user', 'parts': [{'text': summary_text}]}, 
                            {'role': 'model', 'parts': [{'text': 'Understood, retaining this context.'}]}] + recent_messages
            
            print(f"\n[System: Context footprint exceeded {self.max_history_tokens} tokens. Older messages summarized to optimize token window.]\n")
            
        except Exception as e:
            print(f"\n[System: Failed to summarize history: {e}]\n")

    def chat(self, user_input: str) -> str:
        """Handle incoming chat message, contextualize, and return response."""
        
        # 1. Context Window Handling & Token Optimization
        if len(self.history) > 0 and self.get_history_token_count() > self.max_history_tokens:
            self.summarize_history()
            
        # 2. Append new user message to history
        self.history.append({'role': 'user', 'parts': [{'text': user_input}]})
        
        try:
            # 3. Request completion using standard LLM API
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=self.history,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    temperature=0.7 # Slight temperature to balance conciseness and conversational ability
                )
            )
            
            response_text = response.text
            
            # 4. Append the response to maintain conversation history
            self.history.append({'role': 'model', 'parts': [{'text': response_text}]})
            
            return response_text
            
        except Exception as e:
            # If an error occurs, pop the last user input so we don't skew the history array
            self.history.pop()
            return f"Error communicating with LLM API: {e}"

def demo():
    """
    Demonstrates multi-turn conversation and context retention.
    """
    print("=" * 60)
    print("Context-Aware Chatbot Demo Initialized")
    print("Settings: In-memory History, Active Summarization (Max Context = 200 tokens)")
    print("=" * 60)
    print("Type 'quit' or 'exit' to end the session.\n")
    print("Try the following sequence to test demonstration context retention:")
    print('  1. "Tell me about Python"')
    print('  2. "What are its advantages?" (Should know "its" refers to Python)')
    print('  3. "Can you provide a code example for that?"')
    print("=" * 60 + "\n")
    
    # We set a low token threshold (200 tokens) to force token optimization to trigger quickly during demo
    bot = ContextAwareChatBot(max_history_tokens=200)
    
    while True:
        try:
            user_input = input("User >> ")
            if user_input.strip().lower() in ['quit', 'exit']:
                print("\nSession ended. Goodbye!")
                break
            
            if not user_input.strip():
                continue
                
            response = bot.chat(user_input)
            print(f"\nBot  >> {response}\n")
            
        except KeyboardInterrupt:
            print("\nSession ended. Goodbye!")
            break

if __name__ == "__main__":
    demo()
