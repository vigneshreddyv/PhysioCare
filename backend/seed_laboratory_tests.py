#!/usr/bin/env python3
"""
Seed script to populate the laboratory test catalog from the frontend's laboratoryTests.js file.
"""
import json
import subprocess
import sys
import os

from app.models.laboratory_test import LaboratoryTest
from app.database import init_db


def get_laboratory_tests_from_frontend():
    """
    Use Node.js to parse the frontend laboratoryTests.js file and return the array as JSON.
    """
    # Get the absolute path to the frontend file
    frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    frontend_file = os.path.join(frontend_dir, 'src', 'data', 'laboratoryTests.js')
    # Use forward slashes to avoid escaping issues in the node require string on Windows
    frontend_file_posix = frontend_file.replace('\\', '/')

    if not os.path.exists(frontend_file):
        print(f"Error: Frontend file not found at {frontend_file}")
        sys.exit(1)

    # Use Node.js to export the array as JSON
    # We assume Node.js is installed and available in PATH
    cmd = [
        'node',
        '-e',
        f"const tests = require('{frontend_file_posix}'); console.log(JSON.stringify(tests));"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        tests_json = result.stdout.strip()
        tests = json.loads(tests_json)
        return tests
    except subprocess.CalledProcessError as e:
        print(f"Error running Node.js: {e}")
        print(f"stderr: {e.stderr}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON output from Node.js: {e}")
        print(f"Output: {result.stdout}")
        sys.exit(1)


async def seed_laboratory_tests():
    """
    Seed the laboratory test collection with data from the frontend.
    """
    await init_db()

    tests_data = get_laboratory_tests_from_frontend()
    tests_list = tests_data.get('laboratoryTests', tests_data) if isinstance(tests_data, dict) else tests_data

    inserted_count = 0
    skipped_count = 0

    for test_dict in tests_list:
        test_id = test_dict['id']
        # Check if test already exists
        existing = await LaboratoryTest.find_one(LaboratoryTest.test_id == test_id)
        if existing:
            print(f"Test '{test_id}' already exists. Skipping.")
            skipped_count += 1
            continue

        # Create new test
        test = LaboratoryTest(
            test_id=test_id,
            name=test_dict['name'],
            category=test_dict['category'],
            sample=test_dict['sample'],
            price=float(test_dict['price']),
            active=True
        )
        await test.insert()
        print(f"Inserted test: {test_id}")
        inserted_count += 1

    print(f"\nSeeding complete. Inserted: {inserted_count}, Skipped: {skipped_count}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_laboratory_tests())