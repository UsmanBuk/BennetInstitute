import pytest
from unittest.mock import patch, Mock, MagicMock
import requests
from optool import (
    extract_chemical_code,
    check_code_exists,
    get_chemical_name,
    get_spending_data,
    find_top_prescriber_by_month,
    find_top_prescriber_by_month_weighted,
    get_icb_list_sizes
)

# Test data fixtures
@pytest.fixture
def sample_bnf_code():
    """A valid 15-character BNF code."""
    return "0101010G0AAABAB"

@pytest.fixture
def sample_chemical_code():
    """A 9-character chemical code."""
    return "0101010G0"

@pytest.fixture
def api_chemical_response():
    """Mock API response for chemical lookup."""
    return [
        {
            "id": "0101010G0",
            "name": "Co-Magaldrox_Susp 195mg/220mg/5ml S/F",
            "type": "chemical"
        }
    ]

@pytest.fixture
def api_spending_response():
    """Mock API response for spending data."""
    return [
        {
            "date": "2023-01-01",
            "row_id": "ICB001",
            "row_name": "NHS North East London ICB",
            "items": 150,
            "quantity": 1500,
            "actual_cost": 7500.50
        },
        {
            "date": "2023-01-01",
            "row_id": "ICB002",
            "row_name": "NHS South East London ICB",
            "items": 200,
            "quantity": 2000,
            "actual_cost": 10000.00
        },
        {
            "date": "2023-02-01",
            "row_id": "ICB001",
            "row_name": "NHS North East London ICB",
            "items": 180,
            "quantity": 1800,
            "actual_cost": 9000.00
        },
        {
            "date": "2023-02-01",
            "row_id": "ICB002",
            "row_name": "NHS South East London ICB",
            "items": 120,
            "quantity": 1200,
            "actual_cost": 6000.00
        }
    ]

@pytest.fixture
def api_list_sizes_response():
    """Mock API response for ICB list sizes."""
    return [
        {
            "row_id": "ICB001",
            "total_list_size": 500000,
            "date": "2023-01-01"
        },
        {
            "row_id": "ICB002",
            "total_list_size": 800000,
            "date": "2023-01-01"
        }
    ]

# Tests for extract_chemical_code
class TestExtractChemicalCode:
    def test_valid_bnf_code_with_existing_9_char(self):
        """Test extraction when 9-character code exists in API."""
        with patch('optool.check_code_exists') as mock_check:
            mock_check.return_value = True
            result = extract_chemical_code("0101010G0AAABAB")
            assert result == "0101010G0"
            mock_check.assert_called_once_with("0101010G0")
    
    def test_valid_bnf_code_with_7_char_fallback(self):
        """Test extraction falling back to 7-character code."""
        with patch('optool.check_code_exists') as mock_check:
            # First call (9 chars) returns False, second call (7 chars) returns True
            mock_check.side_effect = [False, True]
            result = extract_chemical_code("0101010G0AAABAB")
            assert result == "0101010"
            assert mock_check.call_count == 2
    
    def test_valid_bnf_code_default_to_9_chars(self):
        """Test default to 9 characters when no match found."""
        with patch('optool.check_code_exists') as mock_check:
            mock_check.return_value = False
            result = extract_chemical_code("0101010G0AAABAB")
            assert result == "0101010G0"
    
    def test_invalid_length(self):
        """Test error raised for invalid BNF code length."""
        with pytest.raises(ValueError, match="BNF code must be exactly 15 characters"):
            extract_chemical_code("12345")

# Tests for check_code_exists
class TestCheckCodeExists:
    @patch('requests.get')
    def test_code_exists(self, mock_get, api_chemical_response):
        """Test when code exists in API."""
        mock_response = Mock()
        mock_response.json.return_value = api_chemical_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = check_code_exists("0101010G0")
        assert result is True
    
    @patch('requests.get')
    def test_code_not_exists(self, mock_get):
        """Test when code doesn't exist in API."""
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = check_code_exists("0101010G0")
        assert result is False
    
    @patch('requests.get')
    def test_api_error(self, mock_get):
        """Test handling of API errors."""
        mock_get.side_effect = requests.RequestException("Network error")
        result = check_code_exists("0101010G0")
        assert result is False

# Tests for get_chemical_name
class TestGetChemicalName:
    @patch('requests.get')
    def test_successful_lookup(self, mock_get, api_chemical_response):
        """Test successful chemical name lookup."""
        mock_response = Mock()
        mock_response.json.return_value = api_chemical_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = get_chemical_name("0101010G0")
        assert result == "Co-Magaldrox_Susp 195mg/220mg/5ml S/F"
    
    @patch('requests.get')
    def test_no_data_found(self, mock_get):
        """Test when no data is returned."""
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        with pytest.raises(Exception, match="No data found for chemical code"):
            get_chemical_name("0101010G0")
    
    @patch('requests.get')
    def test_no_exact_match(self, mock_get):
        """Test when no exact match is found."""
        mock_response = Mock()
        mock_response.json.return_value = [{"id": "0101010G1", "name": "Different chemical"}]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        with pytest.raises(Exception, match="No exact match found for chemical code"):
            get_chemical_name("0101010G0")
    
    @patch('requests.get')
    def test_api_request_error(self, mock_get):
        """Test handling of API request errors."""
        mock_get.side_effect = requests.RequestException("Connection error")
        
        with pytest.raises(Exception, match="Failed to fetch data from API"):
            get_chemical_name("0101010G0")

# Tests for get_spending_data
class TestGetSpendingData:
    @patch('requests.get')
    def test_successful_retrieval(self, mock_get, api_spending_response):
        """Test successful spending data retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = api_spending_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = get_spending_data("0101010G0")
        
        # Verify the structure
        assert "2023-01-01" in result
        assert "2023-02-01" in result
        assert len(result["2023-01-01"]) == 2
        assert len(result["2023-02-01"]) == 2
        
        # Verify data transformation
        jan_data = result["2023-01-01"]
        assert jan_data[0]["org_id"] == "ICB001"
        assert jan_data[0]["org_name"] == "NHS North East London ICB"
        assert jan_data[0]["items"] == 150
        assert jan_data[0]["quantity"] == 1500
        assert jan_data[0]["actual_cost"] == 7500.50
    
    @patch('requests.get')
    def test_api_error(self, mock_get):
        """Test handling of API errors."""
        mock_get.side_effect = requests.RequestException("API Error")
        
        with pytest.raises(Exception, match="Failed to fetch spending data from API"):
            get_spending_data("0101010G0")

# Tests for find_top_prescriber_by_month
class TestFindTopPrescriberByMonth:
    def test_find_top_prescribers(self):
        """Test finding top prescribers by item count."""
        spending_data = {
            "2023-01-01": [
                {"org_id": "ICB001", "org_name": "ICB One", "items": 100},
                {"org_id": "ICB002", "org_name": "ICB Two", "items": 200}
            ],
            "2023-02-01": [
                {"org_id": "ICB001", "org_name": "ICB One", "items": 150},
                {"org_id": "ICB002", "org_name": "ICB Two", "items": 120}
            ]
        }
        
        result = find_top_prescriber_by_month(spending_data)
        
        assert len(result) == 2
        assert result[0] == ("2023-01-01", "ICB Two")  # 200 items
        assert result[1] == ("2023-02-01", "ICB One")  # 150 items
    
    def test_empty_data(self):
        """Test with empty spending data."""
        result = find_top_prescriber_by_month({})
        assert result == []
    
    def test_tie_breaking(self):
        """Test tie-breaking (first one wins)."""
        spending_data = {
            "2023-01-01": [
                {"org_id": "ICB001", "org_name": "ICB One", "items": 100},
                {"org_id": "ICB002", "org_name": "ICB Two", "items": 100}
            ]
        }
        
        result = find_top_prescriber_by_month(spending_data)
        assert result[0] == ("2023-01-01", "ICB One")  # First in list wins

# Tests for find_top_prescriber_by_month_weighted
class TestFindTopPrescriberByMonthWeighted:
    def test_weighted_calculation(self):
        """Test weighted calculation by population."""
        spending_data = {
            "2023-01-01": [
                {"org_id": "ICB001", "org_name": "ICB One", "items": 100},
                {"org_id": "ICB002", "org_name": "ICB Two", "items": 200}
            ]
        }
        list_sizes = {
            "2023-01-01": {
                "ICB001": 10000,  # Rate: 100/10000 = 0.01
                "ICB002": 40000   # Rate: 200/40000 = 0.005
            }
        }
        
        result = find_top_prescriber_by_month_weighted(spending_data, list_sizes)
        
        assert len(result) == 1
        assert result[0] == ("2023-01-01", "ICB One")  # Higher rate
    
    def test_missing_list_size(self):
        """Test handling of missing list size data."""
        spending_data = {
            "2023-01-01": [
                {"org_id": "ICB001", "org_name": "ICB One", "items": 100},
                {"org_id": "ICB002", "org_name": "ICB Two", "items": 200}
            ]
        }
        list_sizes = {
            "2023-01-01": {
                "ICB001": 10000  # ICB002 missing
            }
        }
        
        result = find_top_prescriber_by_month_weighted(spending_data, list_sizes)
        
        # Should only include ICB with list size
        assert len(result) == 1
        assert result[0] == ("2023-01-01", "ICB One")

# Tests for get_icb_list_sizes
class TestGetIcbListSizes:
    @patch('requests.get')
    def test_successful_retrieval(self, mock_get, api_list_sizes_response):
        """Test successful list sizes retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = api_list_sizes_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        org_ids = {"ICB001", "ICB002"}
        dates = ["2023-01-01"]
        
        result = get_icb_list_sizes(org_ids, dates)
        
        assert "2023-01-01" in result
        assert result["2023-01-01"]["ICB001"] == 500000
        assert result["2023-01-01"]["ICB002"] == 800000
    
    @patch('requests.get')
    def test_partial_failure_handling(self, mock_get, capsys):
        """Test handling of partial API failures."""
        # First call succeeds, second fails
        success_response = Mock()
        success_response.json.return_value = [
            {"row_id": "ICB001", "total_list_size": 500000}
        ]
        success_response.raise_for_status.return_value = None
        
        def side_effect(url):
            if "2023-01" in url:
                return success_response
            else:
                raise requests.RequestException("API Error")
        
        mock_get.side_effect = side_effect
        
        org_ids = {"ICB001", "ICB002"}
        dates = ["2023-01-01", "2023-02-01"]
        
        result = get_icb_list_sizes(org_ids, dates)
        
        # Should have partial data
        assert "2023-01-01" in result
        assert result["2023-01-01"]["ICB001"] == 500000
        assert "2023-02-01" not in result
        
        # Check warning was printed
        captured = capsys.readouterr()
        assert "Warning: Failed to fetch list sizes" in captured.err
    
    @patch('requests.get')
    def test_multiple_months_same_year(self, mock_get):
        """Test handling multiple dates in same year-month."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {"row_id": "ICB001", "total_list_size": 500000}
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        org_ids = {"ICB001"}
        dates = ["2023-01-01", "2023-01-15", "2023-01-31"]
        
        result = get_icb_list_sizes(org_ids, dates)
        
        # All three dates should have the same data
        assert all(date in result for date in dates)
        assert all(result[date]["ICB001"] == 500000 for date in dates)
        
        # Should only make one API call
        assert mock_get.call_count == 1 