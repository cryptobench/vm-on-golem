import pytest
import pytest_asyncio
from httpx import AsyncClient
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

# Import the app instance from your main application file
# Adjust the import path based on your project structure
from provider.main import app as main_app
from provider.config import settings # Import settings

# Define the standardized error models (can be imported if defined elsewhere)
class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[str] = None

class StandardErrorResponse(BaseModel):
    error: ErrorResponse

# The autouse fixture is now in conftest.py

# Fixture to create a test client
@pytest_asyncio.fixture(scope="function")
async def test_client(): # Remove monkeypatch parameter
    # Ensure settings are available in app state for the test
    # The settings object should now be instantiated without validation error due to the autouse fixture
    main_app.state.settings = settings

    async with AsyncClient(app=main_app, base_url="http://test") as client:
        yield client

# Test for 404 Not Found error
@pytest.mark.asyncio
async def test_not_found_error(test_client: AsyncClient):
    response = await test_client.get("/nonexistent/path")

    assert response.status_code == 404
    error_data = response.json()

    # Validate the structure using the Pydantic model
    parsed_error = StandardErrorResponse(**error_data)
    assert parsed_error.error.code == "HTTP_404"
    assert parsed_error.error.message == "Not Found"
    assert parsed_error.error.details is None

# Test for a generic 500 Internal Server Error
# We need to add a temporary route that raises an unhandled exception
@main_app.get("/_test/internal-error", include_in_schema=False)
async def raise_internal_error():
    raise ValueError("This is a simulated internal error")

@pytest.mark.asyncio
async def test_internal_server_error(test_client: AsyncClient):
    # This route raises ValueError, which should be caught by the generic handler

    # We expect the generic handler to catch the ValueError and return a 500 response
    # The test previously failed because the exception seemed to propagate despite the handler.
    # Let's verify the response received by the client.
    response = await test_client.get("/_test/internal-error")

    assert response.status_code == 500
    error_data = response.json()

    # Validate the structure returned by the generic handler
    parsed_error = StandardErrorResponse(**error_data)
    assert parsed_error.error.code == "INTERNAL_SERVER_ERROR"
    assert parsed_error.error.message == "An unexpected error occurred on the server."
    # We won't assert on details here, as it depends on DEBUG state which we aren't controlling tightly in this simplified test

# Test for a specific HTTPException (e.g., 400 Bad Request)
# Add a temporary route that raises a specific HTTPException
@main_app.get("/_test/http-exception", include_in_schema=False)
async def raise_http_exception():
    raise HTTPException(status_code=400, detail="Specific bad request reason")

@pytest.mark.asyncio
async def test_http_exception_handling(test_client: AsyncClient):
    response = await test_client.get("/_test/http-exception")

    assert response.status_code == 400
    error_data = response.json()

    # Validate the structure
    parsed_error = StandardErrorResponse(**error_data)
    assert parsed_error.error.code == "HTTP_400"
    assert parsed_error.error.message == "Specific bad request reason"
    assert parsed_error.error.details is None # Details are None for HTTPException by default
