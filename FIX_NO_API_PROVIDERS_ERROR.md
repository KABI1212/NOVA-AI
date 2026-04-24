# 🔧 Fix: "No AI Providers Available" Error

## Problem
Your system shows: **"No AI providers available. Please configure at least one API key."**

This means the NOVA-AI system cannot find any API keys in your environment.

---

## ✅ Solution (Step by Step)

### Step 1: Verify Environment Variables Are Set

#### Check Current Environment
```bash
# Check if API keys are set
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY
echo $DEEPSEEK_API_KEY
echo $GOOGLE_API_KEY
echo $META_API_KEY

# If these return empty, your keys are not set
```

#### If Empty, Set Them Now
```bash
# Method 1: Set individually (temporary - expires when terminal closes)
export OPENAI_API_KEY="sk-proj-YOUR_ACTUAL_KEY_HERE"
export ANTHROPIC_API_KEY="sk-ant-YOUR_ACTUAL_KEY_HERE"
export DEEPSEEK_API_KEY="sk-YOUR_ACTUAL_KEY_HERE"
export GOOGLE_API_KEY="YOUR_ACTUAL_KEY_HERE"

# Method 2: Using .env file (BETTER - permanent)
cd /path/to/your/nova-ai/project
nano config.env  # or .env

# Add your keys:
# OPENAI_API_KEY=sk-proj-...
# ANTHROPIC_API_KEY=sk-ant-...
# etc.
```

---

### Step 2: Create/Update Your .env File

#### Option A: Using config.env (Already Provided)

```bash
# Navigate to project directory
cd /path/to/nova-ai

# Edit the existing config.env file
nano config.env
# or
vim config.env
# or use your text editor

# Find the API KEYS section and add your actual keys:
# ============================================================================
# API KEYS (Set these as environment variables)
# ============================================================================

OPENAI_API_KEY=sk-proj-YOUR_OPENAI_KEY_HERE
ANTHROPIC_API_KEY=sk-ant-YOUR_ANTHROPIC_KEY_HERE
DEEPSEEK_API_KEY=sk-YOUR_DEEPSEEK_KEY_HERE
GOOGLE_API_KEY=YOUR_GOOGLE_GEMINI_KEY_HERE
META_API_KEY=YOUR_META_API_KEY_HERE

# Save file (Ctrl+X, then Y, then Enter for nano)
```

#### Option B: Create New .env File

```bash
# Create new .env file in project root
cat > .env << EOF
OPENAI_API_KEY=sk-proj-YOUR_OPENAI_KEY_HERE
ANTHROPIC_API_KEY=sk-ant-YOUR_ANTHROPIC_KEY_HERE
DEEPSEEK_API_KEY=sk-YOUR_DEEPSEEK_KEY_HERE
GOOGLE_API_KEY=YOUR_GOOGLE_GEMINI_KEY_HERE
META_API_KEY=YOUR_META_API_KEY_HERE
EOF

# Verify it was created
cat .env
```

---

### Step 3: Load Environment Variables in Python

#### Method A: Using python-dotenv (RECOMMENDED)

```python
from dotenv import load_dotenv
import os

# Load variables from .env file
load_dotenv()

# Now access them
openai_key = os.getenv("OPENAI_API_KEY")
anthropic_key = os.getenv("ANTHROPIC_API_KEY")

print(f"OpenAI Key: {openai_key[:10]}..." if openai_key else "Not set")
print(f"Anthropic Key: {anthropic_key[:10]}..." if anthropic_key else "Not set")
```

#### Method B: Direct Environment Variables

```python
import os

# If you've already exported in terminal, access directly
openai_key = os.getenv("OPENAI_API_KEY")
anthropic_key = os.getenv("ANTHROPIC_API_KEY")

if not openai_key:
    print("ERROR: OPENAI_API_KEY not set!")
```

#### Method C: Modify nova_ai_system.py

Add this at the top of `nova_ai_system.py`:

```python
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Now the system will find your keys
```

---

### Step 4: Fix the Code

#### In nova_ai_system.py, add this after imports:

```python
import os
from dotenv import load_dotenv

# Add this line (around line 10-15)
load_dotenv()  # ← THIS LINE IS KEY!

# Then the rest of your imports...
import asyncio
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re
from abc import ABC, abstractmethod
```

#### Complete Starting Section Should Look Like:

```python
"""
NOVA-AI: Multi-Model AI Analysis & Response System (2025-2026)
Advanced AI Chatbot with Multi-Model Analysis, Error Handling & CodeX Prompts
"""

import os
from dotenv import load_dotenv  # ← ADD THIS IMPORT

# Load .env file FIRST
load_dotenv()  # ← ADD THIS LINE

# Rest of imports
import json
import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re
from abc import ABC, abstractmethod

# ... rest of the code
```

---

## 🎯 Quick Fix Checklist

### ✅ IMMEDIATE FIX (Do This First)

```bash
# 1. Navigate to project
cd /path/to/nova-ai

# 2. Check if .env exists
ls -la .env config.env

# 3. If not, create it
cat > .env << EOF
OPENAI_API_KEY=sk-proj-YOUR_KEY_HERE
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
DEEPSEEK_API_KEY=sk-YOUR_KEY_HERE
GOOGLE_API_KEY=YOUR_KEY_HERE
EOF

# 4. Add load_dotenv() to nova_ai_system.py (see above)

# 5. Test it
python example_nova_ai.py
```

### ✅ VERIFY API KEYS ARE LOADED

Create a test file: `test_keys.py`

```python
import os
from dotenv import load_dotenv

# Load variables
load_dotenv()

# Test each provider
providers = {
    "OPENAI_API_KEY": "OpenAI",
    "ANTHROPIC_API_KEY": "Anthropic",
    "DEEPSEEK_API_KEY": "DeepSeek",
    "GOOGLE_API_KEY": "Google",
    "META_API_KEY": "Meta"
}

print("API KEY STATUS:")
print("=" * 50)

has_any_key = False
for env_var, provider_name in providers.items():
    key = os.getenv(env_var)
    if key:
        hint = f"{key[:8]}...{key[-4:]}"
        print(f"✓ {provider_name:<15} {hint}")
        has_any_key = True
    else:
        print(f"✗ {provider_name:<15} NOT SET")

print("=" * 50)

if has_any_key:
    print("✓ SUCCESS: At least one API key is configured!")
else:
    print("✗ ERROR: No API keys found. Please configure at least one.")
    print("\nHow to fix:")
    print("1. Edit .env file")
    print("2. Add your API keys")
    print("3. Save and run again")
```

Run it:
```bash
python test_keys.py
```

---

## 🔑 Where to Get API Keys

### OpenAI
1. Go to https://platform.openai.com/api-keys
2. Create new secret key
3. Copy the key (starts with `sk-proj-`)

### Anthropic
1. Go to https://console.anthropic.com/
2. Get API key
3. Copy the key (starts with `sk-ant-`)

### DeepSeek
1. Go to https://platform.deepseek.com/api
2. Create API key
3. Copy the key

### Google Gemini
1. Go to https://ai.google.dev/
2. Create API key
3. Copy the key

### Meta Llama
1. Go to https://www.together.ai/
2. Create API key
3. Copy the key

---

## 🚨 Common Mistakes

### ❌ Mistake 1: Key Not in .env File

```bash
# WRONG - key not in file
cat .env
# (empty or no OPENAI_API_KEY line)

# RIGHT - key is in file
cat .env
# OPENAI_API_KEY=sk-proj-abcd1234...
```

### ❌ Mistake 2: load_dotenv() Not Called

```python
# WRONG - code doesn't call load_dotenv()
import os
api_key = os.getenv("OPENAI_API_KEY")  # Returns None!

# RIGHT - load_dotenv() is called first
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")  # Returns the key!
```

### ❌ Mistake 3: Wrong Environment Variable Name

```bash
# WRONG
export openai_api_key="sk-proj-..."  # lowercase

# RIGHT
export OPENAI_API_KEY="sk-proj-..."  # uppercase
```

### ❌ Mistake 4: Key Format Wrong

```bash
# WRONG - just pasting key without checking format
OPENAI_API_KEY=my-super-secret-key

# RIGHT - use actual key format
OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz

# RIGHT - key formats by provider
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=sk-...
```

---

## 📋 Full Example: Step-by-Step Setup

### Step 1: Create .env File

```bash
cd ~/nova-ai  # or wherever your project is

cat > .env << 'EOF'
# ============================================================================
# NOVA-AI API KEYS CONFIGURATION
# ============================================================================
# Add your actual API keys here. Never commit this file to git!

# OpenAI (https://platform.openai.com/api-keys)
OPENAI_API_KEY=sk-proj-YOUR_ACTUAL_OPENAI_KEY

# Anthropic (https://console.anthropic.com/)
ANTHROPIC_API_KEY=sk-ant-YOUR_ACTUAL_ANTHROPIC_KEY

# DeepSeek (https://platform.deepseek.com/api)
DEEPSEEK_API_KEY=sk-YOUR_ACTUAL_DEEPSEEK_KEY

# Google Gemini (https://ai.google.dev/)
GOOGLE_API_KEY=YOUR_ACTUAL_GOOGLE_API_KEY

# Meta (https://www.together.ai/)
META_API_KEY=YOUR_ACTUAL_META_API_KEY

# ============================================================================
EOF

# Verify it was created
cat .env
```

### Step 2: Add to .gitignore

```bash
# Make sure .env is not committed
echo ".env" >> .gitignore

# Verify
cat .gitignore
```

### Step 3: Update nova_ai_system.py

Add this at the very top after the docstring:

```python
# Around line 10-15, add:
import os
from dotenv import load_dotenv

# CRITICAL: Load environment variables from .env file
load_dotenv()

# Rest of your code continues...
```

### Step 4: Test It

```bash
# Test 1: Check keys are loaded
python test_keys.py

# Test 2: Run example
python example_nova_ai.py

# Test 3: Try custom query
python -c "
from nova_ai_system import NOVAAIOrchestrator
import asyncio

async def test():
    orchestrator = NOVAAIOrchestrator()
    print('✓ System initialized successfully!')
    print(f'Available providers: {orchestrator.question_analyzer.providers.keys()}')

asyncio.run(test())
"
```

---

## 🐛 Debugging

### If Still Getting Error

```python
# Add this debugging code to nova_ai_system.py

import os
from dotenv import load_dotenv

# Load variables
load_dotenv()

# Debug: Print what was loaded
print("DEBUG: Loaded environment variables")
print(f"  OPENAI_API_KEY: {'SET' if os.getenv('OPENAI_API_KEY') else 'NOT SET'}")
print(f"  ANTHROPIC_API_KEY: {'SET' if os.getenv('ANTHROPIC_API_KEY') else 'NOT SET'}")
print(f"  DEEPSEEK_API_KEY: {'SET' if os.getenv('DEEPSEEK_API_KEY') else 'NOT SET'}")
print(f"  GOOGLE_API_KEY: {'SET' if os.getenv('GOOGLE_API_KEY') else 'NOT SET'}")
print(f"  META_API_KEY: {'SET' if os.getenv('META_API_KEY') else 'NOT SET'}")
```

### Check File Path

```bash
# Make sure .env is in the right location
pwd  # Check current directory
ls -la .env  # Verify file exists

# If not in current directory, either:
# 1. Move .env to current directory
cp /path/to/.env ./

# 2. Or specify the path in code
from dotenv import load_dotenv
load_dotenv('/path/to/.env')
```

---

## ✅ Success Indicators

When fixed correctly, you should see:

```
✓ OpenAI         sk-proj-...abcd
✓ Anthropic      sk-ant-...xyz1
✓ DeepSeek       sk-...1234
✓ Google         AIzaSyZ...5678
```

And your system should respond to queries instead of showing the error.

---

## 🎯 Summary

### Quick Fix:
1. **Create .env** with your API keys
2. **Add `load_dotenv()`** to nova_ai_system.py
3. **Run** `python example_nova_ai.py`

### That's it! The error should be gone.

---

## 📞 Still Having Issues?

### Check This Checklist:

- [ ] .env file exists in project root
- [ ] .env contains all API keys with correct format
- [ ] nova_ai_system.py has `from dotenv import load_dotenv`
- [ ] nova_ai_system.py has `load_dotenv()` at the top
- [ ] API keys are from correct providers (not expired)
- [ ] Environment variables have correct UPPERCASE names
- [ ] No typos in API key values
- [ ] File is readable (correct permissions)

If still stuck:
1. Run `python test_keys.py` to verify keys are loaded
2. Check the actual error message in detail
3. Try setting keys directly: `export OPENAI_API_KEY="..."`
4. Run Python directly: `python -c "from nova_ai_system import *"`

---

**You should be up and running now!** 🚀
