"""A host agent that turns any MCP server into a voice display.

The display is the browser; this is everything behind it. One turn is:
hear an utterance, decide which tool answers it, call that tool over
Streamable HTTP, and hand back what the tool said plus the card to draw.
"""

__version__ = "0.1.0"
