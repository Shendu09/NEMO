"""Test browser summarize function"""
from core.browser.web_agent import summarize_page

result = summarize_page('https://bbc.com')
print(f"SUCCESS: {result.get('success', 'N/A')}")
print(f"Title: {result.get('title', '')[:50]}...")
print(f"Summary: {result.get('summary', '')[:100]}...")
