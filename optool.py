#!/usr/bin/env python3
"""
OpenPrescribing command-line tool for retrieving drug information.

This tool uses the OpenPrescribing API to look up chemical substance names
from BNF codes and analyze prescribing data by ICB.

Production Considerations:
- Add structured logging (e.g., using Python's logging module)
- Implement retry logic with exponential backoff for API failures
- Add response caching to reduce API calls and improve performance
- Respect rate limiting (check API documentation for limits)
- Add monitoring/alerting for API failures
- Consider using async requests for parallel API calls
- Add circuit breaker pattern for API resilience
"""

import sys
import requests
import argparse
from datetime import datetime
from collections import defaultdict


# Configuration Constants
API_BASE_URL = "https://openprescribing.net/api/1.0"
API_TIMEOUT = 30  # seconds
BNF_CODE_LENGTH = 15
CHEMICAL_CODE_LENGTH = 9
CHEMICAL_CODE_ALT_LENGTH = 7  # Alternative length for edge cases
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

# TODO: In production, these would come from environment variables or config file
# API_KEY = os.environ.get('OPENPRESCRIBING_API_KEY')
# CACHE_TTL = int(os.environ.get('CACHE_TTL', 3600))


# Custom Exceptions
class OptoolError(Exception):
    """Base exception for optool"""
    pass


class APIError(OptoolError):
    """Raised when API requests fail"""
    pass


class DataNotFoundError(OptoolError):
    """Raised when expected data is not found"""
    pass


class InvalidInputError(OptoolError):
    """Raised when input validation fails"""
    pass


def extract_chemical_code(bnf_code):
    """
    Extract the chemical substance code from a full BNF code.
    
    According to the BNF code structure:
    - Full BNF code is 15 characters
    - Chemical substance code is the first 9 characters
    
    Args:
        bnf_code (str): The full 15-character BNF code
        
    Returns:
        str: The chemical substance code
        
    Raises:
        InvalidInputError: If BNF code is not exactly 15 characters
    """
    if len(bnf_code) != BNF_CODE_LENGTH:
        raise InvalidInputError(
            f"BNF code must be exactly {BNF_CODE_LENGTH} characters, got {len(bnf_code)}"
        )
    
    # TODO: In production, consider caching the results of check_code_exists
    # to avoid repeated API calls for the same codes
    
    # Try different lengths to handle edge cases
    for length in [CHEMICAL_CODE_LENGTH, CHEMICAL_CODE_ALT_LENGTH]:
        chemical_code = bnf_code[:length]
        # Quick check if this code exists in the API
        if check_code_exists(chemical_code):
            return chemical_code
    
    # If no match found, default to standard length
    # TODO: Log this scenario for monitoring unusual BNF codes
    return bnf_code[:CHEMICAL_CODE_LENGTH]


def check_code_exists(code):
    """
    Check if a code exists in the API.
    
    Args:
        code (str): The code to check
        
    Returns:
        bool: True if the code exists, False otherwise
        
    TODO: In production:
    - Implement caching to avoid repeated lookups
    - Add metrics/monitoring for API response times
    """
    api_url = f"{API_BASE_URL}/bnf_code/?format=json&exact=true&param={code}"
    
    try:
        response = requests.get(api_url, timeout=API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        # Check if we have any results with this exact ID
        for item in data:
            if item.get('id') == code:
                return True
        return False
    except requests.RequestException:
        # TODO: In production, log the specific error for debugging
        # For now, assume code doesn't exist if we can't check
        return False


def get_chemical_name(chemical_code):
    """
    Look up the chemical name using the OpenPrescribing API.
    
    Args:
        chemical_code (str): The 9-character chemical substance code
        
    Returns:
        str: The name of the chemical substance
        
    Raises:
        APIError: If the API request fails
        DataNotFoundError: If no data found for the chemical code
    """
    api_url = f"{API_BASE_URL}/bnf_code/?format=json&exact=true&q={chemical_code}"
    
    try:
        # TODO: In production, implement retry logic with exponential backoff
        response = requests.get(api_url, timeout=API_TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        
        if not data:
            raise DataNotFoundError(f"No data found for chemical code {chemical_code}")
        
        # The API returns a list of matching codes
        # We're looking for an exact match
        for item in data:
            if item.get('id') == chemical_code:
                return item.get('name', 'Unknown chemical')
        
        # If no exact match found, raise an error
        raise DataNotFoundError(f"No exact match found for chemical code {chemical_code}")
        
    except requests.RequestException as e:
        # TODO: In production, log full stack trace and request details
        raise APIError(f"Failed to fetch data from API: {e}")
    except ValueError as e:
        raise APIError(f"Failed to parse API response: {e}")


def get_spending_data(chemical_code):
    """
    Get spending data for a chemical by ICB over the last 5 years.
    
    Args:
        chemical_code (str): The chemical substance code
        
    Returns:
        dict: Dictionary mapping dates to ICB spending data
        
    Raises:
        APIError: If the API request fails
        
    TODO: In production:
    - Implement pagination if API supports it
    - Add progress indicator for long-running requests
    - Consider streaming response for large datasets
    """
    api_url = f"{API_BASE_URL}/spending_by_org/?format=json&org_type=icb&code={chemical_code}"
    
    try:
        response = requests.get(api_url, timeout=API_TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        
        # Organize data by date
        spending_by_date = defaultdict(list)
        
        for item in data:
            date = item.get('date')
            if date:
                spending_by_date[date].append({
                    'org_id': item.get('row_id'),
                    'org_name': item.get('row_name'),
                    'items': item.get('items', 0),
                    'quantity': item.get('quantity', 0),
                    'actual_cost': item.get('actual_cost', 0)
                })
        
        return dict(spending_by_date)
        
    except requests.RequestException as e:
        raise APIError(f"Failed to fetch spending data from API: {e}")


def find_top_prescriber_by_month(spending_data):
    """
    Find the ICB with the most items prescribed for each month.
    
    Args:
        spending_data (dict): Dictionary mapping dates to ICB spending data
        
    Returns:
        list: List of tuples (date, icb_name) sorted by date
    """
    results = []
    
    for date in sorted(spending_data.keys()):
        icb_data = spending_data[date]
        
        if not icb_data:
            continue
            
        # Find ICB with most items
        # If there's a tie, we take the first one (as returned by API)
        top_icb = max(icb_data, key=lambda x: x['items'])
        
        results.append((date, top_icb['org_name']))
    
    return results


def get_icb_list_sizes(org_ids, dates):
    """
    Get the total list sizes for ICBs for specific months.
    
    Args:
        org_ids (set): Set of ICB organization IDs
        dates (list): List of dates to get list sizes for
        
    Returns:
        dict: Nested dictionary {date: {org_id: total_list_size}}
        
    TODO: In production:
    - Implement bulk fetching if API supports it
    - Add caching with appropriate TTL
    - Consider using async requests for parallel fetching
    """
    list_sizes = defaultdict(dict)
    
    # The org_details endpoint requires specific date parameters
    # We'll need to query for each unique year/month combination
    unique_months = set()
    for date in dates:
        # Extract year and month from date string (YYYY-MM-DD)
        year_month = date[:7]  # Gets YYYY-MM
        unique_months.add(year_month)
    
    for year_month in unique_months:
        # Query for all ICBs for this month
        api_url = f"{API_BASE_URL}/org_details/?format=json&org_type=icb&keys=total_list_size&date={year_month}-01"
        
        try:
            response = requests.get(api_url, timeout=API_TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            
            # Store the list sizes for this month
            for item in data:
                org_id = item.get('row_id')
                if org_id in org_ids:
                    # The date in the response might be different, so we use our year_month
                    for date in dates:
                        if date.startswith(year_month):
                            list_sizes[date][org_id] = item.get('total_list_size', 0)
                            
        except requests.RequestException as e:
            # Continue with partial data if some requests fail
            # TODO: In production, log this error and track partial failures
            print(f"Warning: Failed to fetch list sizes for {year_month}: {e}", file=sys.stderr)
            continue  # Skip this month and try the next one
    
    return dict(list_sizes)


def find_top_prescriber_by_month_weighted(spending_data, list_sizes):
    """
    Find the ICB with the most items prescribed per patient for each month.
    
    Args:
        spending_data (dict): Dictionary mapping dates to ICB spending data
        list_sizes (dict): Dictionary mapping dates to ICB list sizes
        
    Returns:
        list: List of tuples (date, icb_name) sorted by date
    """
    results = []
    
    for date in sorted(spending_data.keys()):
        icb_data = spending_data[date]
        
        if not icb_data:
            continue
        
        # Calculate items per patient for each ICB
        icb_rates = []
        for icb in icb_data:
            org_id = icb['org_id']
            items = icb['items']
            
            # Get the list size for this ICB on this date
            list_size = list_sizes.get(date, {}).get(org_id, 0)
            
            if list_size > 0:
                rate = items / list_size
                icb_rates.append({
                    'org_name': icb['org_name'],
                    'rate': rate
                })
        
        if icb_rates:
            # Find ICB with highest rate
            top_icb = max(icb_rates, key=lambda x: x['rate'])
            results.append((date, top_icb['org_name']))
    
    return results


def main():
    """
    Main function to handle command-line arguments and execute the tool.
    
    TODO: In production:
    - Add verbose/debug flags for different logging levels
    - Add output format options (JSON, CSV, etc.)
    - Add date range filtering options
    - Consider adding a --dry-run option
    """
    parser = argparse.ArgumentParser(
        description="Look up chemical substance names from BNF codes using the OpenPrescribing API"
    )
    parser.add_argument(
        "bnf_code",
        help="The full 15-character BNF code for a drug"
    )
    parser.add_argument(
        "--weighted",
        action="store_true",
        help="Weight results by population size (items per patient)"
    )
    
    # TODO: In production, add these arguments:
    # parser.add_argument("--cache", action="store_true", help="Enable response caching")
    # parser.add_argument("--timeout", type=int, default=30, help="API timeout in seconds")
    # parser.add_argument("--format", choices=['text', 'json', 'csv'], default='text')
    
    args = parser.parse_args()
    
    try:
        # Extract the chemical code from the full BNF code
        chemical_code = extract_chemical_code(args.bnf_code)
        
        # Look up the chemical name
        chemical_name = get_chemical_name(chemical_code)
        
        # Print the chemical name
        print(chemical_name)
        
        # Part 2: Get spending data
        print()  # Empty line for separation
        
        spending_data = get_spending_data(chemical_code)
        
        if not spending_data:
            print("No spending data found for this chemical.")
            sys.exit(0)
        
        if args.weighted:
            # Part 3: Weighted by population
            # First, collect all unique org_ids and dates
            org_ids = set()
            dates = list(spending_data.keys())
            
            for date_data in spending_data.values():
                for item in date_data:
                    org_ids.add(item['org_id'])
            
            # Get list sizes for all ICBs
            list_sizes = get_icb_list_sizes(org_ids, dates)
            
            # Find top prescribers weighted by population
            top_prescribers = find_top_prescriber_by_month_weighted(spending_data, list_sizes)
        else:
            # Part 2: Raw item counts
            top_prescribers = find_top_prescriber_by_month(spending_data)
        
        # Print results
        for date, icb_name in top_prescribers:
            print(f"{date} {icb_name}")
        
    except InvalidInputError as e:
        # User input errors should be friendly
        print(f"Invalid input: {e}", file=sys.stderr)
        sys.exit(1)
    except DataNotFoundError as e:
        # Data not found is a valid scenario
        print(f"Data not found: {e}", file=sys.stderr)
        sys.exit(1)
    except APIError as e:
        # API errors might be temporary
        print(f"API Error: {e}", file=sys.stderr)
        print("Please try again later or contact support if the problem persists.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # Unexpected errors
        # TODO: In production, log full stack trace
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()