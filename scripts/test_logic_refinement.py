import requests
import json
import uuid

BASE_URL = "http://localhost:8000"

def test_chat_logic():
    # 1. Signup/Login (assume already done or use existing test user)
    # Since I don't have the token here easily without re-running signup, 
    # I'll try to just check if the models/constants were updated correctly in a dry run logic check
    # But better to actually test the endpoint.
    
    print("Testing backend logic refinement...")
    
    # Test signup to get a fresh token
    user_id = str(uuid.uuid4())[:8]
    signup_data = {
        "email": f"test_{user_id}@example.com",
        "username": f"user_{user_id}",
        "password": "password123",
        "full_name": "Logic Tester"
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/api/auth/signup", json=signup_data)
        if resp.status_code != 200:
            print(f"Signup failed: {resp.text}")
            return
        
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Test Chat (Streaming)
        chat_data = {
            "message": "Hello, are you working smoothly?",
            "stream": True,
            "provider": "google" # Test the refined Gemini model name
        }
        
        print("Sending chat request with Gemini...")
        resp = requests.post(f"{BASE_URL}/api/chat", json=chat_data, headers=headers, stream=True)
        
        if resp.status_code != 200:
            print(f"Chat failed with Gemini: {resp.text}")
            # Try fallback
            print("Trying with Groq (fallback logic test)...")
            chat_data["provider"] = "groq"
            resp = requests.post(f"{BASE_URL}/api/chat", json=chat_data, headers=headers, stream=True)
        
        if resp.status_code == 200:
            print("Chat endpoint OK (Streaming started)")
            for line in resp.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith("data: "):
                        data = json.loads(decoded[6:])
                        if data.get("type") == "delta":
                            print(".", end="", flush=True)
                        if data.get("type") == "final":
                            print("\nFinal message received.")
                            break
        else:
            print(f"Chat failed again: {resp.text}")
            
    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    test_chat_logic()
