# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Home Assistant integration for New Zealand's WITS (Wholesale Information Trading System) electricity spot price data. The integration connects to the WITS API using direct OAuth2 client credentials authentication to provide real-time electricity pricing information.

## Development Commands

Since this is a Home Assistant integration, standard Home Assistant development commands apply:

1. **Code Quality**: `pre-commit run --all-files` (run all linters)
2. **Type Checking**: `mypy homeassistant/components/nz_wits`
3. **Testing**: `pytest tests/components/nz_wits/ --cov=homeassistant.components.nz_wits`
4. **Validation**: `python -m script.hassfest --integration nz_wits`

## Architecture

### Core Components

- **`__init__.py`**: Integration entry point, creates API client and coordinator, handles setup/teardown
- **`api.py`**: Direct WITS API client with OAuth2 client credentials authentication
- **`coordinator.py`**: Data update coordinator managing API calls and caching
- **`sensor.py`**: Sensor entities for the four pricing schedules
- **`config_flow.py`**: Configuration flow for UI-based credential entry and options
- **`const.py`**: Constants, schedule definitions, and node options

### Data Flow

1. **Authentication**: Direct OAuth2 client credentials flow to obtain access tokens
2. **Setup**: Integration creates API client → coordinator → sensor entities
3. **Data Fetching**: Coordinator fetches data for all enabled schedule types every 5 minutes
4. **Entity Updates**: Sensor entities read from coordinator's cached data via `entry.runtime_data`
5. **Error Handling**: Graceful handling of auth failures and connection issues

### Schedule Types

The integration creates sensors for four distinct pricing schedules:

- **RTD (Real Time Dispatch)**: Current 5-minute spot price
- **Interim**: Provisional price for previous trading period  
- **PRSS (Price Responsive Schedule Short)**: 3-hour price forecast
- **PRSL (Price Responsive Schedule Long)**: 24-hour price forecast

### Key Configuration

- **Client ID**: OAuth2 client ID from WITS developer portal
- **Client Secret**: OAuth2 client secret from WITS developer portal
- **Node**: The grid exit point (GXP) identifier (e.g., "TGA0331")
- **Update Options**: Toggle switches for which schedules to enable

### API Integration

- **Base URL**: `https://api.electricityinfo.co.nz`
- **Authentication**: Direct OAuth2 client credentials with automatic token refresh
- **Token Management**: Automatic retry on 401 responses
- **Rate Limiting**: Built-in through coordinator update intervals (5 minutes)
- **Error Recovery**: Proper exception handling for network and auth issues

## File Structure

```
homeassistant/components/nz_wits/
├── __init__.py          # Integration setup, API client and coordinator creation
├── api.py              # WitsApiClient with direct OAuth2 client credentials
├── coordinator.py      # WitsDataUpdateCoordinator for data management
├── sensor.py           # WitsPriceSensor entities for each schedule
├── config_flow.py      # NzWitsConfigFlow for credential input and options
├── const.py            # Domain, schedule types, node options, config constants
├── manifest.json       # Integration metadata (no application_credentials dependency)
└── strings.json        # UI text for config flow and options
```

## Implementation Details

### Authentication Pattern
- Uses direct `WitsApiClient` instead of Home Assistant's OAuth2 helper
- Implements client credentials flow manually with token caching
- No `application_credentials.py` dependency required

### Data Storage Pattern
- API client created in `async_setup_entry`
- Coordinator wraps API client and manages updates
- Coordinator stored in `entry.runtime_data`
- Sensors access coordinator via `entry.runtime_data`

### Configuration Pattern
- Config flow collects Client ID, Client Secret, and Node
- Options flow allows enabling/disabling individual schedule sensors
- Uses dropdown selector for Node selection (major GXPs only)
- Proper validation and error handling in config flow

## Important Notes

- No external dependencies beyond Home Assistant core
- Direct OAuth2 implementation without Home Assistant's oauth2 helper
- Price data converted from MWh to kWh for user convenience
- Forecast data included in sensor attributes for PRSS/PRSL schedules
- Entity availability depends on successful API data retrieval
- Follows Home Assistant integration best practices and quality standards


# Using Gemini CLI for Large Codebase Analysis

When analyzing large codebases or multiple files that might exceed context limits, use the Gemini CLI with its massive
context window. Use `gemini -p` to leverage Google Gemini's large context capacity.

## File and Directory Inclusion Syntax

Use the `@` syntax to include files and directories in your Gemini prompts. The paths should be relative to WHERE you run the
  gemini command:

### Examples:

**Single file analysis:**
gemini -p "@src/main.py Explain this file's purpose and structure"

Multiple files:
gemini -p "@package.json @src/index.js Analyze the dependencies used in the code"

Entire directory:
gemini -p "@src/ Summarize the architecture of this codebase"

Multiple directories:
gemini -p "@src/ @tests/ Analyze test coverage for the source code"

Current directory and subdirectories:
gemini -p "@./ Give me an overview of this entire project"

# Or use --all_files flag:
gemini --all_files -p "Analyze the project structure and dependencies"

Implementation Verification Examples

Check if a feature is implemented:
gemini -p "@src/ @lib/ Has dark mode been implemented in this codebase? Show me the relevant files and functions"

Verify authentication implementation:
gemini -p "@src/ @middleware/ Is JWT authentication implemented? List all auth-related endpoints and middleware"

Check for specific patterns:
gemini -p "@src/ Are there any React hooks that handle WebSocket connections? List them with file paths"

Verify error handling:
gemini -p "@src/ @api/ Is proper error handling implemented for all API endpoints? Show examples of try-catch blocks"

Check for rate limiting:
gemini -p "@backend/ @middleware/ Is rate limiting implemented for the API? Show the implementation details"

Verify caching strategy:
gemini -p "@src/ @lib/ @services/ Is Redis caching implemented? List all cache-related functions and their usage"

Check for specific security measures:
gemini -p "@src/ @api/ Are SQL injection protections implemented? Show how user inputs are sanitized"

Verify test coverage for features:
gemini -p "@src/payment/ @tests/ Is the payment processing module fully tested? List all test cases"

When to Use Gemini CLI

Use gemini -p when:
- Analyzing entire codebases or large directories
- Comparing multiple large files
- Need to understand project-wide patterns or architecture
- Current context window is insufficient for the task
- Working with files totaling more than 100KB
- Verifying if specific features, patterns, or security measures are implemented
- Checking for the presence of certain coding patterns across the entire codebase

Important Notes

- Paths in @ syntax are relative to your current working directory when invoking gemini
- The CLI will include file contents directly in the context
- No need for --yolo flag for read-only analysis
- Gemini's context window can handle entire codebases that would overflow Claude's context
- When checking implementations, be specific about what you're looking for to get accurate results



## Recent Changes (Completed)

### Authentication Migration ✅
- **Issue**: Integration was using Home Assistant's OAuth2 helper which caused "missing_configuration" errors
- **Solution**: Migrated to direct OAuth2 client credentials flow
- **Result**: Integration now works correctly with direct credential input

### Key Files Updated:
- **`api.py`**: Replaced OAuth2 helper with `WitsApiClient` implementing direct client credentials flow
- **`config_flow.py`**: Updated to collect Client ID, Client Secret, and Node directly
- **`__init__.py`**: Removed OAuth2 dependencies, creates API client and coordinator
- **`manifest.json`**: Removed `application_credentials` dependency
- **`const.py`**: Added configuration constants and node options
- **`coordinator.py`**: Simplified to work with new API client
- **`sensor.py`**: Updated to use `entry.runtime_data` for coordinator access
- **Removed**: `application_credentials.py` (no longer needed)

## Next Tasks

Future work will focus on addressing issues from the GitHub repository at https://github.com/cods4/ha-nz-wits including:
- Performance improvements
- Additional features
- Bug fixes
- Enhanced error handling