import os
import asyncio
from dotenv import load_dotenv
from google import genai

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

async def test_async():
    client = genai.Client(api_key=GEMINI_API_KEY)
    print("Testing async generate_content...")
    try:
        # Checking how to call it asynchronously in the new SDK
        # Usually it's client.aio.models.generate_content or similar
        response = await client.aio.models.generate_content(
            model='gemini-2.0-flash',
            contents='Hola, ¿quién eres?'
        )
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Async call failed: {e}")
        print("Checking if Client(aio=True) is needed or similar...")

if __name__ == "__main__":
    asyncio.run(test_async())
