// The card side of the MCP Apps handshake.
//
// A card provides two globals before this runs:
//   CARD_APP_NAME — the app name sent in ui/initialize
//   CARD_RENDER   — called with the tool's structuredContent when it lands
//
// and gets back:
//   CARD_CALL(name, args) — call a tool on the MCP server, through the host
//   CARD_RENDERED         — how many times CARD_RENDER has run
//
// Inlined into every card, because a card is one self-contained document
// under a tight CSP and can link nothing at runtime.
(function () {
  "use strict";

  var PROTOCOL_VERSION = "2026-01-26";
  var nextId = 1;
  var host = window.parent;
  var initializeId = null;
  var handshakeDone = false;
  var handshakeTimer = null;
  var attempts = 0;
  var MAX_ATTEMPTS = 24; // ~6s at 250ms

  function send(message) { host.postMessage(message, "*"); }
  function notify(method, params) {
    send({ jsonrpc: "2.0", method: method, params: params || {} });
  }

  function reportSize() {
    var height = Math.max(
      document.documentElement.scrollHeight, document.body.scrollHeight
    );
    notify("ui/notifications/size-changed", { height: height });
  }

  // The card cannot know when the host attached its side of the channel. A
  // host that creates the iframe and wires its transport on the load event
  // is not listening yet when the document first runs, so a single
  // fire-and-forget ui/initialize is lost and the card hangs, looking
  // initialised to nobody. The handshake therefore repeats until the host
  // answers, and ui/notifications/initialized is sent only after that
  // answer — the order the lifecycle implies but does not spell out.
  function beginHandshake() {
    // One id for every attempt. A fresh id per retry means the host's reply
    // answers whichever id it saw and no longer matches the id the card is
    // waiting on, so the handshake never completes and the card retries
    // forever. Retransmitting the same id is also the correct JSON-RPC
    // reading of a retry.
    if (initializeId === null) initializeId = nextId++;
    attempts += 1;
    send({
      jsonrpc: "2.0",
      id: initializeId,
      method: "ui/initialize",
      params: {
        protocolVersion: PROTOCOL_VERSION,
        // appInfo/appCapabilities, not the core MCP clientInfo/capabilities.
        // The Apps handshake looks like `initialize` and is not it; a host
        // validating against the published schema rejects the core shape.
        appInfo: { name: window.CARD_APP_NAME || "card", version: "1.0.0" },
        appCapabilities: {}
      }
    });
    if (attempts >= MAX_ATTEMPTS) return;
    handshakeTimer = setTimeout(function () {
      if (!handshakeDone) beginHandshake();
    }, 250);
  }

  function completeHandshake() {
    if (handshakeDone) return;
    handshakeDone = true;
    if (handshakeTimer) clearTimeout(handshakeTimer);
    notify("ui/notifications/initialized", {});
    reportSize();
  }

  var pending = {};

  window.CARD_CALL = function (name, args) {
    return new Promise(function (resolve, reject) {
      var id = nextId++;
      pending[id] = { resolve: resolve, reject: reject };
      send({
        jsonrpc: "2.0", id: id, method: "tools/call",
        params: { name: name, arguments: args || {} }
      });
      setTimeout(function () {
        if (pending[id]) {
          delete pending[id];
          reject(new Error("tools/call timed out: " + name));
        }
      }, 10000);
    });
  };

  function structuredFrom(payload) {
    if (!payload) return null;
    return payload.structuredContent || payload.structured_content || payload;
  }

  function hand(payload) {
    var structured = structuredFrom(payload);
    if (!structured || typeof structured !== "object") return;
    if (typeof window.CARD_RENDER === "function") {
      window.CARD_RENDER(structured);
      // A card declares its name the moment its script runs, which is
      // before any data reaches it — so a test that waits for the name is
      // waiting for the wrong thing and screenshots an empty card. This is
      // the signal that it has been handed its facts and drawn them.
      window.CARD_RENDERED = (window.CARD_RENDERED || 0) + 1;
      reportSize();
    }
  }

  window.addEventListener("message", function (event) {
    var message = event.data;
    if (!message || message.jsonrpc !== "2.0") return;

    if (message.method === "ui/notifications/tool-result" ||
        message.method === "ui/notifications/tool-input") {
      // Data arriving proves the host is there, so stop retrying even if
      // the handshake reply itself went astray.
      completeHandshake();
      var params = message.params || {};
      hand(params.result || params.toolResult || params);
      return;
    }

    if (message.method === "ui/resource-teardown") {
      if (typeof window.CARD_TEARDOWN === "function") window.CARD_TEARDOWN();
      return;
    }

    if (message.id !== undefined && pending[message.id]) {
      var waiter = pending[message.id];
      delete pending[message.id];
      if (message.error) waiter.reject(new Error(message.error.message || "tool call failed"));
      else waiter.resolve(structuredFrom(message.result) || {});
      return;
    }

    if (message.id !== undefined && message.id === initializeId) {
      completeHandshake();
      if (message.result) hand(message.result.toolResult || message.result);
    }
  });

  window.addEventListener("resize", reportSize);
  beginHandshake();
  reportSize();
})();
