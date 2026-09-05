"""Friday API — FastAPI server for remote control.

Endpoints:
  POST   /v1/goals              Execute a goal
  GET    /v1/goals/{id}         Get goal status
  GET    /v1/goals              List recent goals
  GET    /v1/status             System health
  GET    /v1/memory             Query memory
  POST   /v1/memory             Store a memory
  GET    /v1/patterns           Detected patterns
  GET    /v1/adapter/{name}     Adapter status
  WS     /ws/events             Real-time event stream
"""
