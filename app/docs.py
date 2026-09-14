"""Custom Swagger UI with an embedded OAuth presentation drawer.

The presentation content lives in app/static/presentation.html so it can be
edited directly without touching Python. The drawer fetches it via JS when
opened.
"""

from fastapi.responses import HTMLResponse

_DRAWER_CSS = """
  #errors-drawer-btn {
    position: fixed; top: 62px; right: 16px; z-index: 100;
    padding: 8px 18px; border: none; border-radius: 8px; cursor: pointer;
    font-weight: 700; font-size: 14px; font-family: system-ui, sans-serif;
    background: green; color: white; box-shadow: 0 2px 8px rgba(46,158,79,0.3);
    transition: all 0.2s;
  }
  #errors-drawer-btn:hover { background: #3abf6e; transform: translateY(-1px); }
  #errors-drawer-btn.active { background: #3abf6e; }
  #oauth-drawer-btn {
    position: fixed; top: 12px; right: 16px; z-index: 100;
    padding: 8px 18px; border: none; border-radius: 8px; cursor: pointer;
    font-weight: 700; font-size: 14px; font-family: system-ui, sans-serif;
    background: green; color: white; box-shadow: 0 2px 8px rgba(46,158,79,0.3);
    transition: all 0.2s;
  }
  #oauth-drawer-btn:hover { background: #3abf6e; transform: translateY(-1px); }
  #oauth-drawer-btn.active { background: #3abf6e; }
  #drawer-backdrop {
    position: fixed; inset: 0; background: rgba(0,0,0,0.45); z-index: 9998;
    opacity: 0; pointer-events: none; transition: opacity 0.3s;
  }
  #drawer-backdrop.open { opacity: 1; pointer-events: auto; }
  #oauth-drawer {
    position: fixed; top: 0; right: -100%; width: 85%; max-width: 1100px;
    height: 100vh; background: #fff; z-index: 9999;
    box-shadow: -4px 0 24px rgba(0,0,0,0.18); transition: right 0.35s ease;
    overflow-y: auto; overflow-x: hidden;
  }
  #oauth-drawer.open { right: 0; }
  #drawer-header {
    position: sticky; top: 0; z-index: 10;
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 24px; background: #fff; border-bottom: 1px solid #eee;
  }
  #drawer-header h2 { margin: 0; font-size: 18px; color: #e42527; font-family: system-ui, sans-serif; }
  #drawer-fullscreen {
    background: none; border: none; font-size: 18px; cursor: pointer;
    color: #999; padding: 0 8px; line-height: 1; margin-right: 4px;
  }
  #drawer-fullscreen:hover { color: #333; }
  #drawer-close {
    background: none; border: none; font-size: 28px; cursor: pointer;
    color: #999; padding: 0 8px; line-height: 1;
  }
  #drawer-close:hover { color: #333; }
  #drawer-body { padding: 0 24px 40px; height: calc(100vh - 60px); overflow-y: auto; box-sizing: border-box; }
  #drawer-content { width: 100%; height: 100%; }
  #oauth-drawer:fullscreen {
    width: 100%; max-width: 100%; height: 100vh; background: #fff;
  }
  #oauth-drawer:fullscreen #drawer-body { height: calc(100vh - 60px); }
"""

_DRAWER_JS = """
  var drawerLoadedUrl = null;
  function openDrawer(url, title, btnId) {
    document.getElementById('oauth-drawer').classList.add('open');
    document.getElementById('drawer-backdrop').classList.add('open');
    document.getElementById('drawer-title').textContent = title;
    document.getElementById('errors-drawer-btn').classList.toggle('active', btnId === 'errors-drawer-btn');
    document.getElementById('oauth-drawer-btn').classList.toggle('active', btnId === 'oauth-drawer-btn');
    if (drawerLoadedUrl !== url) {
      var container = document.getElementById('drawer-content');
      container.innerHTML = '<p style="padding:20px;font-family:sans-serif;">Loading presentation...</p>';
      fetch(url)
        .then(function(r) { return r.text(); })
        .then(function(html) {
          var doc = new DOMParser().parseFromString(html, 'text/html');
          container.innerHTML = '';
          doc.querySelectorAll('style, link[rel="stylesheet"]').forEach(function(node) {
            container.appendChild(node.cloneNode(true));
          });
          doc.body.querySelectorAll(':scope > *:not(script)').forEach(function(node) {
            container.appendChild(node);
          });
          var scripts = Array.from(doc.body.querySelectorAll('script'));
          var externalScripts = scripts.filter(function(s) { return s.src; });
          var inlineScripts = scripts.filter(function(s) { return !s.src; });
          function loadNext() {
            if (externalScripts.length === 0) {
              inlineScripts.forEach(function(oldScript) {
                var newScript = document.createElement('script');
                newScript.textContent = oldScript.textContent;
                container.appendChild(newScript);
              });
              return;
            }
            var oldScript = externalScripts.shift();
            var newScript = document.createElement('script');
            newScript.src = oldScript.src;
            newScript.onload = loadNext;
            newScript.onerror = loadNext;
            container.appendChild(newScript);
          }
          loadNext();
          drawerLoadedUrl = url;
        })
        .catch(function(e) { container.innerHTML = '<p style="padding:20px;font-family:sans-serif;">Failed to load presentation: ' + e + '</p>'; });
    }
  }
  function closeDrawer() {
    document.getElementById('oauth-drawer').classList.remove('open');
    document.getElementById('drawer-backdrop').classList.remove('open');
    document.getElementById('errors-drawer-btn').classList.remove('active');
    document.getElementById('oauth-drawer-btn').classList.remove('active');
  }
  function toggleFullscreen() {
    var el = document.getElementById('oauth-drawer');
    if (!document.fullscreenElement) {
      if (el.requestFullscreen) { el.requestFullscreen(); }
    } else {
      if (document.exitFullscreen) { document.exitFullscreen(); }
    }
  }
  document.addEventListener('fullscreenchange', function() {
    var btn = document.getElementById('drawer-fullscreen');
    if (btn) { btn.textContent = document.fullscreenElement ? '\u29c9' : '\u26f6'; }
    setTimeout(function() {
      if (window.Reveal && typeof window.Reveal.layout === 'function') {
        window.Reveal.layout();
      }
    }, 100);
  });
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && document.getElementById('oauth-drawer').classList.contains('open') && !document.fullscreenElement) {
      closeDrawer();
    }
  });
"""


def get_docs_html(openapi_url: str, title: str) -> HTMLResponse:
    """Generate custom Swagger UI HTML with an OAuth presentation drawer button."""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.18.2/swagger-ui.css">
  <style>
    {_DRAWER_CSS}
  </style>
</head>
<body>
  <button id="errors-drawer-btn" onclick="openDrawer('/presentations/errors.html', 'Zoho CRM Error Codes & Rate Limits', 'errors-drawer-btn')">Errors & Rate Limits</button>
  <button id="oauth-drawer-btn" onclick="openDrawer('/presentations/authentication.html', 'Zoho OAuth 2.0 & Token Lifecycle', 'oauth-drawer-btn')">OAuth Presentation</button>

  <div id="swagger-ui"></div>

  <div id="drawer-backdrop" onclick="closeDrawer()"></div>
  <div id="oauth-drawer">
    <div id="drawer-header">
      <h2 id="drawer-title">Zoho OAuth 2.0 & Token Lifecycle</h2>
      <div>
        <button id="drawer-fullscreen" onclick="toggleFullscreen()" title="Toggle fullscreen">&#x26f6;</button>
        <button id="drawer-close" onclick="closeDrawer()">&times;</button>
      </div>
    </div>
    <div id="drawer-body">
      <div id="drawer-content"></div>
    </div>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.18.2/swagger-ui-bundle.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.18.2/swagger-ui-standalone-preset.js"></script>
  <script>
    window.onload = function() {{
      window.ui = SwaggerUIBundle({{
        url: "{openapi_url}",
        dom_id: "#swagger-ui",
        presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
        layout: "StandaloneLayout",
        deepLinking: true
      }});
    }};
  </script>
  <script>
    {_DRAWER_JS}
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)