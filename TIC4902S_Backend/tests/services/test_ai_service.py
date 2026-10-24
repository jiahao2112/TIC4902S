import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.ai_service import aiService
from app.schemas.ai import GeneratedLocation
from groq import RateLimitError, APIConnectionError, APIStatusError

aiServiceClient = TestClient(aiService)

#Mock Groq API and logger
@pytest.fixture
def mock_Groq():
    with patch("app.services.ai_service.AsyncGroq") as mockGroq, \
    patch("app.services.ai_service.logger") as mock_logger:
        mock_instance = mockGroq.return_value
        mock_instance.closed = False

        async def close():
            mock_instance.closed = True

        mock_instance.close.side_effect = close
        mock_logger.disabled = True
        yield mock_instance
    

class TestLifespan:
    def test_lifespan_start(self,mock_Groq):
        with TestClient(aiService):
            assert aiService.state.groq_client is mock_Groq
            assert aiService.state.groq_client.closed is False

    def test_lifespan_stop(self, mock_Groq):
        with TestClient(aiService):
            pass

        assert aiService.state.groq_client.closed is True
        

class TestHealth:
    def test_health(self):
        response = aiServiceClient.get("")

        assert response.status_code == 200
        assert response.json() == "AI service is running."


class TestGenerate:
    valid_payload = {"content": [{"country": "singapore", "days": 1}]}

    def test_generate_success(self, mock_Groq):
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"destinations": [{"destination":"Gardens by the Bay","longitude":103.86381889,"latitude":1.2815655}]}'
                )
            )
        ]
        mock_Groq.chat.completions.create = AsyncMock(return_value=mock_completion)
        aiService.state.groq_client = mock_Groq
        payload = self.valid_payload

        response = aiServiceClient.post("/generate", json=payload)

        assert response.status_code == 200
        assert len(response.json()["content"]) == 1
        for item in response.json()["content"]:
            assert GeneratedLocation.model_validate(item)

    def test_generate_no_client(self):
        payload = {"content": [{"country": "singapore", "days": 1}]}
        aiService.state.groq_client = None

        response = aiServiceClient.post("/generate", json=payload)

        assert response.status_code == 503
        assert response.json()["detail"] == "Groq is not configured. Set GROQ_API_KEY in your .env file."
        

    def test_generate_empty_country_field(self, mock_Groq):
        payload = {"content": [{"country": "", "days": 1}]}
        aiService.state.groq_client = mock_Groq

        response = aiServiceClient.post("/generate", json=payload)

        assert response.status_code == 422
        assert "String should have at least 1 character" in response.json()["detail"][0]

    def test_generate_invalid_days_field(self, mock_Groq):
            payload = {"role": "user", "content": [{"country": "singapore", "days": 0}]}
            aiService.state.groq_client = mock_Groq
    
            response = aiServiceClient.post("/generate", json=payload)
    
            assert response.status_code == 422
            assert "Input should be greater than 0" in response.json()["detail"][0]

    def test_generate_invalid_output(self, mock_Groq):
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"destinations": [{"longitude":103.86381889,"latitude":1.2815655}]}'
                )
            )
        ]
        mock_Groq.chat.completions.create = AsyncMock(return_value=mock_completion)
        aiService.state.groq_client = mock_Groq
        payload = self.valid_payload

        response = aiServiceClient.post("/generate", json=payload)
        print(response.text)
        assert response.status_code == 422
        # assert ""

    def test_generate_rate_limit(self, mock_Groq):
        mock_response = MagicMock()
        mock_body = {"error": "Rate limit exceeded"}
        # Configure the mock to raise RateLimitError
        mock_Groq.chat.completions.create = AsyncMock(
            side_effect=RateLimitError(message="Rate limit exceeded", response=mock_response, body=mock_body)
        )
        aiService.state.groq_client = mock_Groq
        payload = self.valid_payload

        response = aiServiceClient.post("/generate", json=payload)

        assert response.status_code == 429
        assert response.json()["detail"] == "Groq rate limit exceeded."

    def test_generate_api_connection_error(self, mock_Groq):
        # Simulate Groq connection error
        mock_request = MagicMock()
        mock_Groq.chat.completions.create = AsyncMock(
            side_effect=APIConnectionError(message="Connection failed", request=mock_request)
        )
        aiService.state.groq_client = mock_Groq

        payload = self.valid_payload
        response = aiServiceClient.post("/generate", json=payload)

        assert response.status_code == 502
        assert response.json()["detail"] == "Could not connect to Groq. Please try again."

    def test_generate_api_status_error(self, mock_Groq):
        # Simulate Groq connection error
        mock_response = MagicMock()
        mock_body = {"error": "Bad request"}
        mock_Groq.chat.completions.create = AsyncMock(
            side_effect=APIStatusError(message="Bad request", response=mock_response, body=mock_body)
        )
        aiService.state.groq_client = mock_Groq

        payload = self.valid_payload
        response = aiServiceClient.post("/generate", json=payload)

        assert response.status_code == 502
        assert response.json()["detail"] == "Groq returned an error while generating a response."