#!/usr/bin/env python3
"""Diagnostic script to test Fates Engine components."""
import sys
import os


def test_imports():
    print("Testing imports...")
    try:
        from config import settings
        print(f"✓ Config loaded. API Key present: {bool(settings.openai_api_key)}")
    except Exception as e:
        print(f"✗ Config error: {e}")
        return False

    try:
        from experts.gateway import gateway
        print("✓ Gateway import successful")
    except Exception as e:
        print(f"✗ Gateway import failed: {e}")
        return False

    try:
        from synthesis.archon import Archon
        print("✓ Archon import successful")
    except Exception as e:
        print(f"✗ Archon import failed: {e}")
        return False

    return True


def test_openai_connection():
    print("\nTesting OpenAI connection...")
    try:
        from experts.gateway import gateway
        response = gateway.generate(
            system_prompt="You are a test assistant.",
            user_prompt="Say 'Connection successful' and nothing else.",
            model="gpt-4o-mini",  # Use mini for testing (faster/cheaper)
            max_tokens=50
        )
        if response.get("success"):
            print(f"✓ OpenAI connection working: {response['content'][:50]}")
            return True
        else:
            print(f"✗ OpenAI error: {response.get('error')}")
            return False
    except Exception as e:
        print(f"✗ OpenAI exception: {e}")
        return False


def test_chart_calculation():
    print("\nTesting chart calculation...")
    try:
        from orchestrator import orchestrator
        # Test with minimal data
        chart_data = orchestrator._calculate_charts(
            "1990-01-01 12:00",
            "London, UK",
            "male"
        )
        print(f"✓ Chart calculation successful")
        print(f"  - Western data: {bool(chart_data.get('western'))}")
        print(f"  - Vedic data: {bool(chart_data.get('vedic'))}")
        return True
    except Exception as e:
        print(f"✗ Chart calculation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("FATES ENGINE DIAGNOSTIC")
    print("=" * 60)

    results = []
    results.append(("Imports", test_imports()))
    results.append(("OpenAI", test_openai_connection()))
    results.append(("Chart Calc", test_chart_calculation()))

    print("\n" + "=" * 60)
    print("RESULTS:")
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
    print("=" * 60)