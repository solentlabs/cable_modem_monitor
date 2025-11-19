"""Tests for HNAP Request Builder."""

from __future__ import annotations

from unittest.mock import MagicMock
from xml.etree.ElementTree import Element, fromstring

import pytest
import requests

from custom_components.cable_modem_monitor.core.hnap_builder import HNAPRequestBuilder


@pytest.fixture
def builder():
    """Create an HNAP request builder instance."""
    return HNAPRequestBuilder(endpoint="/HNAP1/", namespace="http://purenetworks.com/HNAP1/")


@pytest.fixture
def mock_session():
    """Create a mock requests session."""
    session = MagicMock(spec=requests.Session)
    session.verify = False
    return session


class TestHNAPRequestBuilderInit:
    """Test HNAP builder initialization."""

    def test_init(self):
        """Test initialization with endpoint and namespace."""
        builder = HNAPRequestBuilder(endpoint="/HNAP1/", namespace="http://purenetworks.com/HNAP1/")

        assert builder.endpoint == "/HNAP1/"
        assert builder.namespace == "http://purenetworks.com/HNAP1/"


class TestEnvelopeBuilding:
    """Test SOAP envelope building."""

    def test_build_envelope_no_params(self, builder):
        """Test building envelope without parameters."""
        envelope = builder._build_envelope("GetMotoStatusConnectionInfo", None)

        assert '<?xml version="1.0" encoding="utf-8"?>' in envelope
        assert "<soap:Envelope" in envelope
        assert "<GetMotoStatusConnectionInfo" in envelope
        assert "</GetMotoStatusConnectionInfo>" in envelope
        assert "http://purenetworks.com/HNAP1/" in envelope

    def test_build_envelope_with_params(self, builder):
        """Test building envelope with parameters."""
        params = {"Username": "admin", "Password": "password123"}
        envelope = builder._build_envelope("Login", params)

        assert "<Login" in envelope
        assert "<Username>admin</Username>" in envelope
        assert "<Password>password123</Password>" in envelope
        assert "</Login>" in envelope

    def test_build_envelope_valid_xml(self, builder):
        """Test that built envelope is valid XML."""
        envelope = builder._build_envelope("TestAction", {"Param1": "Value1"})

        # Should parse without error
        root = fromstring(envelope)
        assert root is not None

    def test_build_multi_envelope(self, builder):
        """Test building GetMultipleHNAPs envelope."""
        actions = ["GetMotoStatusConnectionInfo", "GetMotoStatusStartupSequence"]
        envelope = builder._build_multi_envelope(actions)

        assert "<GetMultipleHNAPs" in envelope
        assert "<GetMotoStatusConnectionInfo" in envelope
        assert "<GetMotoStatusStartupSequence" in envelope
        assert "http://purenetworks.com/HNAP1/" in envelope

    def test_build_multi_envelope_single_action(self, builder):
        """Test building multi envelope with single action."""
        actions = ["GetMotoStatusConnectionInfo"]
        envelope = builder._build_multi_envelope(actions)

        assert "<GetMultipleHNAPs" in envelope
        assert "<GetMotoStatusConnectionInfo" in envelope

    def test_build_multi_envelope_valid_xml(self, builder):
        """Test that multi envelope is valid XML."""
        actions = ["Action1", "Action2"]
        envelope = builder._build_multi_envelope(actions)

        # Should parse without error
        root = fromstring(envelope)
        assert root is not None


class TestCallSingle:
    """Test single HNAP action calls."""

    def test_success(self, builder, mock_session):
        """Test successful single action call."""
        mock_response = MagicMock()
        mock_response.text = "<xml>response</xml>"
        mock_session.post.return_value = mock_response

        result = builder.call_single(mock_session, "http://192.168.100.1", "GetMotoStatusConnectionInfo")

        assert result == "<xml>response</xml>"

        # Verify request
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args

        assert call_args[0][0] == "http://192.168.100.1/HNAP1/"
        assert call_args[1]["headers"]["SOAPAction"] == '"http://purenetworks.com/HNAP1/GetMotoStatusConnectionInfo"'
        assert call_args[1]["headers"]["Content-Type"] == "text/xml; charset=utf-8"
        assert call_args[1]["timeout"] == 10

    def test_with_params(self, builder, mock_session):
        """Test single call with parameters."""
        mock_response = MagicMock()
        mock_response.text = "<xml>response</xml>"
        mock_session.post.return_value = mock_response

        params = {"Username": "admin"}
        result = builder.call_single(mock_session, "http://192.168.100.1", "Login", params)

        assert result == "<xml>response</xml>"

        # Verify envelope contains parameters
        call_args = mock_session.post.call_args
        envelope = call_args[1]["data"]
        assert "<Username>admin</Username>" in envelope

    def test_handles_http_error(self, builder, mock_session):
        """Test that HTTP errors are raised."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_session.post.return_value = mock_response

        with pytest.raises(requests.HTTPError):
            builder.call_single(mock_session, "http://192.168.100.1", "GetMotoStatusConnectionInfo")

    def test_uses_session_verify(self, builder, mock_session):
        """Test that session verify setting is used."""
        mock_response = MagicMock()
        mock_response.text = "<xml>response</xml>"
        mock_session.post.return_value = mock_response
        mock_session.verify = True

        builder.call_single(mock_session, "http://192.168.100.1", "TestAction")

        call_args = mock_session.post.call_args
        assert call_args[1]["verify"] is True


class TestCallMultiple:
    """Test batched HNAP action calls."""

    def test_success(self, builder, mock_session):
        """Test successful batched call."""
        mock_response = MagicMock()
        mock_response.text = "<xml>batched response</xml>"
        mock_session.post.return_value = mock_response

        actions = ["GetMotoStatusConnectionInfo", "GetMotoStatusStartupSequence"]
        result = builder.call_multiple(mock_session, "http://192.168.100.1", actions)

        assert result == "<xml>batched response</xml>"

        # Verify request
        call_args = mock_session.post.call_args
        assert call_args[1]["headers"]["SOAPAction"] == '"http://purenetworks.com/HNAP1/GetMultipleHNAPs"'

    def test_handles_http_error(self, builder, mock_session):
        """Test that HTTP errors are raised for batched calls."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_session.post.return_value = mock_response

        with pytest.raises(requests.HTTPError):
            builder.call_multiple(mock_session, "http://192.168.100.1", ["Action1"])


class TestParseResponse:
    """Test XML response parsing."""

    def test_success(self):
        """Test parsing a valid HNAP response."""
        xml_response = """<?xml version="1.0"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <GetMotoStatusConnectionInfoResponse xmlns="http://purenetworks.com/HNAP1/">
              <GetMotoStatusConnectionInfoResult>OK</GetMotoStatusConnectionInfoResult>
              <Frequency>555000000</Frequency>
              <Power>5.0</Power>
            </GetMotoStatusConnectionInfoResponse>
          </soap:Body>
        </soap:Envelope>"""

        result = HNAPRequestBuilder.parse_response(
            xml_response, "GetMotoStatusConnectionInfo", "http://purenetworks.com/HNAP1/"
        )

        assert result is not None
        assert isinstance(result, Element)
        assert result.tag.endswith("GetMotoStatusConnectionInfoResponse")

    def test_without_namespace_prefix(self):
        """Test parsing response without namespace prefix."""
        xml_response = """<?xml version="1.0"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <TestActionResponse>
              <Result>OK</Result>
            </TestActionResponse>
          </soap:Body>
        </soap:Envelope>"""

        result = HNAPRequestBuilder.parse_response(xml_response, "TestAction", "http://example.com/")

        assert result is not None
        assert result.tag == "TestActionResponse"

    def test_not_found(self):
        """Test parsing when action response is not found."""
        xml_response = """<?xml version="1.0"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <DifferentActionResponse>
              <Result>OK</Result>
            </DifferentActionResponse>
          </soap:Body>
        </soap:Envelope>"""

        result = HNAPRequestBuilder.parse_response(xml_response, "TestAction", "http://example.com/")

        assert result is None

    def test_invalid_xml(self):
        """Test parsing invalid XML."""
        invalid_xml = "<invalid xml >"

        result = HNAPRequestBuilder.parse_response(invalid_xml, "TestAction", "http://example.com/")

        assert result is None


class TestGetTextValue:
    """Test text value extraction from XML elements."""

    def test_found(self):
        """Test extracting text value from element."""
        xml = """<root>
            <Frequency>555000000</Frequency>
            <Power>5.0</Power>
        </root>"""
        element = fromstring(xml)

        frequency = HNAPRequestBuilder.get_text_value(element, "Frequency")
        power = HNAPRequestBuilder.get_text_value(element, "Power")

        assert frequency == "555000000"
        assert power == "5.0"

    def test_not_found(self):
        """Test getting text value when tag doesn't exist."""
        xml = "<root><Frequency>555000000</Frequency></root>"
        element = fromstring(xml)

        value = HNAPRequestBuilder.get_text_value(element, "NonExistent")

        assert value == ""  # Default value

    def test_with_custom_default(self):
        """Test custom default value."""
        xml = "<root><Frequency>555000000</Frequency></root>"
        element = fromstring(xml)

        value = HNAPRequestBuilder.get_text_value(element, "NonExistent", default="N/A")

        assert value == "N/A"

    def test_none_element(self):
        """Test getting value from None element."""
        value = HNAPRequestBuilder.get_text_value(None, "AnyTag")

        assert value == ""

    def test_empty_tag(self):
        """Test getting value from empty tag."""
        xml = "<root><EmptyTag></EmptyTag></root>"
        element = fromstring(xml)

        value = HNAPRequestBuilder.get_text_value(element, "EmptyTag", default="default")

        assert value == "default"  # Empty text returns default

    def test_strips_whitespace(self):
        """Test that whitespace is stripped from values."""
        xml = "<root><Value>  text with spaces  </Value></root>"
        element = fromstring(xml)

        value = HNAPRequestBuilder.get_text_value(element, "Value")

        assert value == "text with spaces"


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_full_workflow_single_action(self, builder, mock_session):
        """Test complete workflow: build envelope, call, parse response."""
        # Mock response - namespace is handled by parse_response, child elements should not be namespaced
        mock_response_xml = """<?xml version="1.0"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <GetMotoStatusConnectionInfoResponse>
              <Frequency>555000000</Frequency>
              <Power>5.0</Power>
            </GetMotoStatusConnectionInfoResponse>
          </soap:Body>
        </soap:Envelope>"""

        mock_response = MagicMock()
        mock_response.text = mock_response_xml
        mock_session.post.return_value = mock_response

        # Make call
        result_xml = builder.call_single(mock_session, "http://192.168.100.1", "GetMotoStatusConnectionInfo")

        # Parse result
        result = HNAPRequestBuilder.parse_response(result_xml, "GetMotoStatusConnectionInfo", builder.namespace)

        assert result is not None

        # Extract values
        frequency = HNAPRequestBuilder.get_text_value(result, "Frequency")
        power = HNAPRequestBuilder.get_text_value(result, "Power")

        assert frequency == "555000000"
        assert power == "5.0"

    def test_endpoint_variations(self):
        """Test builders with different endpoint formats."""
        builder1 = HNAPRequestBuilder("/HNAP1/", "http://purenetworks.com/HNAP1/")
        builder2 = HNAPRequestBuilder("/api/hnap", "http://example.com/api/")

        assert builder1.endpoint == "/HNAP1/"
        assert builder2.endpoint == "/api/hnap"
        assert builder1.namespace == "http://purenetworks.com/HNAP1/"
        assert builder2.namespace == "http://example.com/api/"
