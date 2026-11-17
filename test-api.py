import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
	print('Error: GEMINI_API_KEY not found in environment.')
	exit(1)

client = genai.Client(api_key=api_key)

print('Available Gemini models for current credentials:')
for model in client.models.list():
	supported_actions = getattr(model, 'supported_actions', []) or []
	if 'generateContent' in supported_actions:
		print(f' - {model.name} ({getattr(model, "display_name", "")})')
