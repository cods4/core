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
- **Node**: The grid exit point (GXP) identifier from a comprehensive list of 300+ validated nodes
- **Update Options**: Configurable checkboxes for which schedules to enable

### Node Selection

**Comprehensive Coverage**: The integration provides a curated list of 300+ grid nodes that have been validated to return pricing data from the WITS API. This includes nodes across all voltage levels (11kV, 33kV, 66kV, 220kV) covering the entire New Zealand electricity grid.

### Multi-Step Configuration Flow

The integration uses a modern 3-step configuration flow:

1. **Credentials Step**: Enter Client ID and Client Secret with validation
2. **Node Selection Step**: Choose from dropdown of 300+ validated grid nodes
3. **Schedule Selection Step**: Select which price schedules to monitor via checkboxes

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
- Multi-step config flow: credentials → node selection → schedule selection
- Options flow allows enabling/disabling individual schedule sensors and changing nodes
- Uses dropdown selector for Node selection with 300+ validated options
- Configurable schedule checkboxes for user preference
- Proper validation and error handling in config flow

## Important Notes

- No external dependencies beyond Home Assistant core
- Direct OAuth2 implementation without Home Assistant's oauth2 helper
- Price data converted from MWh to kWh for user convenience
- Forecast data included in sensor attributes for PRSS/PRSL schedules
- Entity availability depends on successful API data retrieval
- Follows Home Assistant integration best practices and quality standards

## API Documentation
### Market Prices
openapi: 3.0.2
info:
  title: Market Prices
  description: >+
    Energy prices for PRS and RTP schedules at specified grid points (rolling window -7 to +7TP)

    ## Pre-requisites ##

    See [How To Call Our APIs](guides) for information on registration, authentication and authorisation requirements.

    ## Overview ##

    The purpose of this API is to retrieve market energy or reserve prices for identified schedule(s).


    Pricing information can be filtered in a variety of different ways. The minimum required parameters to filter data are a list of one or more schedules (market run types) and the market type being queried (either `E` for energy prices or `R` for reserve prices).


    * A single schedule can be queried through the `/schedules/{schedule}/prices` path.

    * Multiple schedules can be queried through the `/prices` path, identifying one or more schedules in the `schedules` query parameter.


    Schedules supported by this API can be obtained through a query to `/schedules`.


    In either case, the market type being queried must be included in the `market-type` query parameter.

    * Check out the WITS portal: <https://www2.electricityinfo.co.nz/>


    ## API Parameters ##

    ### Range Requests ###

    Pricing data can be filtered by a combination of trading datetime or sliding trading period ranges.


    The available query parameters for specifying a range are:

    * `from`

    * `to`

    * `back`

    * `forward`


    **From and To**


    The `from` and `to` parameters specify a date-time for which to filter queried data by. None, one or both parameters may be provided. The date-time must conform to the `RFC3339` standard formatting, e.g. `yyyy-MM-dd'T'HH:mm:ssXXX`.


    If both `from` and `to` are provided, this is an inclusive window of time to query data for.


    If a `from` parameter is provided without a corresponding `to` parameter, this represents a query of data filtered from the trading period implied by the `from` date-time forward as far as possible for the queried schedule(s).


    If a `to` parameter is provided without a corresponding `from` parameter, this represents a query of data filtered from the oldest data available forward to the trading period implied by the `to` date-time.


    **Back and Forward**


    Unlike the `from` and `to` parameters, the `back` and `forward` filter can be used to identify a sliding window of data to query. A request cannot include both `from` and/or `to` parameters __and__ `back` and/or `forward`.


    The `back` parameter specifies a number of trading periods _before_ the current trading period to include data for. Correspondingly, the `to` parameter specifies a number of trading periods _ahead_ of the current trading period to include data for.


    For example, if the current trading period is `23` (11:00:00 NZT - 11:29:59 NZT) and both `back` and `forward` are set to `5`, data from trading periods `18` - `28` will be queried. Note that not all schedules will have data available beyond the current trading period.


    ### Node Filters ###

    The pricing data can also be filtered by providing the ID of one or more `nodes` (Grid injection or extraction points) in the corresponding query parameter. If this parameter is included, only data for nodes in the supplied list will be returned.


    Nodes supported by this API can be obtained through a query to `/nodes`.


    ### Island Filter ###

    The data can also be filtered by `Island` (`NI` or `SI`). When the `island` query parameter is set, only information pertaining to that island will be returned.


    ### Pagination ###

    This API supports basic pagination. A maximum of 10,000 records will be returned for any API call. If further data is required, set the `offset` query parameter to retrieve further data. For example, to retrieve the second set of 10,000 records set the `offset` query parameter to `10000`. Subsequently to retrieve the third set of 10,000 records, set the `offset` parameter to `20000`.
  version: 0.0.1


servers:
  - url: 'https://api.electricityinfo.co.nz/api/market-prices/v1'
    variables: {}
    description: Live


security:
  - oAuthClientCredentials: []

paths:

  /schedules:
    get:
      tags:
        - Market Prices
      summary: Retrieve a list of schedules for which pricing data is currently available
      responses:
        "200":
          $ref: '#/components/responses/listSchedulesResponse'
        "400":
          $ref: '#/components/responses/badRequestResponse'
        "403":
          $ref: '#/components/responses/authorisationErrorResponse'
        "405":
          $ref: '#/components/responses/methodNotAllowedResponse'
        "406":
          $ref: '#/components/responses/unacceptableResponse'
        "500":
          $ref: '#/components/responses/internalErrorResponse'


  /schedules/{schedule}/prices:
    parameters:
      - in: path
        name: schedule
        required: true
        schema:
          $ref: '#/components/schemas/schedule'
      - $ref: '#/components/parameters/marketType'
      - $ref: '#/components/parameters/nodes'
      - $ref: '#/components/parameters/from'
      - $ref: '#/components/parameters/to'
      - $ref: '#/components/parameters/back'
      - $ref: '#/components/parameters/forward'
      - $ref: '#/components/parameters/island'
      - $ref: '#/components/parameters/offset'
    get:
      tags:
          - Market Prices
      summary: Retrieve a list of prices for the given schedule
      responses:
        "200":
          $ref: '#/components/responses/getSchedulePricesResponse'
        "400":
          $ref: '#/components/responses/badRequestResponse'
        "403":
          $ref: '#/components/responses/authorisationErrorResponse'
        "404":
          $ref: '#/components/responses/notFoundResponse'
        "405":
          $ref: '#/components/responses/methodNotAllowedResponse'
        "406":
          $ref: '#/components/responses/unacceptableResponse'
        "500":
          $ref: '#/components/responses/internalErrorResponse'

  /nodes:
    get:
      tags:
        - Market Prices
      summary: Retrieve a list of GXP/GIP supported by this API
      responses:
        "200":
          $ref: '#/components/responses/listNodesResponse'
        "400":
          $ref: '#/components/responses/badRequestResponse'
        "403":
          $ref: '#/components/responses/authorisationErrorResponse'
        "405":
          $ref: '#/components/responses/methodNotAllowedResponse'
        "406":
          $ref: '#/components/responses/unacceptableResponse'
        "500":
          $ref: '#/components/responses/internalErrorResponse'

  /prices:
    get:
      tags:
        - Market Prices
      summary: Retrieve a list of prices across schedules
      parameters:
        - $ref: '#/components/parameters/schedules'
        - $ref: '#/components/parameters/marketType'
        - $ref: '#/components/parameters/nodes'
        - $ref: '#/components/parameters/from'
        - $ref: '#/components/parameters/to'
        - $ref: '#/components/parameters/back'
        - $ref: '#/components/parameters/forward'
        - $ref: '#/components/parameters/island'
        - $ref: '#/components/parameters/offset'
      responses:
        "200":
          $ref: '#/components/responses/getPricesResponse'
        "400":
          $ref: '#/components/responses/badRequestResponse'
        "403":
          $ref: '#/components/responses/authorisationErrorResponse'
        "405":
          $ref: '#/components/responses/methodNotAllowedResponse'
        "406":
          $ref: '#/components/responses/unacceptableResponse'
        "500":
          $ref: '#/components/responses/internalErrorResponse'
components:
  securitySchemes:
    oAuthClientCredentials:
      type: oauth2
      description: This API uses OAuth 2 with the client credentials grant flow
      flows:
        clientCredentials:
          tokenUrl: /login/oauth2/token
          scopes: {}

  parameters:

    schedules:
      in: query
      name: schedules
      style: form
      explode: false
      required: true
      schema:
        type: array
        items:
          $ref: '#/components/schemas/schedule'
    marketType:
      in: query
      name: marketType
      schema:
        $ref: '#/components/schemas/marketType'
      required: true
      description: Mandatory market type filter
    nodes:
      in: query
      name: nodes
      style: form
      explode: false
      schema:
        type: array
        items:
          $ref: '#/components/schemas/node'
      required: false
      description: Optional node list filter
    from:
      in: query
      name: from
      schema:
        type: string
        format: datetime
      required: false
      description: Optional trading period to filter historical data
    to:
      in: query
      name: to
      schema:
        type: string
        format: datetime
      required: false
      description: Optional trading period to filter historical data
    back:
      in: query
      name: back
      schema:
        type: integer
        minimum: 1
        maximum: 48
      required: false
      description: Optional trading period filter
    forward:
      in: query
      name: forward
      schema:
        type: integer
        minimum: 1
        maximum: 48
      required: false
      description: Optional trading period filter
    island:
      in: query
      name: island
      schema:
        $ref: '#/components/schemas/island'
      required: false
      description: Return pricing data only for the selected island
    offset:
      in: query
      name: offset
      schema:
        $ref: '#/components/schemas/offset'
      required: false
      description: Optional offset parameter for basic pagination

  responses:

    getPricesResponse:
      description: Successfully received prices
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/getPricesResponse'

    listSchedulesResponse:
      description: Successfully listed schedules
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/listSchedulesResponse'

    listNodesResponse:
      description: Successfully listed schedules
      content:
        application/json:
          schema:
            type: array
            items:
              $ref: '#/components/schemas/node'

    getSchedulePricesResponse:
      description: Successfully received prices
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/scheduleDetails'

    badRequestResponse:
      description: Client has supplied invalid parameters
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/fault'
          examples:
            schemaFailure:
              summary: Invalid API Request
              value:
                status: 400
                code: 'BAD_REQUEST'
                message: 'Invalid Request'
                detail: '52 is greater than maximum 50 for parameter "tradingPeriod"'
                timestamp: '20210406T11:54:33+13:00'
    authorisationErrorResponse:
      description: Resource not found
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/fault'
          examples:
            schemaFailure:
              summary: Client not authorised to access resource
              value:
                status: 403
                code: 'FORBIDDEN'
                message: 'Invalid or missing authorisation token'
                timestamp: '20210406T11:54:33+13:00'
    notFoundResponse:
      description: Resource not found
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/fault'
          examples:
            schemaFailure:
              summary: Schedule not found
              value:
                status: 404
                code: 'NOT_FOUND'
                message: 'Schedule "ABC" not found'
                timestamp: '20210406T11:54:33+13:00'
    methodNotAllowedResponse:
      description: Method not allowed
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/fault'
          examples:
            schemaFailure:
              summary: Invalid accept header
              value:
                status: 405
                code: 'METHOD_NOT_ALLOWED'
                message: 'HTTP Method "PUT" is not valid for this operation'
                timestamp: '20210406T11:54:33+13:00'
    unacceptableResponse:
      description: Content type not produced
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/fault'
          examples:
            schemaFailure:
              summary: Invalid accept header
              value:
                status: 406
                code: 'NOT_ACCEPTABLE'
                message: 'Requested content type "application/xml" is not produced by this API'
                detail: 'Only "application/json" is produced by this API'
                timestamp: '20210406T11:54:33+13:00'
    internalErrorResponse:
      description: Content type not produced
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/fault'
          examples:
            schemaFailure:
              summary: Invalid accept header
              value:
                status: 500
                code: 'INTERNAL_SERVER_ERROR'
                message: 'Internal server error. Please try again later.'
                timestamp: '20210406T11:54:33+13:00'

  schemas:

    schedule:
      type: string
      example: RTP
    marketType:
      type: string
      enum: [E,R]
      example: E
    island:
      type: string
      enum: [NI, SI]
    offset:
      type: integer
      minimum: 0
      description: Optional offset for pagination
      example: 0
      default: 0
    node:
      type: string
      description: |-
        The name of the Grid Injection Point(GIP) or Grid Exit Point (GXP).
        This is the first 8 characters of the Market Node ID.
      example: BEN2202
    runType:
      type: string
      description: Sub-type of schedule
      example: long
    price:
      type: number
      multipleOf: 0.01
      minimum: -1000000000
      maximum: 1000000000
      exclusiveMinimum: true
      exclusiveMaximum: true
      example: 12.34
    tradingDateTime:
      type: string
      format: datetime
      example: '2021-06-16T10:30:00+12:00'
    tradingPeriod:
      type: integer
      minimum: 1
      maximum: 50
      description: |-
        A sequential 30-minute period starting from period 1 at midnight (00:00) and, on most days,
        ending at period 48 at 23:30.  The exceptions to this are on the spring and autumn daylight-time changeover days.
        The spring change-over day is 23 hours long (as the clock jumps forward from 2am to 3am) so only has 46 trading-periods and
        the autumn change-over day is 25 hours long (as the clock jumps back from 3am to 2am) and has 50 trading-periods.
      example: 2
    lastRunTime:
      type: string
      format: datetime
      description: |-
        Solution run-time
      example: '2021-03-16T10:00:00+13:00'

    listSchedulesResponse:
      type: array
      items:
        type: object
        properties:
          schedule:
            $ref: '#/components/schemas/schedule'
          runType:
            $ref: '#/components/schemas/runType'
          marketType:
            $ref: '#/components/schemas/marketType'

    getPricesResponse:
      type: object
      required:
        - schedules
      properties:
        schedules:
          type: array
          items:
            $ref: '#/components/schemas/scheduleDetails'

    scheduleDetails:
      type: object
      required:
        - schedule
        - prices
      properties:
        schedule:
          $ref: '#/components/schemas/schedule'
        prices:
          type: array
          items:
            $ref: '#/components/schemas/priceDetails'

    priceDetails:
      type: object
      description: Price list retrieved
      required:
        - tradingDateTime
        - tradingPeriod
        - runTime
        - node
      properties:
        schedule:
          $ref: '#/components/schemas/schedule'
        tradingDateTime:
          $ref: '#/components/schemas/tradingDateTime'
        tradingPeriod:
          $ref: '#/components/schemas/tradingPeriod'
        runType:
          $ref: '#/components/schemas/runType'
        lastRunTime:
          $ref: '#/components/schemas/lastRunTime'
        node:
          $ref: '#/components/schemas/node'
        price:
          $ref: '#/components/schemas/price'
        price6s:
          $ref: '#/components/schemas/price'
        price60s:
          $ref: '#/components/schemas/price'
        reserveNode:
          $ref: '#/components/schemas/node'
    fault:
      description: Standard fault model
      type: object
      required:
        - status
        - code
        - message
        - timestamp
      properties:
        status:
          type: integer
          minimum: 100
          maximum: 599
          description: The HTTP Status code of the response
          example: 404
        code:
          type: string
          description: Application specific error code
          example: INVALID_NODE
        message:
          type: string
          description: Basic error message
          example: Schedule 'XYZ' is not valid
        detail:
          type: string
          description: Extended error details
        timestamp:
          type: string
          format: datetime
          description: Server timestamp of failure
          example: '20210325T10:00:00+13:00'

### Energy and Reserve Quantities
openapi: 3.0.2
info:
  title: Energy and Reserve Quantities
  description: >+
    PRS schedule, NI and SI (rolling window -24 to +24 TP)

    ## Pre-requisites ##

    See [How To Call Our APIs](guides) for information on registration, authentication and authorisation requirements.

    ## Overview ##

    The purpose of this API is to retrieve energy and reserve quantities for identified schedule(s).


    Quantity information can be filtered in a variety of different ways. The minimum required parameters to filter data are a list of one or more schedules (market run types) and the market type being queried (Energy or Reserves).


    * Energy quantities for a single schedule can be queried through the `/schedules/{schedule}/energy` path.

    * Reserve quantities for a single schedule can be queried through the `/schedules/{schedule}/reserves` path.

    * Energy quantities for multiple schedules can be queried through the `/energy` path, identifying one or more schedules in the `schedules` query parameter.

    * Reserve quantities for multiple schedules can be queried through the `/reserves` path, identifying one or more schedules in the `schedules` query parameter.

    Schedules supported by this API can be obtained through a query to `/schedules`.

    * Check out the WITS portal: <https://www2.electricityinfo.co.nz/>


    ## API Parameters ##

    ### Run Class Filter ###

    Reserve Quantities must include a `runClass` filter. This query parameter must be set to one of `InstantaneousReserve`, `ReserveOffers` or `AdjustedReserveOffers`.


    ### Range Requests ###

    Quantity data can be filtered using date-times for absolute windows, or by period offsets for rolling windows.


    The available query parameters for specifying a range are:

    * `from`

    * `to`

    * `back`

    * `forward`


    **From and To**


    The `from` and `to` parameters specify a date-time for which to filter queried data by. None, one or both parameters may be provided. The date-time must conform to the `RFC3339` standard formatting, e.g. `yyyy-MM-dd'T'HH:mm:ssXXX`.


    If both `from` and `to` are provided, this is an inclusive window of time to query data for.


    If a `from` parameter is provided without a corresponding `to` parameter, this represents a query of data filtered from the trading period implied by the `from` date-time forward as far as possible for the queried schedule(s).


    If a `to` parameter is provided without a corresponding `from` parameter, this represents a query of data filtered from the oldest data available forward to the trading period implied by the `to` date-time.


    **Back and Forward**


    Unlike the `from` and `to` parameters, the `back` and `forward` filter can be used to identify a sliding window of data to query. A request cannot include both `from` and/or `to` parameters __and__ `back` and/or `forward`.


    The `back` parameter specifies a number of trading periods _before_ the current trading period to include data for. Correspondingly, the `to` parameter specifies a number of trading periods _ahead_ of the current trading period to include data for.


    For example, if the current trading period is `23` (11:00:00 NZT - 11:29:59 NZT) and both `back` and `forward` are set to `5`, data from trading periods `18` - `28` will be queried. Note that not all schedules will have data available beyond the current trading period.

    ### Island Filter ###

    The data can also be filtered by `Island` (`NI` or `SI`). When the `island` query parameter is set, only information pertaining to that island will be returned.

  version: 0.0.1

servers:
  - url: 'https://api.electricityinfo.co.nz/api/quantities/v1'
    variables: {}
    description: Live

security:
  - oAuthClientCredentials: []

paths:

  /schedules:
    get:
      tags:
        - Energy
        - Reserves
      summary: Retrieve a list of schedules for which quantity data is currently available
      responses:
        "200":
          $ref: '#/components/responses/listSchedulesResponse'
        "400":
          $ref: '#/components/responses/badRequestResponse'
        "403":
          $ref: '#/components/responses/authorisationErrorResponse'
        "405":
          $ref: '#/components/responses/methodNotAllowedResponse'
        "406":
          $ref: '#/components/responses/unacceptableResponse'
        "500":
          $ref: '#/components/responses/internalErrorResponse'


  /schedules/{schedule}/energy:
    parameters:
      - in: path
        name: schedule
        required: true
        schema:
          $ref: '#/components/schemas/schedule'
      - $ref: '#/components/parameters/from'
      - $ref: '#/components/parameters/to'
      - $ref: '#/components/parameters/back'
      - $ref: '#/components/parameters/forward'
      - $ref: '#/components/parameters/island'
    get:
      tags:
        - Energy
      summary: Retrieve a list of energy quantities for the given schedule
      responses:
        "200":
          $ref: '#/components/responses/getScheduleEnergyQuantitiesResponse'
        "400":
          $ref: '#/components/responses/badRequestResponse'
        "403":
          $ref: '#/components/responses/authorisationErrorResponse'
        "404":
          $ref: '#/components/responses/notFoundResponse'
        "405":
          $ref: '#/components/responses/methodNotAllowedResponse'
        "406":
          $ref: '#/components/responses/unacceptableResponse'
        "500":
          $ref: '#/components/responses/internalErrorResponse'

  /schedules/{schedule}/reserves:
    parameters:
      - in: path
        name: schedule
        required: true
        schema:
          $ref: '#/components/schemas/schedule'
      - $ref: '#/components/parameters/runClass'
      - $ref: '#/components/parameters/from'
      - $ref: '#/components/parameters/to'
      - $ref: '#/components/parameters/back'
      - $ref: '#/components/parameters/forward'
      - $ref: '#/components/parameters/island'
    get:
      tags:
        - Reserves
      summary: Retrieve a list of reserve quantities for the given schedule
      responses:
        "200":
          $ref: '#/components/responses/getScheduleReserveQuantitiesResponse'
        "400":
          $ref: '#/components/responses/badRequestResponse'
        "403":
          $ref: '#/components/responses/authorisationErrorResponse'
        "404":
          $ref: '#/components/responses/notFoundResponse'
        "405":
          $ref: '#/components/responses/methodNotAllowedResponse'
        "406":
          $ref: '#/components/responses/unacceptableResponse'
        "500":
          $ref: '#/components/responses/internalErrorResponse'

  /energy:
    get:
      summary: Retrieve a list of energy quantities across schedules
      tags:
        - Energy
      parameters:
        - $ref: '#/components/parameters/schedules'
        - $ref: '#/components/parameters/from'
        - $ref: '#/components/parameters/to'
        - $ref: '#/components/parameters/back'
        - $ref: '#/components/parameters/forward'
        - $ref: '#/components/parameters/island'
      responses:
        "200":
          $ref: '#/components/responses/getEnergyResponse'
        "400":
          $ref: '#/components/responses/badRequestResponse'
        "403":
          $ref: '#/components/responses/authorisationErrorResponse'
        "405":
          $ref: '#/components/responses/methodNotAllowedResponse'
        "406":
          $ref: '#/components/responses/unacceptableResponse'
        "500":
          $ref: '#/components/responses/internalErrorResponse'

  /reserves:
    get:
      summary: Retrieve a list of reserve quantities across schedules
      tags:
        - Reserves
      parameters:
        - $ref: '#/components/parameters/schedules'
        - $ref: '#/components/parameters/runClass'
        - $ref: '#/components/parameters/from'
        - $ref: '#/components/parameters/to'
        - $ref: '#/components/parameters/back'
        - $ref: '#/components/parameters/forward'
        - $ref: '#/components/parameters/island'
      responses:
        "200":
          $ref: '#/components/responses/getReservesResponse'
        "400":
          $ref: '#/components/responses/badRequestResponse'
        "403":
          $ref: '#/components/responses/authorisationErrorResponse'
        "405":
          $ref: '#/components/responses/methodNotAllowedResponse'
        "406":
          $ref: '#/components/responses/unacceptableResponse'
        "500":
          $ref: '#/components/responses/internalErrorResponse'

components:
  securitySchemes:
    oAuthClientCredentials:
      type: oauth2
      description: This API uses OAuth 2 with the client credentials grant flow
      flows:
        clientCredentials:
          tokenUrl: /login/oauth2/token
          scopes: {}

  parameters:

    schedules:
      in: query
      name: schedules
      style: form
      explode: false
      required: true
      schema:
        type: array
        items:
          $ref: '#/components/schemas/schedule'
    from:
      in: query
      name: from
      schema:
        type: string
        format: datetime
      required: false
      description: Optional trading date-time to filter historical data
    to:
      in: query
      name: to
      schema:
        type: string
        format: datetime
      required: false
      description: Optional trading date-time to filter historical data
    back:
      in: query
      name: back
      schema:
        type: integer
        minimum: 1
        maximum: 48
      required: false
      description: Optional trading period filter
    forward:
      in: query
      name: forward
      schema:
        type: integer
        minimum: 1
        maximum: 48
      required: false
      description: Optional trading period filter
    island:
      in: query
      name: island
      schema:
        $ref: '#/components/schemas/island'
      required: false
      description: Return quantity data only for the selected island
    runClass:
      in: query
      name: runClass
      schema:
        $ref: '#/components/schemas/runClass'
      required: true
      description: Mandatory run class filter

  responses:

    listSchedulesResponse:
      description: Successfully listed schedules
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/listSchedulesResponse'

    getEnergyResponse:
      description: Successfully received energy quantities
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/getEnergyQuantitiesResponse'

    getReservesResponse:
      description: Successfully received reserve quantities
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/getReserveQuantitiesResponse'

    getScheduleEnergyQuantitiesResponse:
      description: Successfully received energy quantities
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/energyScheduleDetails'

    getScheduleReserveQuantitiesResponse:
      description: Successfully received reserve quantities
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/reserveScheduleDetails'

    badRequestResponse:
      description: Client has supplied invalid parameters
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/fault'
          examples:
            schemaFailure:
              summary: Invalid API Request
              value:
                status: 400
                code: 'BAD_REQUEST'
                message: 'Invalid Request'
                detail: '52 is greater than maximum 50 for parameter "tradingPeriod"'
                timestamp: '20210406T11:54:33+13:00'
    authorisationErrorResponse:
      description: Resource not found
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/fault'
          examples:
            schemaFailure:
              summary: Client not authorised to access resource
              value:
                status: 403
                code: 'FORBIDDEN'
                message: 'Invalid or missing authorisation token'
                timestamp: '20210406T11:54:33+13:00'
    notFoundResponse:
      description: Resource not found
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/fault'
          examples:
            schemaFailure:
              summary: Schedule not found
              value:
                status: 404
                code: 'NOT_FOUND'
                message: 'Schedule "ABC" not found'
                timestamp: '20210406T11:54:33+13:00'
    methodNotAllowedResponse:
      description: Method not allowed
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/fault'
          examples:
            schemaFailure:
              summary: Invalid accept header
              value:
                status: 405
                code: 'METHOD_NOT_ALLOWED'
                message: 'HTTP Method "PUT" is not valid for this operation'
                timestamp: '20210406T11:54:33+13:00'
    unacceptableResponse:
      description: Content type not produced
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/fault'
          examples:
            schemaFailure:
              summary: Invalid accept header
              value:
                status: 406
                code: 'NOT_ACCEPTABLE'
                message: 'Requested content type "application/xml" is not produced by this API'
                detail: 'Only "application/json" is produced by this API'
                timestamp: '20210406T11:54:33+13:00'
    internalErrorResponse:
      description: Content type not produced
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/fault'
          examples:
            schemaFailure:
              summary: Invalid accept header
              value:
                status: 500
                code: 'INTERNAL_SERVER_ERROR'
                message: 'Internal server error. Please try again later.'
                timestamp: '20210406T11:54:33+13:00'

  schemas:

    listSchedulesResponse:
      type: object
      required:
        - reserveSchedules
        - energySchedules
      properties:
        reserveSchedules:
          type: array
          items:
            type: string
          example:
            - NRS
            - PRS
        energySchedules:
          type: array
          items:
            type: string
          example:
            - NRS
            - PRS
            - WDS

    getEnergyQuantitiesResponse:
      type: object
      required:
        - schedules
      properties:
        schedules:
          type: array
          items:
            $ref: '#/components/schemas/energyScheduleDetails'

    getReserveQuantitiesResponse:
      type: object
      required:
        - schedules
      properties:
        schedules:
          type: array
          items:
            $ref: '#/components/schemas/reserveScheduleDetails'

    energyScheduleDetails:
      type: object
      required:
        - schedule
        - energyQuantities
      properties:
        schedule:
          $ref: '#/components/schemas/schedule'
        energyQuantities:
          type: array
          items:
            $ref: '#/components/schemas/energyQuantitityDetails'

    reserveScheduleDetails:
      type: object
      required:
        - schedule
        - energyQuantities
      properties:
        schedule:
          $ref: '#/components/schemas/schedule'
        reserveQuantities:
          type: array
          items:
            $ref: '#/components/schemas/reserveQuantitityDetails'

    energyQuantitityDetails:
      allOf:
        - $ref: '#/components/schemas/baseQuantityDetails'
        - type: object
          properties:
            load:
              type: number
              example: 4191.901
            generation:
              type: number
              example: 2829.590
            intermittentGeneration:
              type: number
              example: 813.578
            totalBids:
              type: number
              example: 2324
            totalOffers:
              type: number
              example: 8465
            intermittentOffers:
              type: number
              example: 165

    reserveQuantitityDetails:
      allOf:
        - $ref: '#/components/schemas/baseQuantityDetails'
        - type: object
          properties:
            runType:
              type: string
              maxLength: 1
              example: N
            reserveClass:
              type: string
              example: F
            runClass:
              type: string
              example: R2
            price:
              $ref: '#/components/schemas/price'
            reserveMw:
              type: number
              example: 344.773
            riskMw:
              type: number
              example: 12.43
            riskAdjustmentFactor:
              type: number
              example: 33.43

    baseQuantityDetails:
      type: object
      required:
        - tradingDateTime
        - tradingPeriod
        - schedule
      properties:
        tradingDateTime:
          $ref: '#/components/schemas/tradingDateTime'
        tradingPeriod:
          $ref: '#/components/schemas/tradingPeriod'
        schedule:
          $ref: '#/components/schemas/schedule'
        island:
          $ref: '#/components/schemas/island'

    schedule:
      type: string
      example: NRS

    island:
      type: string
      enum: [NI, SI]

    runClass:
      type: string
      enum: [InstantaneousReserve, ReserveOffers, AdjustedReserveOffers]

    tradingDateTime:
      type: string
      format: datetime
      example: '2021-06-16T10:30:00+12:00'

    tradingPeriod:
      type: integer
      minimum: 1
      maximum: 50
      description: |-
        A sequential 30-minute period starting from period 1 at midnight (00:00) and, on most days,
        ending at period 48 at 23:30.  The exceptions to this are on the spring and autumn daylight-time changeover days.
        The spring change-over day is 23 hours long (as the clock jumps forward from 2am to 3am) so only has 46 trading-periods and
        the autumn change-over day is 25 hours long (as the clock jumps back from 3am to 2am) and has 50 trading-periods.
      example: 2

    price:
      type: number
      multipleOf: 0.01
      minimum: -1000000000
      maximum: 1000000000
      exclusiveMinimum: true
      exclusiveMaximum: true
      example: 12.34

    fault:
      description: Standard fault model
      type: object
      required:
        - status
        - code
        - message
        - timestamp
      properties:
        status:
          type: integer
          minimum: 100
          maximum: 599
          description: The HTTP Status code of the response
          example: 404
        code:
          type: string
          description: Application specific error code
          example: INVALID_NODE
        message:
          type: string
          description: Basic error message
          example: Schedule 'XYZ' is not valid
        detail:
          type: string
          description: Extended error details
        timestamp:
          type: string
          format: datetime
          description: Server timestamp of failure
          example: '20210325T10:00:00+13:00'


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

### Dynamic Node Selection & Enhanced Configuration ✅
- **Issue**: User requested dynamic node selection from API and configurable price types
- **Solution**: Implemented comprehensive node list and multi-step config flow
- **Result**: 300+ validated nodes available with checkbox-based schedule selection

### Key Implementation Details:

#### Enhanced Configuration Flow:
- **Multi-step flow**: credentials → node selection → schedule selection
- **Dynamic API methods**: `get_available_nodes()` and `get_available_schedules()`
- **Comprehensive node coverage**: 300+ validated GXP nodes across New Zealand
- **Configurable schedules**: Checkbox selection for RTD, Interim, PRSS, PRSL

#### API Discovery & Validation:
- **API Testing**: Comprehensive testing revealed WITS API limitations
- **Node Validation**: All 300+ nodes tested and confirmed to return pricing data
- **Fallback Strategy**: Uses validated static list when API discovery fails
- **Island Filtering**: Originally planned but removed due to API limitations

#### Error Resolution:
- **Deprecation Fix**: Resolved `config_entry` assignment issue in OptionsFlow
- **Selector Validation**: Fixed node parsing to handle API response variations
- **Form Submission**: Resolved schedule selection form not submitting
- **Field Display**: Ensured proper form schema without unexpected fields

#### Quality Improvements:
- **Home Assistant Compliance**: Added `quality_scale.yaml` for Bronze tier compliance
- **Best Practices**: Follows modern Home Assistant integration patterns
- **Error Handling**: Robust exception handling and graceful API fallbacks
- **User Experience**: Clear multi-step flow with descriptive text

### File Updates Summary:
- **`api.py`**: Added dynamic node/schedule fetching with robust parsing
- **`config_flow.py`**: Complete rewrite for 3-step flow with proper state management
- **`const.py`**: Added 300+ validated nodes and configuration constants
- **`strings.json`**: Updated UI text for multi-step flow
- **`quality_scale.yaml`**: Added for Home Assistant quality compliance

## Current Status

✅ **Fully Functional**: Integration supports complete configuration workflow
✅ **Production Ready**: Follows Home Assistant best practices and quality standards
✅ **User Friendly**: Intuitive multi-step configuration with comprehensive options
✅ **Robust**: Handles API limitations with validated fallbacks

## NordPool Integration Analysis & Improvement Roadmap

Based on comprehensive analysis of the similar NordPool integration (Platinum quality scale), the following improvements have been identified for the NZ WITS integration:

In addition to the below... I see that nordpool uses this python library https://github.com/gjohansson-ST/pynordpool. Is it necessary to create something similar for nz-wits or not? Why?

### Phase 1: Essential Missing Features (Bronze/Silver Quality)

#### 1. Diagnostics Implementation
- **Missing**: Complete diagnostics system for debugging and support
- **NordPool Advantage**: Comprehensive diagnostics with API data, coordinator status, and error tracking
- **Implementation**: Create `diagnostics.py` with redacted sensitive data and full system state

#### 2. Entity Structure Enhancement
- **Missing**: Dedicated base entity class and proper device organization
- **NordPool Advantage**: `NordpoolBaseEntity` class with shared functionality and device-based organization
- **Implementation**: Create `entity.py` with `NzWitsBaseEntity` for consistent entity behavior

#### 3. Translation Support
- **Missing**: Entity name translations and icon configuration
- **NordPool Advantage**: Full translation support for entity names, descriptions, and dynamic icons
- **Implementation**: Enhance `strings.json` and create `icons.json` for proper internationalization

### Phase 2: Advanced Data Processing (Gold Quality)

#### 4. Enhanced Price Analytics
- **Missing**: Price statistics, forecasting analysis, and historical comparisons
- **NordPool Advantage**: Complex price calculations (min/max, averages, block prices, trends)
- **Implementation**: Add price analysis functions with forecast summaries and statistical calculations

#### 5. Service Implementation
- **Missing**: External services for historical data and node information
- **NordPool Advantage**: `get_prices_for_date` service with comprehensive data retrieval
- **Implementation**: Create `services.py` with historical price retrieval and node discovery services

#### 6. Multiple Entity Types
- **Missing**: Specialized sensors for different data aspects
- **NordPool Advantage**: Multiple sensor types (current, average, min/max prices) with entity descriptions
- **Implementation**: Enhanced sensor architecture with `NzWitsSensorEntityDescription` for diverse price metrics

### Phase 3: Production Excellence (Platinum Quality)

#### 7. Advanced Coordinator Features
- **Missing**: Custom scheduling and intelligent error handling
- **NordPool Advantage**: Dynamic update intervals and per-schedule error recovery
- **Implementation**: Enhanced coordinator with schedule-aware timing and partial failure handling

#### 8. Quality Scale Compliance
- **Missing**: Full Platinum compliance (currently partial Gold implementation)
- **NordPool Advantage**: 87 quality rules implemented with comprehensive testing
- **Implementation**: Complete quality scale requirements including strict typing and comprehensive testing

#### 9. Dynamic Configuration
- **Missing**: Runtime node discovery and adaptive configuration
- **NordPool Advantage**: API-driven configuration with fallback strategies
- **Implementation**: Enhanced config flow with real-time API integration and intelligent defaults

### Specific Technical Improvements

#### Data Processing Enhancements
```python
# Price Statistics and Forecasting
- get_price_statistics(): Min/max/average calculations
- get_forecast_summary(): Next hour/3h/6h predictions
- Enhanced extra_state_attributes with rich metadata
```

#### Service Architecture
```python
# Historical Data Access
- get_historical_prices(): Date range price retrieval
- get_node_info(): Dynamic node and schedule discovery
- Comprehensive service validation and error handling
```

#### Entity Management
```python
# Multi-Entity Architecture
- Current price sensor (primary)
- Average price sensor (diagnostic)
- Min/max price sensors (analytical)
- Forecast summary sensors (predictive)
```

### Implementation Priority Matrix

| Feature | Impact | Effort | Priority |
|---------|--------|--------|----------|
| Diagnostics | High | Low | 1 |
| Entity Translations | High | Low | 2 |
| Base Entity Class | Medium | Low | 3 |
| Price Analytics | High | Medium | 4 |
| Service Implementation | Medium | Medium | 5 |
| Advanced Coordinator | High | High | 6 |
| Multiple Entity Types | Medium | High | 7 |

### Quality Scale Progression

**Current State**: Partial Gold (basic functionality with good patterns)
**Target State**: Platinum (feature-complete with advanced capabilities)

**Path to Platinum**:
1. **Bronze Completion**: Add missing diagnostics and basic translations
2. **Silver Achievement**: Implement entity availability and parallel updates
3. **Gold Enhancement**: Add device management, diagnostics, and full translations
4. **Platinum Excellence**: Complete strict typing, async dependencies, and comprehensive testing

### Expected Benefits

#### User Experience
- **Better Debugging**: Comprehensive diagnostics for troubleshooting
- **Richer Data**: Price analytics, forecasts, and historical trends
- **Enhanced Control**: Services for data retrieval and configuration
- **Improved Reliability**: Advanced error handling and partial failure recovery

#### Developer Experience
- **Code Quality**: Cleaner architecture with proper inheritance and typing
- **Maintainability**: Better separation of concerns and comprehensive testing
- **Extensibility**: Foundation for future WITS API endpoints and features
- **Standards Compliance**: Full Home Assistant quality scale adherence

This roadmap transforms the NZ WITS integration from a functional implementation to a comprehensive, production-ready solution matching the sophistication of top-tier Home Assistant integrations.

## Detailed Implementation Patterns from NordPool

### Advanced Coordinator Patterns

#### Custom Time-Based Scheduling
```python
# Enhanced coordinator with intelligent scheduling
def get_next_interval(self, now: datetime) -> datetime:
    """Compute next update based on trading periods."""
    # For RTD: Update every 5 minutes aligned to trading periods
    if self._has_rtd_enabled():
        next_period = now.replace(second=0, microsecond=0) + timedelta(minutes=5)
        # Align to 5-minute boundaries (00:00, 00:05, 00:10, etc.)
        minutes = (next_period.minute // 5 + 1) * 5
        if minutes >= 60:
            next_period = next_period.replace(hour=(next_period.hour + 1) % 24, minute=0)
        else:
            next_period = next_period.replace(minute=minutes)
    else:
        # For forecasts: Update at top of each hour
        next_period = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    return next_period

async def fetch_data(self, now: datetime) -> None:
    """Fetch data with custom scheduling."""
    await self._async_update_data()
    self.unsub = async_track_point_in_utc_time(
        self.hass, self.fetch_data, self.get_next_interval(dt_util.utcnow())
    )
```

#### Data Validation and Filtering
```python
async def _async_update_data(self) -> dict[str, Any]:
    """Enhanced update with validation."""
    try:
        enabled_schedules = self._get_enabled_schedules()
        all_data = {}

        for schedule_type in enabled_schedules:
            data = await self.api_client.get_price_data(schedule_type)

            # Validate data quality
            if self._validate_price_data(data, schedule_type):
                all_data[schedule_type] = data
            else:
                _LOGGER.warning("Invalid data for %s, using cached data", schedule_type)
                if self.data and schedule_type in self.data:
                    all_data[schedule_type] = self.data[schedule_type]

        return all_data

    except Exception as error:
        self.async_set_update_error(error)
        raise UpdateFailed(f"Error fetching WITS data: {error}") from error

def _validate_price_data(self, data: list[dict], schedule_type: str) -> bool:
    """Validate API response data."""
    if not data:
        return False

    required_fields = ["tradingDateTime", "tradingPeriod", "price", "node"]
    for item in data:
        if not all(field in item for field in required_fields):
            return False
        if item.get("price") is None:
            return False
        if not isinstance(item.get("tradingPeriod"), int):
            return False

    return True
```

### Enhanced Entity Architecture

#### Advanced Entity Descriptions with Lambda Functions
```python
@dataclass(frozen=True, kw_only=True)
class NzWitsSensorEntityDescription(SensorEntityDescription):
    """Enhanced entity description for NZ WITS sensors."""

    value_fn: Callable[[WitsPriceSensor], float | None]
    extra_fn: Callable[[WitsPriceSensor], dict[str, Any] | None] = lambda x: None
    schedule_type: str | None = None

# Multi-line lambda implementation for complex calculations
WITS_SENSOR_TYPES = (
    NzWitsSensorEntityDescription(
        key="current_price",
        translation_key="current_price",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        schedule_type=SCHEDULE_RTD,
        value_fn=lambda entity: (
            entity.coordinator.data[SCHEDULE_RTD][0]["price"] / 1000
            if entity.coordinator.data
            and SCHEDULE_RTD in entity.coordinator.data
            and entity.coordinator.data[SCHEDULE_RTD]
            else None
        ),
        extra_fn=lambda entity: {
            "trading_period": entity.coordinator.data[SCHEDULE_RTD][0]["tradingPeriod"],
            "trading_datetime": entity.coordinator.data[SCHEDULE_RTD][0]["tradingDateTime"],
            "node": entity.coordinator.data[SCHEDULE_RTD][0]["node"],
        } if entity.coordinator.data and SCHEDULE_RTD in entity.coordinator.data else {},
    ),
    NzWitsSensorEntityDescription(
        key="average_price_24h",
        translation_key="average_price_24h",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda entity: entity.get_average_price_24h(),
        extra_fn=lambda entity: entity.get_price_statistics(),
    ),
)
```

#### Dynamic Entity Creation Pattern
```python
async def async_setup_entry(
    hass: HomeAssistant, entry: NzWitsConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors dynamically based on configuration."""
    coordinator = entry.runtime_data
    entities: list[NzWitsBaseEntity] = []

    # Get enabled schedules from config
    enabled_schedules = get_enabled_schedules(entry)

    # Create entities for each enabled schedule
    for schedule_type in enabled_schedules:
        # Primary price sensor for each schedule
        entities.append(
            NzWitsPriceSensor(
                coordinator,
                SCHEDULE_SENSOR_DESCRIPTIONS[schedule_type],
                schedule_type,
            )
        )

        # Additional analytical sensors (disabled by default)
        if schedule_type in [SCHEDULE_PRSS, SCHEDULE_PRSL]:
            entities.extend([
                NzWitsForecastSensor(coordinator, desc, schedule_type)
                for desc in FORECAST_SENSOR_TYPES
            ])

    # Global statistics sensors
    entities.extend([
        NzWitsStatisticsSensor(coordinator, desc)
        for desc in STATISTICS_SENSOR_TYPES
    ])

    async_add_entities(entities)
```

### Robust Configuration Flow Patterns

#### Multi-Select with Proper Validation
```python
# Enhanced node selection with grouping
NODE_GROUPS = {
    "North Island - Major": ["BEN2201", "HAM0331", "MLG0331", "OTA0221"],
    "North Island - Regional": ["KAW0111", "TGA0331", "WHI0111"],
    "South Island - Major": ["CYD0331", "HAY2201", "ISL0331"],
    "South Island - Regional": ["COB0661", "ROX2201", "TIM0111"],
}

SELECT_NODES = []
for group, nodes in NODE_GROUPS.items():
    SELECT_NODES.extend([
        SelectOptionDict(value=node, label=f"{node} ({group})")
        for node in nodes
    ])

NODE_SCHEMA = vol.Schema({
    vol.Required(CONF_NODE): SelectSelector(
        SelectSelectorConfig(
            options=SELECT_NODES,
            mode=SelectSelectorMode.DROPDOWN,
            sort=True,
        )
    ),
})
```

#### Comprehensive API Testing
```python
async def test_wits_api(hass: HomeAssistant, user_input: dict[str, Any]) -> dict[str, str]:
    """Test WITS API with comprehensive error handling."""
    session = async_get_clientsession(hass)
    client = WitsApiClient(
        user_input[CONF_CLIENT_ID],
        user_input[CONF_CLIENT_SECRET],
        user_input.get(CONF_NODE, "BEN2201"),
        session,
    )

    try:
        # Test authentication
        await client.test_authentication()

        # Test data retrieval
        await client.get_price_data(SCHEDULE_RTD)

        # Test node availability
        available_nodes = await client.get_available_nodes()
        if user_input.get(CONF_NODE) not in available_nodes:
            return {"base": "node_unavailable"}

    except InvalidAuth:
        return {"base": "invalid_auth"}
    except CannotConnect:
        return {"base": "cannot_connect"}
    except Exception:
        return {"base": "unknown"}

    return {}
```

#### Reconfiguration Flow Support
```python
async def async_step_reconfigure(
    self, user_input: dict[str, Any] | None = None
) -> ConfigFlowResult:
    """Handle reconfiguration."""
    reconfigure_entry = self._get_reconfigure_entry()
    errors: dict[str, str] = {}

    if user_input:
        errors = await test_wits_api(self.hass, user_input)
        if not errors:
            return self.async_update_reload_and_abort(
                reconfigure_entry,
                data_updates=user_input,
                reload_even_if_entry_is_unchanged=False,
            )

    return self.async_show_form(
        step_id="reconfigure",
        data_schema=self.add_suggested_values_to_schema(
            CREDENTIALS_SCHEMA, user_input or reconfigure_entry.data
        ),
        errors=errors,
        description_placeholders={
            "node": reconfigure_entry.data.get(CONF_NODE, "Unknown"),
        },
    )
```

### Advanced Service Implementation

#### Service with Proper Config Entry Validation
```python
def get_config_entry(hass: HomeAssistant, entry_id: str) -> NzWitsConfigEntry:
    """Get and validate config entry."""
    if not (entry := hass.config_entries.async_get_entry(entry_id)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_found",
        )

    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_loaded",
        )

    return entry

SERVICE_GET_HISTORICAL_PRICES_SCHEMA = vol.Schema({
    vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
    vol.Required(ATTR_START_DATE): cv.date,
    vol.Optional(ATTR_END_DATE): cv.date,
    vol.Optional(ATTR_SCHEDULE, default=SCHEDULE_RTD): vol.In(list(SCHEDULE_TYPES.keys())),
    vol.Optional(ATTR_NODE): vol.In(NODE_OPTIONS),
})

async def get_historical_prices(call: ServiceCall) -> ServiceResponse:
    """Get historical WITS prices."""
    entry = get_config_entry(hass, call.data[ATTR_CONFIG_ENTRY])
    start_date: date = call.data[ATTR_START_DATE]
    end_date: date = call.data.get(ATTR_END_DATE, start_date)
    schedule: str = call.data[ATTR_SCHEDULE]
    node: str = call.data.get(ATTR_NODE) or entry.data[CONF_NODE]

    coordinator = entry.runtime_data

    try:
        # Create temporary client for historical data
        historical_client = WitsApiClient(
            entry.data[CONF_CLIENT_ID],
            entry.data[CONF_CLIENT_SECRET],
            node,
            async_get_clientsession(hass),
        )

        historical_data = await historical_client.get_historical_price_data(
            start_date, end_date, schedule
        )

        return {
            "schedule": schedule,
            "node": node,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "prices": [
                {
                    "datetime": item["tradingDateTime"],
                    "period": item["tradingPeriod"],
                    "price_mwh": item["price"],
                    "price_kwh": round(item["price"] / 1000, 5),
                }
                for item in historical_data
            ],
        }

    except InvalidAuth as error:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="service_auth_failed",
        ) from error
    except CannotConnect as error:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="service_connection_failed",
        ) from error
```

### Comprehensive Testing Patterns

#### Mock Setup with Multiple Endpoints
```python
@pytest.fixture(name="mock_wits_api")
async def mock_wits_api_fixture(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> AsyncGenerator[WitsApiClient]:
    """Mock WITS API with comprehensive endpoints."""

    # Mock OAuth2 token endpoint
    aioclient_mock.post(
        "https://api.electricityinfo.co.nz/login/oauth2/token",
        json={"access_token": "test_token", "token_type": "Bearer"},
    )

    # Mock schedules endpoint
    aioclient_mock.get(
        "https://api.electricityinfo.co.nz/api/market-prices/v1/schedules",
        json=[{"schedule": "RTD", "runType": "real_time", "marketType": "E"}],
    )

    # Mock nodes endpoint
    aioclient_mock.get(
        "https://api.electricityinfo.co.nz/api/market-prices/v1/nodes",
        json=["BEN2201", "HAY2201", "TGA0331"],
    )

    # Mock prices endpoint with different schedules
    for schedule in ["RTD", "Interim", "PRSS", "PRSL"]:
        aioclient_mock.get(
            "https://api.electricityinfo.co.nz/api/market-prices/v1/prices",
            json=[{
                "schedule": schedule,
                "prices": load_fixture(f"wits_price_data_{schedule.lower()}.json", DOMAIN)
            }],
        )

    session = async_get_clientsession(hass)
    client = WitsApiClient("test_id", "test_secret", "TGA0331", session)
    yield client
```

#### Parameterized Error Testing
```python
@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (InvalidAuth(), "invalid_auth"),
        (CannotConnect(), "cannot_connect"),
        (asyncio.TimeoutError(), "cannot_connect"),
        (aiohttp.ClientError(), "cannot_connect"),
    ],
)
async def test_config_flow_api_errors(
    hass: HomeAssistant,
    mock_wits_api: WitsApiClient,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test config flow handles all API errors properly."""

    with patch(
        "homeassistant.components.nz_wits.config_flow.WitsApiClient.test_authentication",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_CLIENT_ID: "test", CONF_CLIENT_SECRET: "test"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
```

### Quality Scale Implementation Details

#### Strategic Rule Exemptions
```yaml
# quality_scale.yaml - Enhanced with detailed exemptions
rules:
  # Bronze
  config-flow: done
  entity-unique-id: done
  action-setup:
    status: exempt
    comment: Integration does not register custom actions, only provides sensor data.

  # Silver
  entity-unavailable: done
  parallel-updates: done
  reauthentication-flow: done
  reconfiguration-flow: done

  # Gold
  devices: done
  diagnostics: done
  entity-translations: done
  exception-translations: done
  icon-translations:
    status: exempt
    comment: Integration uses standard electricity/price icons without dynamic selection.

  # Platinum
  strict-typing: done
  async-dependencies: done
  websession-injection: done
```

#### Translation Examples with Placeholders
```json
{
  "entity": {
    "sensor": {
      "current_price": {"name": "Current price"},
      "average_price_24h": {"name": "24h average price"},
      "forecast_next_hour": {"name": "Next hour forecast"},
      "forecast_peak_today": {"name": "Today's peak price"}
    }
  },
  "exceptions": {
    "config_entry_not_found": {
      "message": "Config entry {entry_id} not found"
    },
    "service_auth_failed": {
      "message": "Service call failed due to authentication error"
    },
    "historical_data_unavailable": {
      "message": "Historical data unavailable for {start_date} to {end_date}"
    }
  },
  "services": {
    "get_historical_prices": {
      "name": "Get historical prices",
      "description": "Retrieve historical electricity prices for a date range",
      "fields": {
        "start_date": {"name": "Start date"},
        "end_date": {"name": "End date"},
        "schedule": {"name": "Schedule type"},
        "node": {"name": "Grid node"}
      }
    }
  }
}
```

These detailed patterns provide concrete implementation guidance for transforming the NZ WITS integration into a production-ready, Platinum-quality Home Assistant integration following the exact patterns used by top-tier integrations like NordPool.


## Another Issue to fix.
Home assistant recently brought out integration sub-entries. These allow you to add multiple subentries under the one integration using the same credentials etc. For example, if I wanted to use NZ_WITS to monitor multiple nodes, I wouldn't have to enter the api credentials every time, and they would all come under the same integration entry. CUrrently this integration isn't following this new framework, and each new node I add is creating a new instance of the integration if you know what I mean.