# Development Notes

--------------------------------------------------------------------------------

Nonstandard openapi.json parsing needs hacked up openapi-python-client:
- edit parser/openapi.py, line 169: comment out error append
- edit parser/properties/__init__, line 330: comment out reference schemas error append

--------------------------------------------------------------------------------
