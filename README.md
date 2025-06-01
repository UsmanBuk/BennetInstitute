# OpenPrescribing Tool

A command-line tool that uses the OpenPrescribing API to retrieve information about prescribing of particular drugs and calculate how this varies around the country.

## Features

- Look up chemical substance names from BNF (British National Formulary) codes
- Analyze prescribing data by ICB (Integrated Care Board)
- Find the ICB with the highest prescribing rate for a given chemical each month
- Optional population-weighted analysis to account for different ICB sizes

## Installation

### Prerequisites

- Python 3.7 or higher
- pip package manager

### Dependencies

Install the required packages:

```bash
pip install -r requirements.txt
```

Or install manually:

```bash
pip install requests
```

### Development Dependencies

For running tests:

```bash
pip install pytest
```

## Usage

### Basic Usage

Look up a chemical name and find top prescribing ICBs:

```bash
python optool.py 1304000H0AAAAAA
```

Output:
```
Clobetasone butyrate

2024-01-01 NHS GREATER MANCHESTER INTEGRATED CARE BOARD
2024-02-01 NHS NORTH EAST AND NORTH CUMBRIA INTEGRATED CARE BOARD
...
```

### Population-Weighted Analysis

To weight results by ICB population size (items per patient):

```bash
python optool.py --weighted 1304000H0AAAAAA
```

This provides a more accurate comparison by accounting for the different numbers of patients in each ICB.

### Example BNF Codes

You can test the tool with these example codes:
- `1304000H0AAAAAA` - Clobetasone butyrate
- `0212000AAAAAIAI` - Atenolol
- `0407010ADBCAAAB` - Paracetamol
- `0301020I0BBAFAF` - Salbutamol
- `040702040BEABAC` - Morphine

## Code Structure

### Main Components

- **`extract_chemical_code()`**: Extracts the chemical substance code from a full 15-character BNF code
- **`get_chemical_name()`**: Queries the OpenPrescribing API to retrieve the chemical name
- **`get_spending_data()`**: Fetches prescribing data for all ICBs over the available time period
- **`find_top_prescriber_by_month()`**: Identifies the ICB with the highest number of items prescribed each month
- **`find_top_prescriber_by_month_weighted()`**: Calculates prescribing rates per patient using ICB population data
- **`get_icb_list_sizes()`**: Retrieves population (list size) data for ICBs to enable weighted analysis

### Error Handling

The tool includes custom exceptions for different error scenarios:
- `InvalidInputError`: For invalid BNF codes
- `DataNotFoundError`: When requested data doesn't exist
- `APIError`: For API communication failures

## Design Decisions

### Chemical Code Extraction

The tool attempts to extract chemical codes using both 9 and 7 character lengths. According to BNF structure, the chemical code is typically the first 9 characters, but we check both lengths to handle edge cases. This approach ensures compatibility with various BNF code formats.

### API Error Handling

The tool implements graceful error handling with user-friendly messages. API failures are caught and reported clearly, with the tool continuing to process partial data where possible (e.g., if some monthly data fails to load).

### Population Weighting

The weighted analysis fetches list sizes for each month separately, as ICB populations can change over time. This ensures accurate per-patient calculations even as populations shift.

### Performance Considerations

- API calls are made with appropriate timeouts to prevent hanging
- The tool processes data efficiently using dictionaries for O(1) lookups
- Error handling allows partial data processing to continue when some API calls fail

## Testing

Run the test suite:

```bash
pytest test_optool.py
```

For verbose output:

```bash
pytest -v test_optool.py
```

The test suite includes:
- Unit tests for all major functions
- Mock API responses to test without network dependencies
- Edge case handling (empty data, ties, missing data)
- Error condition testing

## Production Considerations

This tool is designed as a prototype. For production use, consider:

- **Caching**: Implement response caching to reduce API load
- **Retry Logic**: Add exponential backoff for failed requests
- **Logging**: Replace print statements with structured logging
- **Configuration**: Move API URLs and timeouts to environment variables
- **Rate Limiting**: Respect API rate limits with appropriate delays
- **Async Operations**: Consider parallel API calls for better performance
- **Monitoring**: Add metrics and alerting for API failures

## API Documentation

This tool uses the OpenPrescribing API. For more information:
- API Documentation: https://openprescribing.net/api/
- BNF Code Structure: https://www.bennett.ox.ac.uk/blog/2017/04/prescribing-data-bnf-codes/

## License

This project was created as part of a coding assessment for the Bennett Institute.