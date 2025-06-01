#!/usr/bin/env python3
"""
OpenPrescribing command-line tool for retrieving drug information.

This tool uses the OpenPrescribing API to look up chemical substance names
from BNF codes and analyze prescribing data by ICB.
"""

import sys
import requests
import argparse
from datetime import datetime
from collections import defaultdict


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
    """
    if len(bnf_code) != 15:
        raise ValueError(f"BNF code must be exactly 15 characters, got {len(bnf_code)}")
    
    
    for length in [9, 7]:
        chemical_code = bnf_code[:length]
        # Quick check if this code exists in the API
        if check_code_exists(chemical_code):
            return chemical_code
    
    # If no match found, default to 9 characters
    return bnf_code[:9]


def check_code_exists(code):
    """
    Check if a code exists in the API.
    
    Args:
        code (str): The code to check
        
    Returns:
        bool: True if the code exists, False otherwise
    """
    api_url = f"https://openprescribing.net/api/1.0/bnf_code/?format=json&exact=true&param={code}"
    
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        
        # Check if we have any results with this exact ID
        for item in data:
            if item.get('id') == code:
                return True
        return False
    except:
        return False


def get_chemical_name(chemical_code):
    """
    Look up the chemical name using the OpenPrescribing API.
    
    Args:
        chemical_code (str): The 9-character chemical substance code
        
    Returns:
        str: The name of the chemical substance
        
    Raises:
        Exception: If the API request fails or returns unexpected data
    """
    api_url = f"https://openprescribing.net/api/1.0/bnf_code/?format=json&exact=true&q={chemical_code}"
    
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        
        data = response.json()
        
        if not data:
            raise ValueError(f"No data found for chemical code {chemical_code}")
        
        # The API returns a list of matching codes
        # We're looking for an exact match
        for item in data:
            if item.get('id') == chemical_code:
                return item.get('name', 'Unknown chemical')
        
        # If no exact match found, raise an error
        raise ValueError(f"No exact match found for chemical code {chemical_code}")
        
    except requests.RequestException as e:
        raise Exception(f"Failed to fetch data from API: {e}")
    except ValueError as e:
        raise Exception(f"Failed to parse API response: {e}")


def get_spending_data(chemical_code):
    """
    Get spending data for a chemical by ICB over the last 5 years.
    
    Args:
        chemical_code (str): The chemical substance code
        
    Returns:
        dict: Dictionary mapping dates to ICB spending data
        
    Raises:
        Exception: If the API request fails
    """
    api_url = f"https://openprescribing.net/api/1.0/spending_by_org/?format=json&org_type=icb&code={chemical_code}"
    
    try:
        response = requests.get(api_url)
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
        raise Exception(f"Failed to fetch spending data from API: {e}")


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
        api_url = f"https://openprescribing.net/api/1.0/org_details/?format=json&org_type=icb&keys=total_list_size&date={year_month}-01"
        
        try:
            response = requests.get(api_url)
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
    """Main function to handle command-line arguments and execute the tool."""
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
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()