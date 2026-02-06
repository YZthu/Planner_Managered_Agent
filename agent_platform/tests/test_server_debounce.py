import asyncio
import httpx
import time
import sys

async def run_integration_test():
    print("🚀 Starting Server Integration Test for Debouncing...")
    url = "http://localhost:8000/api/chat"
    
    # Session ID must be the same for debouncing to work
    session_id = f"test_live_{int(time.time())}"
    
    # Define payloads
    messages = [
        "Part 1: The quick brown fox",
        "Part 2: jumps over",
        "Part 3: the lazy dog."
    ]
    
    async def send_msg(msg):
        async with httpx.AsyncClient() as client:
            print(f"   -> Sending: '{msg}'")
            try:
                resp = await client.post(url, json={
                    "message": msg, 
                    "session_id": session_id,
                    "provider": "deepseek" # Force a provider that we know is configured or generic
                }, timeout=30.0)
                return resp.json()
            except Exception as e:
                return {"error": str(e)}

    print(f"\n📡 Sending 3 requests concurrently to {url}...")
    start_time = time.time()
    
    # Fire them all at once
    results = await asyncio.gather(*[send_msg(m) for m in messages])
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"\n⏱️  Total duration: {duration:.2f}s")
    
    # Verification
    print("\n🔍 Analyzing Results:")
    responses = [r.get("response", r.get("error")) for r in results]
    
    # 1. Check if all responses are identical
    first_resp = responses[0]
    all_same = all(r == first_resp for r in responses)
    
    if all_same:
        print("   [PASS] All client responses are identical.")
    else:
        print("   [FAIL] Responses differ!")
        for i, r in enumerate(responses):
            print(f"     Req {i}: {r[:50]}...")

    # 2. Check content (DeepSeek might just chat, but hopefully it sees all parts)
    # We can't strictly check the *content* without seeing what the LLM said, 
    # but usually it will acknowledge the full sentence if it got it all.
    print(f"\n🤖 Agent Response:\n{first_resp}")

    if duration >= 1.0: # Default debounce is 1000ms
        print(f"\n   [PASS] Debounce delay observed (Wait time > 1s)")
    else:
        print(f"\n   [WARN] Response was too fast ({duration}s). Did debounce kick in?")

if __name__ == "__main__":
    # Check if server is up first
    try:
        import requests
        requests.get("http://localhost:8000/health")
    except:
        print("❌ Server is seemingly NOT running at localhost:8000")
        print("   Please start the server with: python main.py")
        sys.exit(1)
        
    asyncio.run(run_integration_test())
