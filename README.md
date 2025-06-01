# OpenPrescribing Command-Line Tool

A command-line tool that uses the OpenPrescribing API to retrieve information about prescribing of particular drugs and analyze prescribing patterns across England.

## Installation

### Prerequisites
- Python 3.6 or higher
- pip (Python package installer)

### Dependencies
Install the required dependencies using pip:

```bash
pip install requests
```

### Setup
Make the script executable:

```bash
chmod +x optool.py
```

## Usage

### Part 1 & 2: Chemical name and ICB prescribing data

The tool takes a full 15-character BNF code and:
1. Returns the name of the chemical substance
2. Shows which ICB prescribed the most of this chemical each month

```bash
python optool.py 1304000H0AAAAAA
```

or if you've made it executable:

```bash
./optool.py 1304000H0AAAAAA
```

Expected output:
```
Clobetasone butyrate

2024-01-01 NHS GREATER MANCHESTER INTEGRATED CARE BOARD
2024-02-01 NHS NORTH EAST AND NORTH CUMBRIA INTEGRATED CARE BOARD
2024-03-01 NHS GREATER MANCHESTER INTEGRATED CARE BOARD
...
```

### Part 3: Weighted by population

To weight the results by population size (items per patient), use the `--weighted` flag:

```bash
python optool.py --weighted 1304000H0AAAAAA
```

Expected output:
```
Clobetasone butyrate

2024-01-01 NHS DEVON INTEGRATED CARE BOARD
2024-02-01 NHS DEVON INTEGRATED CARE BOARD
2024-03-01 NHS DEVON INTEGRATED CARE BOARD
...
```

With the weighted option, the tool calculates the prescribing rate per patient for each ICB, taking into account the different population sizes.

## Running Tests

Run the test suite using:

```bash
python -m unittest test_optool.py
```

For verbose output:

```bash
python -m unittest test_optool.py -v
```

## Code Structure

The tool is organized into the following main functions:

1. **`extract_chemical_code(bnf_code)`**: Extracts the 9-character chemical substance code from the full 15-character BNF code. According to the BNF code structure, the chemical code is the first 9 characters.

2. **`get_chemical_name(chemical_code)`**: Makes an API call to the OpenPrescribing API to retrieve the name of the chemical substance. It uses the `bnf_code` endpoint with exact matching to ensure we get the correct chemical.

3. **`get_spending_data(chemical_code)`**: Retrieves spending data for the chemical across all ICBs over the last 5 years using the `spending_by_org` endpoint.

4. **`find_top_prescriber_by_month(spending_data)`**: Analyzes the spending data to find which ICB prescribed the most items of the chemical for each month.

5. **`get_icb_list_sizes(org_ids, dates)`**: Retrieves the total list size (patient population) for ICBs for specific months using the `org_details` endpoint.

6. **`find_top_prescriber_by_month_weighted(spending_data, list_sizes)`**: Calculates items per patient for each ICB and finds the one with the highest rate for each month.

7. **`main()`**: The entry point that handles command-line arguments, orchestrates the workflow, and provides error handling.

## Design Decisions

### Error Handling
- **Input validation**: The tool validates that the BNF code is exactly 15 characters before processing.
- **API errors**: Network errors and API failures are caught and reported with user-friendly error messages.
- **Data validation**: The tool checks for exact matches in the API response to ensure accuracy.

### API Integration
- Used the `q` parameter (not `param`) as specified in the API documentation.
- For Part 1: Uses the `bnf_code` endpoint with `exact=true` to find the chemical name.
- For Part 2: Uses the `spending_by_org` endpoint with `org_type=icb` to get ICB-level data.

### Data Processing
- Spending data is organized by date for efficient processing.
- When there's a tie in the number of items prescribed, the first ICB in the API response is selected (as specified in the requirements).
- Results are sorted chronologically for easy reading.
- For weighted calculations:
  - The tool fetches total list sizes for each ICB for each month
  - Calculates items per patient (items / total_list_size)
  - Handles edge cases where list size might be 0 or unavailable
  - List sizes are fetched month by month as they change over time

### User Experience
- Clear error messages are provided to stderr when things go wrong.
- The tool exits with code 1 on error and 0 on success, following Unix conventions.
- Output format follows the specification exactly, with the chemical name followed by a blank line and then the monthly ICB data.

### Testing Strategy
- Unit tests cover the core functionality including:
  - BNF code validation and extraction
  - API integration with mocked responses
  - Spending data processing
  - Top prescriber identification
  - Error handling scenarios
  - End-to-end command-line interface testing

### Code Style
- Clear function names and comprehensive docstrings
- Follows PEP 8 style guidelines
- Modular design allows easy extension for Part 3

## Example BNF Codes for Testing

- `1304000H0AAAAAA` - Clobetasone butyrate
- `0212000AAAAAIAI` - Rosuvastatin calcium
- `0407010ADBCAAAB` - Paracetamol and ibuprofen
- `0301020I0BBAFAF` - Ipratropium bromide
- `040702040BEABAC` - Tramadol hydrochloride