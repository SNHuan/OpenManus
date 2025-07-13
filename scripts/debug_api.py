#!/usr/bin/env python3
"""Debug API registration issues."""

import asyncio
import aiohttp
import json
from typing import Dict, Any

API_BASE = "http://localhost:8000/api/v1"

async def test_registration():
    """Test user registration with detailed error reporting."""

    async with aiohttp.ClientSession() as session:
        print("🔍 Debugging API Registration...")

        # Test data
        user_data = {
            "username": "debuguser",
            "email": "debug@example.com",
            "password": "debugpassword123"
        }

        print(f"\n📤 Sending registration request:")
        print(f"URL: {API_BASE}/auth/register")
        print(f"Data: {json.dumps(user_data, indent=2)}")

        try:
            async with session.post(
                f"{API_BASE}/auth/register",
                json=user_data,
                headers={"Content-Type": "application/json"}
            ) as resp:
                print(f"\n📥 Response:")
                print(f"Status: {resp.status}")
                print(f"Headers: {dict(resp.headers)}")

                # Get response text
                response_text = await resp.text()
                print(f"Raw response: {response_text}")

                # Try to parse as JSON
                try:
                    response_data = json.loads(response_text)
                    print(f"Parsed JSON: {json.dumps(response_data, indent=2)}")
                except json.JSONDecodeError:
                    print("Response is not valid JSON")

                if resp.status == 422:
                    print("\n❌ Validation Error (422):")
                    try:
                        error_data = json.loads(response_text)
                        if "detail" in error_data:
                            print("Validation errors:")
                            for error in error_data["detail"]:
                                print(f"  - Field: {error.get('loc', 'unknown')}")
                                print(f"    Message: {error.get('msg', 'unknown')}")
                                print(f"    Type: {error.get('type', 'unknown')}")
                    except:
                        print("Could not parse validation errors")

        except Exception as e:
            print(f"❌ Request failed: {e}")

async def test_health():
    """Test health endpoint."""
    async with aiohttp.ClientSession() as session:
        print("\n🏥 Testing health endpoint...")

        try:
            async with session.get("http://localhost:8000/health") as resp:
                print(f"Status: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    print(f"Health data: {json.dumps(data, indent=2)}")
                else:
                    text = await resp.text()
                    print(f"Error response: {text}")
        except Exception as e:
            print(f"❌ Health check failed: {e}")

async def test_docs():
    """Test if docs are accessible."""
    async with aiohttp.ClientSession() as session:
        print("\n📚 Testing docs endpoint...")

        try:
            async with session.get("http://localhost:8000/docs") as resp:
                print(f"Docs status: {resp.status}")
                if resp.status == 200:
                    print("✅ Docs are accessible")
                else:
                    print(f"❌ Docs not accessible: {resp.status}")
        except Exception as e:
            print(f"❌ Docs check failed: {e}")

async def main():
    """Main function."""
    try:
        await test_health()
        await test_docs()
        await test_registration()

        print("\n💡 Debugging tips:")
        print("1. Check if the backend server is running")
        print("2. Visit http://localhost:8000/docs for API documentation")
        print("3. Check server logs for detailed error messages")
        print("4. Verify database is properly initialized")

    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
